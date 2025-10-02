#!/bin/bash

# === KONFIGURACE ===
PORT="/dev/ttyAMA3"        # UART port
SLAVE_ADDR=3               # Slave adresa, vysilac: 55, prijimac: 1
BAUDRATE=57600             # Baudrate, def: 57600
GPIO_CHIP="gpiochip0"
GPIO_PIN=16

# === VSTUP: AKCE ===
ACTION=$1  # např. ./modbus_action.sh reset

if [ -z "$ACTION" ]; then
  echo "❌ Chybí parametr akce! Použij např.: ./modbus_action.sh reset"
  exit 1
fi

# === PŘÍPRAVA PROMĚNNÝCH ===
REGISTER=""
VALUE=""
MBPOLL_ARGS=""

case "$ACTION" in
  reset)
    REGISTER=1638     # 0x0666
    VALUE=31260       # 0x7A1C
    MBPOLL_ARGS=""
    ;;

  hw_reset)
    REGISTER=1639     # 0x0667
    VALUE=31261       # 0x7A1D
    MBPOLL_ARGS=""
    ;;

  read_address)
    REGISTER=16387    # 0x4003
    MBPOLL_ARGS=""
    ;;

  read_mode)
    REGISTER=16419    # 0x4023
    MBPOLL_ARGS=""
    ;;

  read_status)
    REGISTER=16438    # 
    MBPOLL_ARGS=""
    ;;

    
  test_modbus_echo)
     REGISTER=0
     ;;

  test_modbus_mbpoll)
     REGISTER=0
     ;;

  *)
    echo "❌ Neznámá akce: $ACTION"
    echo "Dostupné akce: reset, hw_reset, read_address, read_mode"
    exit 1
    ;;
esac

# === FUNKCE ===
function log_gpio {
  echo "Stav GPIO$GPIO_PIN:"
  raspi-gpio get $GPIO_PIN
}

# === ZAČÁTEK ===
echo "=============================="
echo "MODBUS AKCE: $ACTION"
echo "Port: $PORT | Slave: $SLAVE_ADDR | Registr: $REGISTER"
echo "=============================="
log_gpio

# DE = HIGH
echo "DE=HIGH (vysílání)..."
sudo gpioset --mode=wait $GPIO_CHIP $GPIO_PIN=1 &
GPID=$!
sleep 0.05
log_gpio

# MBPOLL VOLÁNÍ
if [[ "$ACTION" == "test_modbus_echo" ]]; then
  echo "Echo zkusime zda vubec komunikace na portu jede"
  echo "aabbbbb" > /dev/ttyAMA3
elif [[ "$ACTION" == "test_modbus_mbpoll" ]]; then
  echo "MBPoll zkusime zda vubec modbus jede"
  # zde je baudrate 9600 coz je nastavene pro test i na macu
  mbpoll -m rtu -b 9600 -P none -s 1 -d 8 -a 1 -r 1200 /dev/ttyAMA3
elif [[ "$MBPOLL_ARGS" == *"--"* ]]; then
  echo "MBPoll: zápis hodnoty do registru..."
  mbpoll -m rtu -b $BAUDRATE -P none -s 1 -d 8 -a $SLAVE_ADDR -r $REGISTER $MBPOLL_ARGS $PORT -- $VALUE
else
  echo "MBPoll: čtení hodnoty z registru..."
  mbpoll -m rtu -b $BAUDRATE -P none -s 1 -d 8 -a $SLAVE_ADDR -r $REGISTER -c 1 $MBPOLL_ARGS $PORT
fi

# DE = LOW
echo "DE=LOW (příjem)..."
kill $GPID
sudo gpioset --mode=exit $GPIO_CHIP $GPIO_PIN=0

log_gpio
echo "✅ HOTOVO."
echo "=============================="
