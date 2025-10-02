"""Utilities for simulating JSVV hardware frames towards the client library."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable, Iterator, Sequence

from .client import JSVVClient, JSVVError, JSVVFrame


@dataclass(frozen=True)
class SimulationEvent:
    """Descriptor of a single simulated hardware frame."""

    mid: str
    params: Sequence[object] = ()
    delay: float = 0.0
    priority: str | None = None
    timestamp: int | None = None
    note: str | None = None


class JSVVSimulator:
    """Build and feed frames into :class:`JSVVClient` as if sent by hardware."""

    def __init__(
        self,
        *,
        network_id: int = 1,
        vyc_id: int = 1,
        kpps_address: str = "0x0001",
        operator_id: int | None = None,
        client: JSVVClient | None = None,
    ) -> None:
        self.network_id = network_id
        self.vyc_id = vyc_id
        self.kpps_address = kpps_address
        self.operator_id = operator_id
        self.client = client or JSVVClient.from_defaults()

    def emit(
        self,
        mid: str,
        params: Sequence[object] = (),
        *,
        priority: str | None = None,
        timestamp: int | None = None,
    ) -> tuple[str, dict[str, object], bool]:
        frame_text = JSVVClient.build_frame(mid, params)
        frame = self._parse(frame_text)
        payload = self.client.build_json_payload(
            frame,
            network_id=self.network_id,
            vyc_id=self.vyc_id,
            kpps_address=self.kpps_address,
            operator_id=self.operator_id,
            timestamp=timestamp,
            priority=priority,
        )
        is_new = self.client.validate_and_track(
            frame,
            network_id=self.network_id,
            vyc_id=self.vyc_id,
            kpps_address=self.kpps_address,
            operator_id=self.operator_id,
            timestamp=payload["timestamp"],
        )
        return frame_text.rstrip("\n"), payload, not is_new

    def run(self, events: Iterable[SimulationEvent]) -> Iterator[dict[str, object]]:
        for event in events:
            if event.delay > 0:
                time.sleep(event.delay)
            raw, payload, duplicate = self.emit(
                event.mid,
                event.params,
                priority=event.priority,
                timestamp=event.timestamp,
            )
            yield {
                "raw": raw,
                "json": payload,
                "duplicate": duplicate,
                "note": event.note,
            }

    def _parse(self, frame_text: str) -> JSVVFrame:
        try:
            return JSVVClient.parse_frame(frame_text)
        except JSVVError as exc:
            raise JSVVError(f"Unable to parse simulated frame '{frame_text.strip()}': {exc}") from exc


SCENARIOS: dict[str, tuple[SimulationEvent, ...]] = {
    "p2_activation": (
        SimulationEvent("SIREN", (1, 180), note="Trigger siren for 180 s"),
        SimulationEvent("TEXT", ("Evakuacni", "hlaseni"), priority="P3", note="Display message on panel"),
    ),
    "p1_stop": (
        SimulationEvent("SIREN", (2, 120), note="Start siren"),
        SimulationEvent("STOP", (), delay=0.5, note="Abort current activity"),
    ),
    "status_roundtrip": (
        SimulationEvent("READ_CFG", (), note="VyC requests configuration"),
        SimulationEvent("READ_CFG", (1, 30, 180, "0000000000000001", 3, 10, 2, 1, 12), note="KPPS responds"),
    ),
    "fault_alarm": (
        SimulationEvent("FAULT", ("KPPS", 42, "Battery", "low"), priority="P1", note="KPPS reports alarm"),
    ),
    "verbal_broadcast": (
        SimulationEvent("GONG", (1,), note="Play opening gong"),
        SimulationEvent("VERBAL", (3, "female"), note="Play prerecorded message slot 3"),
        SimulationEvent("GONG", (2,), note="Play closing gong"),
    ),
    "remote_takeover": (
        SimulationEvent("REMOTE", (), note="Enable remote live voice"),
        SimulationEvent("STOP", (), delay=1.0, note="Operator stops remote session"),
        SimulationEvent("LOCAL", (), note="Fallback to local microphone"),
    ),
    "diagnostics_cycle": (
        SimulationEvent("READ_CFG", (), note="Configuration request"),
        SimulationEvent("STATUS_KPPS", (), note="Query KPPS status"),
        SimulationEvent("STATUS_EKPV", (), note="Query EKPV status"),
        SimulationEvent("READ_LOG", (10,), note="Read last 10 log entries"),
    ),
    "duplicate_guard": (
        SimulationEvent("TEST", (), note="Initial silent test"),
        SimulationEvent("TEST", (), delay=0.1, note="Repeat to exercise dedup handling"),
    ),
    "critical_fault": (
        SimulationEvent("FAULT", ("Battery", 101, "Voltage below 11.5"), priority="P1", note="Battery alarm"),
        SimulationEvent("STOP", (), note="Stop active transmissions"),
        SimulationEvent("RESET", (), note="Perform controlled reset"),
    ),
}
