"""Constant values and command metadata for the JSVV communication layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


# Serial link defaults as per zadani_deepsearch_jsvv.txt
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_TIMEOUT = 1.0

FRAME_TERMINATOR = "\n"
FRAME_ENCODING = "ascii"

CRC_POLYNOMIAL = 0x1021
CRC_INITIAL_VALUE = 0x0000

DEFAULT_DEDUP_WINDOW_SECONDS = 180.0

AUDIO_ASSET_SUBDIR = "assets/jsvv/verbal-informations"


ParserFunc = Callable[[str], object]


def parse_int(value: str) -> int:
    """Parse integer tokens that may be decimal or hex (0x prefix)."""

    return int(value, 0)


def identity(value: str) -> str:
    return value


@dataclass(frozen=True)
class ParameterSpec:
    """Describe a single token mapping for known JSVV commands."""

    name: str
    parser: ParserFunc = identity
    optional: bool = False
    rest: bool = False
    description: str | None = None


@dataclass(frozen=True)
class CommandSpec:
    """Metadata describing a JSVV MID and its semantic mapping."""

    mid: str
    command: str
    type: str
    priority: str
    parameters: Sequence[ParameterSpec] = ()
    description: str | None = None
    expects_response: bool = False


COMMAND_SPECS: dict[str, CommandSpec] = {
    "SIREN": CommandSpec(
        mid="SIREN",
        command="SIREN_SIGNAL",
        type="ACTIVATION",
        priority="P2",
        parameters=(
            ParameterSpec("signalType", parse_int),
            ParameterSpec("duration", parse_int, optional=True),
        ),
        description="Activate acoustic siren with optional duration.",
    ),
    "GONG": CommandSpec(
        mid="GONG",
        command="GONG",
        type="ACTIVATION",
        priority="P3",
        parameters=(ParameterSpec("gongType", parse_int),),
    ),
    "VERBAL": CommandSpec(
        mid="VERBAL",
        command="VERBAL_INFO",
        type="ACTIVATION",
        priority="P2",
        parameters=(ParameterSpec("slot", parse_int), ParameterSpec("voice", identity, optional=True)),
        description="Play a pre-recorded verbal information slot.",
    ),
    "RADIO": CommandSpec(
        mid="RADIO",
        command="RADIO_BRIDGE",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
        description="Route audio from connected radio receiver.",
    ),
    "REMOTE": CommandSpec(
        mid="REMOTE",
        command="REMOTE_VOICE",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
        description="Enable live audio from the VyC microphone.",
    ),
    "LOCAL": CommandSpec(
        mid="LOCAL",
        command="LOCAL_VOICE",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
        description="Enable local microphone audio.",
    ),
    "EXT1": CommandSpec(
        mid="EXT1",
        command="EXTERNAL_AUDIO_PRIMARY",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
    ),
    "EXT2": CommandSpec(
        mid="EXT2",
        command="EXTERNAL_AUDIO_SECONDARY",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
    ),
    "TEXT": CommandSpec(
        mid="TEXT",
        command="TEXT_PANEL",
        type="ACTIVATION",
        priority="P3",
        parameters=(ParameterSpec("text", identity, rest=True),),
    ),
    "STOP": CommandSpec(
        mid="STOP",
        command="STOP",
        type="ACTIVATION",
        priority="P1",
        parameters=(),
    ),
    "RESET": CommandSpec(
        mid="RESET",
        command="RESET",
        type="ACTIVATION",
        priority="P1",
        parameters=(),
    ),
    "TEST": CommandSpec(
        mid="TEST",
        command="TEST",
        type="ACTIVATION",
        priority="P3",
        parameters=(),
    ),
    "READ_CFG": CommandSpec(
        mid="READ_CFG",
        command="READ_CFG",
        type="QUERY",
        priority="P1",
        parameters=(),
        expects_response=True,
    ),
    "READ_ADR": CommandSpec(
        mid="READ_ADR",
        command="READ_ADR",
        type="QUERY",
        priority="P1",
        parameters=(),
        expects_response=True,
    ),
    "READ_LOG": CommandSpec(
        mid="READ_LOG",
        command="READ_LOG",
        type="QUERY",
        priority="P1",
        parameters=(ParameterSpec("limit", parse_int, optional=True),),
        expects_response=True,
    ),
    "STATUS_KPPS": CommandSpec(
        mid="STATUS_KPPS",
        command="STATUS_KPPS",
        type="STATUS",
        priority="P1",
        parameters=(),
    ),
    "STATUS_EKPV": CommandSpec(
        mid="STATUS_EKPV",
        command="STATUS_EKPV",
        type="STATUS",
        priority="P1",
        parameters=(),
    ),
    "STATUS_KPM": CommandSpec(
        mid="STATUS_KPM",
        command="STATUS_KPM",
        type="STATUS",
        priority="P1",
        parameters=(),
    ),
    "FAULT": CommandSpec(
        mid="FAULT",
        command="FAULT",
        type="FAULT",
        priority="P1",
        parameters=(
            ParameterSpec("device", identity),
            ParameterSpec("code", parse_int),
            ParameterSpec("detail", identity, optional=True, rest=True),
        ),
    ),
}
