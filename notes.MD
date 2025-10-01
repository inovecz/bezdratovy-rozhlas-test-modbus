Dle aktualniho nastaveni plati toto:


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


Korektni nastaveni pro komunikaci skrze modbus:
SERIAL_SETTINGS = SerialSettings(
    port="/dev/tty.usbserial-AV0K3CPZ",  # change to the serial port used on your system
    baudrate=57600,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1.0,
)
UNIT_ID = 1


