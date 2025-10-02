"""High level helper for interacting with VP_PRIJIMAC Modbus receivers/transmitters.

The module builds on top of :mod:`pymodbus` and focuses on the register layout
summarised in ``constants.py``. It intentionally keeps the surface small so the
code can run on macOS or Linux (including Raspberry Pi).
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Iterable, Mapping, MutableMapping

from . import constants

try:  # pragma: no cover - depends on installed pymodbus variant
    from pymodbus.client import ModbusSerialClient as _SerialClient
except Exception:  # pragma: no cover - fallback for pymodbus < 3
    try:
        from pymodbus.client.sync import ModbusSerialClient as _SerialClient
    except Exception as exc:  # pragma: no cover - surfaced as runtime error
        _SerialClient = None  # type: ignore[assignment]
        _PYMODBUS_IMPORT_ERROR = exc
    else:
        _PYMODBUS_IMPORT_ERROR = None
else:
    _PYMODBUS_IMPORT_ERROR = None

try:  # pragma: no cover - pymodbus optional dependency
    from pymodbus.exceptions import ModbusIOException
except Exception:  # pragma: no cover
    ModbusIOException = Exception  # type: ignore[misc, assignment]


class ModbusAudioError(RuntimeError):
    """Generic runtime error raised by :class:`ModbusAudioClient`."""


@dataclass
class SerialSettings:
    """Settings forwarded to :class:`pymodbus.client.ModbusSerialClient`."""

    port: str = constants.DEFAULT_SERIAL_PORT
    method: str = "rtu"
    baudrate: int = constants.DEFAULT_BAUDRATE
    parity: str = constants.DEFAULT_PARITY
    stopbits: int = constants.DEFAULT_STOPBITS
    bytesize: int = constants.DEFAULT_BYTESIZE
    timeout: float = constants.DEFAULT_TIMEOUT


class ModbusAudioClient:
    """Convenience wrapper around ``pymodbus`` for this specific device family."""

    @classmethod
    def from_defaults(cls) -> "ModbusAudioClient":
        """Create a client using the default serial settings and unit id."""

        return cls(SerialSettings(), unit_id=constants.DEFAULT_UNIT_ID)

    def __init__(self, settings: SerialSettings, unit_id: int = 55) -> None:
        if _SerialClient is None:
            raise ModbusAudioError(
                "pymodbus is not available. Install it with 'pip install pymodbus[serial]'."
            ) from _PYMODBUS_IMPORT_ERROR

        self.settings = settings
        self.unit_id = unit_id
        serial_kwargs = self._build_serial_kwargs(settings)
        self._client = _SerialClient(**serial_kwargs)
        self._connected = False

    # ---------------------------------------------------------------------
    # Context manager helpers
    # ---------------------------------------------------------------------
    def __enter__(self) -> "ModbusAudioClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        if self._connected:
            return

        if not self._client.connect():
            raise ModbusAudioError(f"Unable to open serial port {self.settings.port}")

        self._connected = True

    def close(self) -> None:
        if self._connected:
            self._client.close()
            self._connected = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_device_info(self) -> Mapping[str, object]:
        """Collect a snapshot of the most useful device registers."""

        blocks = list(constants.DEVICE_INFO_REGISTERS.values())
        merged = constants.register_block_to_request(blocks)

        cache: MutableMapping[int, int] = {}
        for block in merged:
            for offset, value in enumerate(self._read_registers(block.start, block.quantity)):
                cache[block.start + offset] = value

        info: dict[str, object] = {}
        for name, block in constants.DEVICE_INFO_REGISTERS.items():
            words = [cache[block.start + idx] for idx in range(block.quantity)]
            info[name] = self._format_register_value(name, words)

        return info

    def read_register(self, address: int, unit: int | None = None) -> int:
        """Read a single holding register."""

        return self._read_registers(address, 1, unit=unit)[0]

    def read_registers(self, address: int, quantity: int, unit: int | None = None) -> list[int]:
        """Read multiple holding registers."""

        return self._read_registers(address, quantity, unit=unit)

    def probe(self, register: int = constants.PROBE_REGISTER, unit: int | None = None) -> int:
        """Read a register to verify the device responds."""

        return self.read_register(register, unit=unit)

    def read_serial_number(self) -> str:
        """Return the device serial number as a hexadecimal string."""

        block = constants.DEVICE_INFO_REGISTERS["serial_number"]
        words = self.read_registers(block.start, block.quantity)
        return "".join(f"{word:04X}" for word in words)

    def read_frequency(self, unit: int | None = None) -> int:
        """Return the configured RF frequency (register 0x4024)."""

        return self.read_register(constants.FREQUENCY_REGISTER, unit=unit)

    def write_frequency(self, value: int | None = None, unit: int | None = None) -> None:
        """Set the RF frequency register; defaults to the documented value."""

        target = constants.DEFAULT_FREQUENCY if value is None else value
        self.write_register(constants.FREQUENCY_REGISTER, target, unit=unit)

    def start_stream(self, zones: Iterable[int] | None = None) -> None:
        """Start audio streaming by writing ``2`` into TxControl (0x4035)."""

        zone_values = list(zones) if zones is not None else list(constants.DEFAULT_DESTINATION_ZONES)
        if zone_values:
            self.set_destination_zones(zone_values)
        # Some firmware revisions only honour TxControl writes when issued via
        # function code 16 (write multiple registers), even for a single word.
        self.write_registers(constants.TX_CONTROL, (2,))

    def stop_stream(self) -> None:
        """Stop audio streaming by writing ``1`` into TxControl (0x4035)."""

        self.write_registers(constants.TX_CONTROL, (1,))

    def write_register(self, address: int, value: int, unit: int | None = None) -> None:
        """Write a single holding register."""

        try:
            response = self._call_with_unit(
                self._client.write_register,
                address=address,
                value=value,
                unit=unit,
            )
        except ModbusIOException as exc:  # pragma: no cover - depends on transport
            raise ModbusAudioError(
                f"No response while writing register 0x{address:04X}; verify wiring, port, and unit id"
            ) from exc
        if getattr(response, "isError", lambda: False)():  # pragma: no cover - depends on pymodbus
            raise ModbusAudioError(f"Modbus error while writing register 0x{address:04X}")

    def write_registers(self, address: int, values: Iterable[int], unit: int | None = None) -> None:
        """Write consecutive holding registers."""

        value_list = list(values)
        try:
            response = self._call_with_unit(
                self._client.write_registers,
                address=address,
                values=value_list,
                unit=unit,
            )
        except ModbusIOException as exc:  # pragma: no cover - depends on transport
            raise ModbusAudioError(
                f"No response while writing registers starting at 0x{address:04X}; check connection"
            ) from exc
        if getattr(response, "isError", lambda: False)():  # pragma: no cover - depends on pymodbus
            raise ModbusAudioError(
                f"Modbus error while writing {len(value_list)} registers starting at 0x{address:04X}"
            )

    def configure_route(self, addresses: Iterable[int]) -> None:
        """Populate the RAM routing table (0x0000..0x0005)."""

        addr_list = list(addresses)
        if len(addr_list) > constants.MAX_ADDR_ENTRIES:
            raise ValueError(
                f"At most {constants.MAX_ADDR_ENTRIES} hop addresses are supported; received {len(addr_list)}"
            )

        padded = addr_list + [0] * (constants.MAX_ADDR_ENTRIES - len(addr_list))
        self.write_register(constants.NUM_ADDR_RAM, len(addr_list))
        self.write_registers(constants.ADDR_RAM_BASE, padded[: constants.MAX_ADDR_ENTRIES])

    def set_destination_zones(self, zones: Iterable[int]) -> None:
        """Configure the destination zone registers (0x4030..0x4034)."""

        zone_list = list(zones)
        if len(zone_list) > constants.MAX_DEST_ZONES:
            raise ValueError(
                f"At most {constants.MAX_DEST_ZONES} destination zones are supported; received {len(zone_list)}"
            )

        padded = zone_list + [0] * (constants.MAX_DEST_ZONES - len(zone_list))
        self.write_registers(constants.RF_DEST_ZONE_BASE, padded[: constants.MAX_DEST_ZONES])

    def start_audio_stream(self, hop_addresses: Iterable[int], zones: Iterable[int] | None = None) -> None:
        """Send the sequence of writes needed to start broadcasting audio."""

        self.configure_route(hop_addresses)
        if zones is not None:
            self.set_destination_zones(zones)
        self.write_registers(constants.TX_CONTROL, (2,))

    def stop_audio_stream(self) -> None:
        """Stop the audio stream by clearing ``TxControl`` (0x4035)."""

        self.write_registers(constants.TX_CONTROL, (1,))

    def dump_documented_registers(self) -> list[tuple[str, str, str, str]]:
        """Return a table of documented registers and their current values."""

        rows: list[tuple[str, str, str, str]] = []
        for desc in constants.DOCUMENTED_REGISTERS:
            address = f"0x{desc.block.start:04X}"
            quantity = str(desc.block.quantity)

            if not desc.readable:
                rows.append((desc.name, address, quantity, "write-only"))
                continue

            try:
                values = self.read_registers(desc.block.start, desc.block.quantity)
            except ModbusAudioError as exc:
                rows.append((desc.name, address, quantity, f"error: {exc}"))
                continue

            rendered = (
                str(values[0]) if desc.block.quantity == 1 else "[" + ", ".join(str(v) for v in values) + "]"
            )
            rows.append((desc.name, address, quantity, rendered))

        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _read_registers(self, address: int, quantity: int, unit: int | None = None) -> list[int]:
        try:
            response = self._call_with_unit(
                self._client.read_holding_registers,
                address=address,
                count=quantity,
                unit=unit,
            )
        except ModbusIOException as exc:  # pragma: no cover - depends on transport
            raise ModbusAudioError(
                f"No response while reading register(s) 0x{address:04X}-0x{address + quantity - 1:04X};"
                " verify port, wiring, baud rate, and unit id"
            ) from exc
        if getattr(response, "isError", lambda: False)():  # pragma: no cover - depends on pymodbus
            raise ModbusAudioError(
                f"Modbus error while reading {quantity} register(s) starting at 0x{address:04X}"
            )
        if not hasattr(response, "registers"):
            raise ModbusAudioError("Unexpected response payload from pymodbus")
        return list(response.registers)

    @staticmethod
    def _build_serial_kwargs(settings: SerialSettings) -> dict[str, object]:
        """Prepare keyword arguments compatible with the installed pymodbus version."""

        base_kwargs: dict[str, object] = {
            "port": settings.port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "stopbits": settings.stopbits,
            "bytesize": settings.bytesize,
            "timeout": settings.timeout,
        }

        init_signature = inspect.signature(_SerialClient.__init__)
        if "method" in init_signature.parameters:
            base_kwargs["method"] = settings.method
            return base_kwargs

        # pymodbus >= 3.0 removed the 'method' argument; provide the matching framer instead.
        framers = _resolve_framers()

        method_key = settings.method.lower()
        if not framers:
            if method_key == "rtu":
                # Rely on pymodbus default (RTU) if framers could not be located.
                return base_kwargs
            raise ModbusAudioError(
                "Unable to import Modbus framers from pymodbus; install a full pymodbus package"
            )

        if method_key == "rtu" and "rtu" not in framers:
            return base_kwargs

        if method_key not in framers:
            valid = ", ".join(sorted(framers)) or "rtu"
            raise ModbusAudioError(f"Unsupported Modbus method '{settings.method}'. Valid options: {valid}")

        base_kwargs["framer"] = framers[method_key]
        return base_kwargs

    @staticmethod
    def _format_register_value(name: str, words: list[int]) -> object:
        """Convert raw register values to a friendly representation."""

        if not words:
            return None

        if name in {"serial_number", "unit_number"}:
            return "".join(f"{word:04X}" for word in words)

        if name == "firmware_date" and len(words) == 2:
            # YYMM and DD?? layout according to the vendor document.
            year = (words[0] >> 8) + 2000
            month = words[0] & 0xFF
            day = words[1] & 0xFF
            return {"year": year, "month": month, "day": day}

        if name in {"rf_address", "configured_route", "destination_zones"}:
            return words

        if len(words) == 1:
            return words[0]

        return words

    def _call_with_unit(self, method, *, unit: int | None = None, **kwargs):
        """Invoke a pymodbus client method using the appropriate unit/slave keyword."""

        signature = inspect.signature(method)
        target_unit = self.unit_id if unit is None else unit
        if "unit" in signature.parameters:
            kwargs["unit"] = target_unit
        elif "slave" in signature.parameters:
            kwargs["slave"] = target_unit
        return method(**kwargs)


def _resolve_framers() -> dict[str, type]:
    """Locate Modbus framer implementations in the installed pymodbus package."""

    candidates = (
        (
            "pymodbus.transaction",
            "ModbusAsciiFramer",
            "ModbusBinaryFramer",
            "ModbusRtuFramer",
        ),
        (
            "pymodbus.framer.ascii_framer",
            "ModbusAsciiFramer",
            None,
            None,
        ),
        (
            "pymodbus.framer.binary_framer",
            "ModbusBinaryFramer",
            None,
            None,
        ),
        (
            "pymodbus.framer.rtu_framer",
            "ModbusRtuFramer",
            None,
            None,
        ),
        (
            "pymodbus.framer.ascii",
            "ModbusAsciiFramer",
            None,
            None,
        ),
        (
            "pymodbus.framer.binary",
            "ModbusBinaryFramer",
            None,
            None,
        ),
        (
            "pymodbus.framer.rtu",
            "ModbusRtuFramer",
            None,
            None,
        ),
    )

    framers: dict[str, type] = {}
    for module_name, attr1, attr2, attr3 in candidates:
        try:  # pragma: no cover - depends on pymodbus layout
            module = __import__(module_name, fromlist=[name for name in (attr1, attr2, attr3) if name])
        except Exception:
            continue

        if attr1 and hasattr(module, attr1):
            framers.setdefault("ascii", getattr(module, attr1))
        if attr2 and hasattr(module, attr2):
            framers.setdefault("binary", getattr(module, attr2))
        if attr3 and hasattr(module, attr3):
            framers.setdefault("rtu", getattr(module, attr3))

        if {"ascii", "binary", "rtu"}.issubset(framers.keys()):
            break

    return framers
