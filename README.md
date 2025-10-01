Current default hardware setup:


Vysílač:
- slave adresa: 1
- frekvence: 7 100
- RF Addr: 22
- RF Dest Zone: 22

Přijímač #1:
- slave adresa: 1
- frekvence: 7 100
- RF Addr: 116
- RF Dest Zone: 22

Přijímač #2: (ten, ze kterého vede adaptér do sítě)
- slave adresa: 1
- frekvence: 7 100
- RF Addr: 225
- RF Dest Zone: 22

---

## Modbus Helper Library

Python support code for working with the VP_PRIJIMAC digital receiver/transmitter family sits in `src/modbus_audio`. The library wraps the key Modbus registers exposed by the device so that you can

1. inspect the most relevant device registers,
2. write any holding register,
3. populate the routing table and start or stop audio streaming to selected receivers.

### Requirements

- Python 3.10 or newer
- `pymodbus[serial]` (installs `pymodbus` together with the PySerial extras)

Example installation in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pymodbus[serial]
```

> On Windows replace `source .venv/bin/activate` with `.venv\Scripts\activate`.

### Library usage

```python
from modbus_audio import ModbusAudioClient, constants

# Optional: override defaults by editing constants.DEFAULT_SERIAL_PORT, etc.
with ModbusAudioClient.from_defaults() as client:
    info = client.get_device_info()
    print("Device info:", info)

    # Write an arbitrary register (example: tweak RF frequency)
    client.write_frequency(constants.DEFAULT_FREQUENCY)

    # Start audio streaming towards the configured hop/receiver chain
    client.start_stream(zones=constants.DEFAULT_DESTINATION_ZONES)

    # Later on, stop the stream again
    client.stop_stream()
```

- `get_device_info()` returns a dictionary with the key configuration and identification registers (serial number, RF details, zones, firmware identifiers, and diagnostic flags).
- `write_register(address, value)` updates any holding register on the device.
- `start_stream(zones)` updates the destination zones (0x4030..0x4034) and sets `TxControl (0x5035)` to `2` which triggers audio playback on the remote receivers. Use `stop_stream()` to revert `TxControl` to `1`.
- `start_audio_stream(addresses, zones)` remains available when you need to program a hop chain as part of the same call.
- Serial defaults (serial port, baudrate, parity, etc.) live in `modbus_audio.constants`; adjust them once and every helper (library, CLI, and the example script) will pick them up automatically.

### Command line helper

A thin CLI wrapper lives in `src/modbus_audio/cli.py`. Run it directly from the repository root by putting `src` on `PYTHONPATH`:

```bash
PYTHONPATH=src python -m modbus_audio.cli \
    --port /dev/ttyUSB0 \
    --baudrate 57600 \
    --parity N \
    --stopbits 1 \
    --unit-id 1 \
    info --pretty
```

Supported commands:

- `info` → prints the aggregated device snapshot as JSON.
- `read --count N ADDRESS` → reads one or more holding registers.
- `write ADDRESS VALUE` → writes a single holding register.
- `start-audio --addresses ... [--zones ...]` → fills the hop table and starts audio streaming.
- `stop-audio` → stops the stream by writing `1` into `TxControl`.

Values accept decimal (`7100`) or hexadecimal (`0x1BC4`) notation. The CLI surfaces errors from the device or from the transport layer so wiring faults and Modbus exceptions are easy to spot.

### Cross-platform notes

- macOS: use `/dev/tty.usbserial*` or `/dev/cu.*` depending on the adapter.
- Raspberry Pi / Linux: use `/dev/ttyUSB*` or `/dev/ttyAMA0` (after enabling the UART and disabling the console on the port).
- Windows: supply the `COM` port number and keep the default `method=rtu`.

For production use you may want to add logging (pymodbus integrates with Python’s logging module) and wrap the helper in a systemd service or launchd agent.
