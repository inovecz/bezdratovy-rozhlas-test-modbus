"""Constant values describing Modbus register layout for the VP_PRIJIMAC devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


NUM_ADDR_RAM = 0x0000
ADDR_RAM_BASE = 0x0001
MAX_ADDR_ENTRIES = 5

RF_DEST_ZONE_BASE = 0x4030
MAX_DEST_ZONES = 5

# Legacy documentation mentioned 0x5035 (TxControl) for transmitters. Current
# hardware toggles streaming via register 0x4035 instead.
TX_CONTROL = 0x4035
RX_CONTROL = 0x4035

STATUS_REGISTER = 0x4036
ERROR_REGISTER = 0x4037
OGG_BITRATE = 0x403F

FREQUENCY_REGISTER = 0x4024
SERIAL_NUMBER_BLOCK = (0x4000, 3)

DEFAULT_SERIAL_PORT = "/dev/ttyAMA3"  #tty.usbserial-AV0K3CPZ
DEFAULT_BAUDRATE = 57600
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_TIMEOUT = 1.0
DEFAULT_UNIT_ID = 1

DEFAULT_ROUTE = (1, 116, 225)
DEFAULT_DESTINATION_ZONES = (22,)
DEFAULT_FREQUENCY = 7100
PROBE_REGISTER = 0x0000

# Optional RS485 direction control via GPIO.
ENABLE_RS485_GPIO = True                    # false
RS485_GPIO_CHIP = "/dev/gpiochip0"
RS485_GPIO_LINE_OFFSET = 16
RS485_GPIO_ACTIVE_HIGH = True
RS485_GPIO_CONSUMER = "modbus-audio"


@dataclass(frozen=True)
class RegisterBlock:
    """Descriptor of a contiguous register block."""

    start: int
    quantity: int = 1

    def to_slice(self) -> slice:
        return slice(self.start, self.start + self.quantity)


@dataclass(frozen=True)
class RegisterDescriptor:
    """Metadata describing a documented Modbus register block."""

    name: str
    block: RegisterBlock
    readable: bool = True
    description: str | None = None


DEVICE_INFO_REGISTERS = {
    "serial_number": RegisterBlock(SERIAL_NUMBER_BLOCK[0], SERIAL_NUMBER_BLOCK[1]),
    "slave_address": RegisterBlock(0x4003),
    "rf_address": RegisterBlock(0x4004, 5),
    "rf_net_id": RegisterBlock(0x4022),
    "mode": RegisterBlock(0x4023),
    "frequency": RegisterBlock(FREQUENCY_REGISTER),
    "num_configured_addresses": RegisterBlock(0x4025),
    "configured_route": RegisterBlock(0x4026, 5),
    "destination_zones": RegisterBlock(RF_DEST_ZONE_BASE, MAX_DEST_ZONES),
    "rx_control": RegisterBlock(RX_CONTROL),
    "status": RegisterBlock(STATUS_REGISTER),
    "error": RegisterBlock(ERROR_REGISTER),
    "ogg_bitrate": RegisterBlock(OGG_BITRATE),
    "instrument_id": RegisterBlock(0xFFF3),
    "hardware_version": RegisterBlock(0xFFF4),
    "firmware_version": RegisterBlock(0xFFF5),
    "firmware_date": RegisterBlock(0xFFF9, 2),
    "unit_number": RegisterBlock(0xFFFB, 4),
}


def register_block_to_request(blocks: Sequence[RegisterBlock]) -> Sequence[RegisterBlock]:
    """Return merged register blocks to minimise round-trips.

    The Modbus protocol incurs overhead per call. When requesting multiple blocks,
    it is more efficient to merge overlapping or adjacent blocks into a single
    request. This helper keeps the code readable inside the client module.
    """

    if not blocks:
        return []

    sorted_blocks = sorted(blocks, key=lambda b: b.start)
    merged: list[RegisterBlock] = []

    for block in sorted_blocks:
        if not merged:
            merged.append(block)
            continue

        prev = merged[-1]
        prev_end = prev.start + prev.quantity
        block_end = block.start + block.quantity

        if block.start <= prev_end:
            # Overlap or adjacency: merge by extending the previous block.
            merged[-1] = RegisterBlock(prev.start, max(prev_end, block_end) - prev.start)
        else:
            merged.append(block)

    return merged


DOCUMENTED_REGISTERS: tuple[RegisterDescriptor, ...] = (
    RegisterDescriptor("numAddrRam", RegisterBlock(NUM_ADDR_RAM), description="Number of hop addresses in RAM"),
    RegisterDescriptor("Addr0Ram", RegisterBlock(0x0001)),
    RegisterDescriptor("Addr1Ram", RegisterBlock(0x0002)),
    RegisterDescriptor("Addr2Ram", RegisterBlock(0x0003)),
    RegisterDescriptor("Addr3Ram", RegisterBlock(0x0004)),
    RegisterDescriptor("Addr4Ram", RegisterBlock(0x0005)),
    RegisterDescriptor("SWRESET", RegisterBlock(0x0666), readable=False, description="Software reset"),
    RegisterDescriptor("RESET", RegisterBlock(0x0667), readable=False, description="Hardware reset"),
    RegisterDescriptor("Buff0-9", RegisterBlock(0x3000, 10), description="Inbound RF buffer"),
    RegisterDescriptor("SerialNumber", RegisterBlock(SERIAL_NUMBER_BLOCK[0], SERIAL_NUMBER_BLOCK[1])),
    RegisterDescriptor("SlaveAddr", RegisterBlock(0x4003)),
    RegisterDescriptor("RFAddr0-4", RegisterBlock(0x4004, 5)),
    RegisterDescriptor("RFNetID", RegisterBlock(0x4022)),
    RegisterDescriptor("Mode", RegisterBlock(0x4023)),
    RegisterDescriptor("Frequency", RegisterBlock(FREQUENCY_REGISTER)),
    RegisterDescriptor("numAddrFlash", RegisterBlock(0x4025)),
    RegisterDescriptor("Addr0Flash-4", RegisterBlock(0x4026, 5)),
    RegisterDescriptor("RFDestZone0-4", RegisterBlock(RF_DEST_ZONE_BASE, MAX_DEST_ZONES)),
    RegisterDescriptor("RxControl", RegisterBlock(RX_CONTROL)),
    RegisterDescriptor("TxControl", RegisterBlock(TX_CONTROL), readable=False),
    RegisterDescriptor("Status", RegisterBlock(STATUS_REGISTER)),
    RegisterDescriptor("Error", RegisterBlock(ERROR_REGISTER)),
    RegisterDescriptor("OggBitrate", RegisterBlock(OGG_BITRATE)),
    RegisterDescriptor("InstrumentID", RegisterBlock(0xFFF3)),
    RegisterDescriptor("HardwareVersion", RegisterBlock(0xFFF4)),
    RegisterDescriptor("FirmwareVersion", RegisterBlock(0xFFF5)),
    RegisterDescriptor("FirmwareDate", RegisterBlock(0xFFF9, 2)),
    RegisterDescriptor("UnitNumber", RegisterBlock(0xFFFB, 4)),
)
