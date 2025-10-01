"""High level helper for parsing and emitting JSVV ASCII frames."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from . import constants

try:  # pragma: no cover - pyserial optional dependency
    import serial  # type: ignore
except Exception as exc:  # pragma: no cover
    serial = None  # type: ignore[assignment]
    _PYSERIAL_IMPORT_ERROR = exc
else:  # pragma: no cover
    _PYSERIAL_IMPORT_ERROR = None


class JSVVError(RuntimeError):
    """Generic runtime error raised by :class:`JSVVClient`."""


@dataclass
class SerialSettings:
    """Serial link configuration for the RS-232 transport."""

    port: str = constants.DEFAULT_SERIAL_PORT
    baudrate: int = constants.DEFAULT_BAUDRATE
    parity: str = constants.DEFAULT_PARITY
    stopbits: int = constants.DEFAULT_STOPBITS
    bytesize: int = constants.DEFAULT_BYTESIZE
    timeout: float = constants.DEFAULT_TIMEOUT


@dataclass
class JSVVFrame:
    """Decoded representation of a JSVV frame."""

    mid: str
    params: tuple[str, ...]
    raw: str
    provided_crc: str | None
    calculated_crc: str | None
    spec: constants.CommandSpec | None
    parsed_params: Mapping[str, object]
    received_at: float = field(default_factory=time.time)

    def crc_ok(self) -> bool:
        if self.provided_crc is None:
            return True
        return self.calculated_crc == self.provided_crc.upper()

    def body(self) -> str:
        return " ".join((self.mid, *self.params)) if self.params else self.mid

    def to_json(
        self,
        *,
        network_id: int,
        vyc_id: int,
        kpps_address: str,
        operator_id: int | None = None,
        timestamp: int | None = None,
        priority: str | None = None,
    ) -> dict[str, object]:
        spec = self.spec
        command = spec.command if spec else self.mid
        payload_priority = priority if priority is not None else (spec.priority if spec else "P3")
        params = dict(self.parsed_params)
        if not params and self.params:
            params = {"tokens": list(self.params)}

        payload_timestamp = timestamp
        if payload_timestamp is None and "timestamp" in params:
            extracted = params.get("timestamp")
            if isinstance(extracted, int):
                payload_timestamp = extracted
        if payload_timestamp is None:
            payload_timestamp = int(self.received_at)

        message = {
            "networkId": network_id,
            "vycId": vyc_id,
            "kppsAddress": kpps_address,
            "operatorId": operator_id,
            "type": spec.type if spec else "UNKNOWN",
            "command": command,
            "params": params,
            "priority": payload_priority,
            "timestamp": payload_timestamp,
            "rawMessage": self.body(),
        }
        if self.provided_crc is not None:
            message["crc"] = {
                "provided": self.provided_crc,
                "calculated": self.calculated_crc,
                "valid": self.crc_ok(),
            }
        return message

    def build_dedup_key(
        self,
        *,
        network_id: int,
        vyc_id: int,
        kpps_address: str,
        operator_id: int | None,
        timestamp: int,
    ) -> str:
        command = self.spec.command if self.spec else self.mid
        normalized_params = json.dumps(self.parsed_params, sort_keys=True, separators=(",", ":"))
        parts = [
            str(network_id),
            str(vyc_id),
            kpps_address,
            command,
            normalized_params,
            str(operator_id or 0),
            str(timestamp),
        ]
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return digest


class JSVVClient:
    """Read and write ASCII framed JSVV messages with CRC validation."""

    @classmethod
    def from_defaults(cls) -> "JSVVClient":
        return cls(SerialSettings())

    def __init__(
        self,
        settings: SerialSettings,
        *,
        dedup_window: float = constants.DEFAULT_DEDUP_WINDOW_SECONDS,
        audio_root: Path | None = None,
    ) -> None:
        self.settings = settings
        self._serial: Any | None = None
        self._connected = False
        self._dedup_window = dedup_window
        self._recent: MutableMapping[str, float] = {}
        self._audio_root = self._resolve_audio_root(audio_root)
        self._verbal_index = self._load_verbal_index(self._audio_root)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def __enter__(self) -> "JSVVClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._connected:
            return
        if serial is None:
            raise JSVVError(
                "pyserial is not available. Install it with 'pip install pyserial'."
            ) from _PYSERIAL_IMPORT_ERROR
        self._serial = serial.Serial(  # type: ignore[name-defined]
            port=self.settings.port,
            baudrate=self.settings.baudrate,
            parity=self.settings.parity,
            stopbits=self.settings.stopbits,
            bytesize=self.settings.bytesize,
            timeout=self.settings.timeout,
        )
        self._connected = True

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self._connected = False

    # ------------------------------------------------------------------
    # Frame helpers
    # ------------------------------------------------------------------
    def send_frame(self, mid: str, params: Sequence[object] = (), *, include_crc: bool = True) -> str:
        if not self._connected or self._serial is None:
            raise JSVVError("Client is not connected; call connect() first")
        payload = self._build_frame(mid, [str(token) for token in params], include_crc=include_crc)
        data = payload.encode(constants.FRAME_ENCODING)
        written = self._serial.write(data)
        if written != len(data):  # pragma: no cover - depends on pyserial transport
            raise JSVVError("Failed to write complete frame to serial port")
        return payload

    def receive_frame(self, *, timeout: float | None = None, validate_crc: bool = True) -> JSVVFrame:
        if not self._connected or self._serial is None:
            raise JSVVError("Client is not connected; call connect() first")
        original_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            raw_bytes = self._serial.readline()
        finally:
            if timeout is not None:
                self._serial.timeout = original_timeout
        if not raw_bytes:
            raise JSVVError("No data received before timeout expired")
        try:
            decoded = raw_bytes.decode(constants.FRAME_ENCODING)
        except UnicodeDecodeError as exc:
            raise JSVVError("Received frame is not valid ASCII") from exc
        frame = self.parse_frame(decoded, validate_crc=validate_crc)
        return frame

    # ------------------------------------------------------------------
    # Message to JSON helpers
    # ------------------------------------------------------------------
    def validate_and_track(
        self,
        frame: JSVVFrame,
        *,
        network_id: int,
        vyc_id: int,
        kpps_address: str,
        operator_id: int | None = None,
        timestamp: int | None = None,
    ) -> bool:
        payload_timestamp = timestamp if timestamp is not None else int(frame.received_at)
        dedup_key = frame.build_dedup_key(
            network_id=network_id,
            vyc_id=vyc_id,
            kpps_address=kpps_address,
            operator_id=operator_id,
            timestamp=payload_timestamp,
        )
        now = time.time()
        self._evict_old(now)
        if dedup_key in self._recent:
            if self._recent[dedup_key] >= now:
                return False
        self._recent[dedup_key] = now + self._dedup_window
        return True

    def build_json_payload(
        self,
        frame: JSVVFrame,
        *,
        network_id: int,
        vyc_id: int,
        kpps_address: str,
        operator_id: int | None = None,
        timestamp: int | None = None,
        priority: str | None = None,
    ) -> dict[str, object]:
        return frame.to_json(
            network_id=network_id,
            vyc_id=vyc_id,
            kpps_address=kpps_address,
            operator_id=operator_id,
            timestamp=timestamp,
            priority=priority,
        )

    # ------------------------------------------------------------------
    # Verbal asset helpers
    # ------------------------------------------------------------------
    def get_verbal_asset(self, slot: int, voice: str = "male") -> Path:
        normalized_voice = self._normalize_voice(voice)
        if normalized_voice:
            key = (slot, normalized_voice)
            if key in self._verbal_index:
                return self._verbal_index[key]
        fallback_key = (slot, "male") if normalized_voice != "male" else None
        if fallback_key and fallback_key in self._verbal_index:
            return self._verbal_index[fallback_key]
        any_key = next((path for (idx, _voice), path in self._verbal_index.items() if idx == slot), None)
        if any_key is not None:
            return any_key
        raise JSVVError(f"No audio asset found for slot {slot}")

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------
    @staticmethod
    def parse_frame(raw: str, *, validate_crc: bool = True) -> JSVVFrame:
        stripped = raw.rstrip("\r\n")
        if not stripped:
            raise JSVVError("Received empty frame")
        tokens = stripped.split()
        if not tokens:
            raise JSVVError("Frame does not contain any tokens")

        provided_crc: str | None = None
        body_tokens = tokens
        if len(tokens) >= 3 and tokens[-2].upper() == "CRC":
            provided_crc = tokens[-1].upper()
            body_tokens = tokens[:-2]
        if not body_tokens:
            raise JSVVError("CRC section present but no body tokens found")

        mid = body_tokens[0]
        params = tuple(body_tokens[1:])
        body = " ".join(body_tokens)
        calculated_crc: str | None = None
        if provided_crc is not None:
            calculated_crc = JSVVClient._format_crc(JSVVClient._calculate_crc(body))
            if validate_crc and calculated_crc != provided_crc:
                raise JSVVError(
                    f"CRC mismatch for MID {mid}: provided {provided_crc}, calculated {calculated_crc}"
                )

        spec = constants.COMMAND_SPECS.get(mid)
        parsed_params: Mapping[str, object] = {}
        if spec is not None and spec.parameters:
            parsed_params = JSVVClient._parse_params(spec, list(params))
        elif params:
            parsed_params = {"tokens": list(params)}

        return JSVVFrame(
            mid=mid,
            params=params,
            raw=stripped,
            provided_crc=provided_crc,
            calculated_crc=calculated_crc,
            spec=spec,
            parsed_params=parsed_params,
        )

    @staticmethod
    def _build_frame(mid: str, params: Sequence[str], *, include_crc: bool) -> str:
        if not mid:
            raise JSVVError("MID must be a non-empty string")
        if any(" " in token or "\n" in token for token in params):
            raise JSVVError("Parameters must not contain spaces or newlines; encode payload before sending")
        body_tokens = [mid, *params] if params else [mid]
        body = " ".join(body_tokens)
        if include_crc:
            crc = JSVVClient._format_crc(JSVVClient._calculate_crc(body))
            return f"{body} CRC {crc}{constants.FRAME_TERMINATOR}"
        return f"{body}{constants.FRAME_TERMINATOR}"

    @staticmethod
    def build_frame(mid: str, params: Sequence[object] = (), *, include_crc: bool = True) -> str:
        string_params = [str(token) for token in params]
        return JSVVClient._build_frame(mid, string_params, include_crc=include_crc)

    @staticmethod
    def _calculate_crc(data: str) -> int:
        crc = constants.CRC_INITIAL_VALUE
        for byte in data.encode(constants.FRAME_ENCODING):
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ constants.CRC_POLYNOMIAL) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    @staticmethod
    def _format_crc(value: int) -> str:
        return f"{value:04X}"

    @staticmethod
    def _parse_params(spec: constants.CommandSpec, tokens: Sequence[str]) -> Mapping[str, object]:
        parsed: dict[str, object] = {}
        index = 0
        total = len(tokens)
        for parameter in spec.parameters:
            if parameter.rest:
                if index >= total:
                    if parameter.optional:
                        continue
                    raise JSVVError(f"Missing value for parameter '{parameter.name}'")
                rest_tokens = tokens[index:]
                try:
                    parsed[parameter.name] = parameter.parser(" ".join(rest_tokens))
                except Exception as exc:  # pragma: no cover - parser callable may vary
                    raise JSVVError(f"Failed to parse parameter '{parameter.name}'") from exc
                index = total
                break
            if index >= total:
                if parameter.optional:
                    continue
                raise JSVVError(f"Missing value for parameter '{parameter.name}'")
            token = tokens[index]
            try:
                parsed[parameter.name] = parameter.parser(token)
            except Exception as exc:  # pragma: no cover - parser callable may vary
                raise JSVVError(f"Failed to parse parameter '{parameter.name}'") from exc
            index += 1
        if index < total:
            parsed.setdefault("extra", list(tokens[index:]))
        return parsed

    @staticmethod
    def _resolve_audio_root(audio_root: Path | None) -> Path:
        if audio_root is not None:
            return audio_root
        base = Path(__file__).resolve().parents[2]
        return base / constants.AUDIO_ASSET_SUBDIR

    @staticmethod
    def _load_verbal_index(root: Path) -> MutableMapping[tuple[int, str], Path]:
        index: MutableMapping[tuple[int, str], Path] = {}
        if not root.exists():
            return index
        for path in root.glob("*.mp3"):
            slot = JSVVClient._extract_slot(path.stem)
            if slot is None:
                continue
            voice = JSVVClient._extract_voice(path.stem)
            if voice is None:
                voice = "male"
            index[(slot, voice)] = path
        return index

    @staticmethod
    def _extract_slot(stem: str) -> int | None:
        match = re.search(r"\d+", stem)
        if not match:
            return None
        try:
            return int(match.group(0), 10)
        except ValueError:
            return None

    @staticmethod
    def _extract_voice(stem: str) -> str | None:
        normalized = JSVVClient._normalize_text(stem)
        if "female" in normalized or "zena" in normalized:
            return "female"
        if "muz" in normalized:
            return "male"
        if "woman" in normalized:
            return "female"
        if "male" in normalized:
            return "male"
        if "man" in normalized:
            return "male"
        return None

    @staticmethod
    def _normalize_voice(voice: str) -> str:
        normalized = JSVVClient._normalize_text(voice)
        if normalized in {"female", "zena", "zen"}:
            return "female"
        if normalized in {"male", "muz", "man"}:
            return "male"
        return normalized

    @staticmethod
    def _normalize_text(text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()

    def _evict_old(self, now: float) -> None:
        expired = [key for key, deadline in self._recent.items() if deadline < now]
        for key in expired:
            self._recent.pop(key, None)
