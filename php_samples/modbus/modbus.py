import minimalmodbus
import RPi.GPIO as GPIO
import time

# === KONFIGURACE ===
PORT = '/dev/ttyAMA3'       # nebo '/dev/serial0' podle zařízení
SLAVE_ADDRESS = 3
BAUDRATE = 57600
DE_RE_PIN = 16              # GPIO16
REGISTER = 16437            # register 16437 - ovlada vysilani
VALUE = 1                   # 1 - vypnuti vysilani, 2 - zapnuti vysilani (3. kontrolka v tneto moment sviti cervene)


# spusteni
# 1 - nastaveni vysilac / prijimac (hex: 4023, int: 16419) - 1 prijimac, 0 vysilac
# 2 - zjistim adresy prijimacu (hex: 4005, int: 16389) - vrati mi to 1 z adres, na ktere posloucha / reaguje audio
# 3 - zapisi adresy prijimacu do vysilace (hex: 4030, int: 16432) - zapis adresy (je zde vice registru, do kazdeho se zapisuje 1 adresa) 
# 4 - zapnu vysilani: (hex: , int: 16437), 1 - vypnuti vysilani, 2 - zapnuti vysilani (3. kontrola v tento moment sviti cervene)
#   - na prijimaci bude zelena kontrolka, ktera nyni blika, blikat rychleji

# obecne
# pri cteni - enable_rx
# pri zapisu - enable_tx

# shell prikazy
# raspi-gpio get 16 - vrati info, zda je pin de/re na vysilani nebo prijmu
# level=0,func=output,pull=down - spravne pro vysilani
# gpioset --mode=exit gpiochip=0 16=1 - nebo 16=0

# === GPIO nastavení ===
GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)
GPIO.setup(DE_RE_PIN, GPIO.OUT)
GPIO.output(DE_RE_PIN, GPIO.LOW)

def enable_tx():
    GPIO.output(DE_RE_PIN, GPIO.HIGH)

def enable_rx():
    GPIO.output(DE_RE_PIN, GPIO.LOW)

def sendMessage(registerAddress, value = ''):
    # Inicializace Modbus RTU klienta
    instrument = minimalmodbus.Instrument(PORT, SLAVE_ADDRESS)
    instrument.serial.baudrate = BAUDRATE
    instrument.serial.bytesize = 8
    instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
    instrument.serial.stopbits = 1
    instrument.serial.timeout = 0.5
    instrument.mode = minimalmodbus.MODE_RTU
    
    if(value == ''):
        enable_rx()
        regValue = instrument.read_register(registerAddress,functioncode=3)
        print(f"✅ Precteno: {regValue} z registru {registerAddress}")
    else:
        enable_tx()
        instrument.write_register(registerAddress, VALUE)
        print(f"✅ Zapsáno: {value} do registru {registerAddress}")
 
    
    # vzdy zapnu cteni po zpracovani prikazu
    enable_rx()

def sendWriteMessage(registerAddress, value):
    sendMessage(registerAddress, value)
    
def sendReadMessage(registerAddress):  
    sendMessage(registerAddress)  

# define control methods
def setAsTransmitter():
    sendWriteMessage(16419,0)
    
def setAsReciever():
    sendWriteMessage(16419,1)  

def reset():
    sendWriteMessage(31260,1)        

def getAddress():
    sendReadMessage(16389)
    
def startAudio():
    # set addresses
    sendWriteMessage(16432, 444444)     # druhy parametr je adresa
    # start playing
    sendWriteMessage(16437,2)
    # stop playing    
    time.sleep(10)                      # cekame nyni cca 10 sekund
    sendWriteMessage(16437,1)

try:

    getAddress()
    
    

except Exception as e:
    enable_rx()
    print("❌ Chyba při zápisu:", e)

finally:
    GPIO.cleanup()





# todo:
# pri startu je treba GPIO16 nastavit na 1
# vycist registr na prijimacich
# - register 4005 v HEX na prijimaci - vrati mi to 1 z adres na kterych reaguje na audio
# nasledne cisla ziskana vyse zapsat do vysilace na adresu/y 4030hex
# 3 pinovy audio kablik propojit s ustrednou
# dat si pozor na vysilace / prijimace - registr 4023 - 0 je vysilac, 1 je prijimac
# opticky, pokud to je dobre nastaveno, zelena kontrolka, ktera blika, bude blikat rychleji - na prijimaci
