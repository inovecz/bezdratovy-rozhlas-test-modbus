import minimalmodbus
import gpiod
import time

# Nastavení GPIO pinu (např. GPIO16 jako výstup)
RS485_DE_RE_PIN = 16
chip = gpiod.Chip('gpiochip0')
line = chip.get_line(RS485_DE_RE_PIN)
line.request(consumer='modbus-de',type=gpiod.LINE_REQ_DIR_OUT)



# Inicializace modbus zařízení (např. přes /dev/ttyUSB0)
instrument = minimalmodbus.Instrument('/dev/ttyAMA3', 1)  # Port, slave address
instrument.serial.baudrate = 57600
instrument.serial.bytesize = 8
instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
instrument.serial.timeout = 0.5
instrument.mode = minimalmodbus.MODE_RTU

def enable_rx():
    line.set_value(0)

def enable_tx():
    line.set_value(1)

def read_register(address):
    try:
        
        enable_tx()
        time.sleep(0.01)
        value = instrument.read_register(16419)
        print(f"Hodnota registru {hex(address)}: {value}")
        enable_rx()
        return value
    except Exception as e:
        print(f"Chyba při čtení registru {hex(address)}: {e}")
        return None

def write_reset_key():
    try:
        print("DE/RE = HIGH")
        enable_rx()
        time.sleep(0.05)
        instrument.write_register(20535,2)
        enable_rx()
        line.release()
        print("DE/RE = low")
        print("Software reset byl uspesne odeslan")
    except Exception as e:
        print(f"Chyba při čtení registru {e}")
        return None    

# write_reset_key()
# Příklad čtení registru Mode (0x4023)
write_reset_key()
