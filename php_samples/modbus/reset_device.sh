#!/bin/bash

# === Konfigurace ===
PORT="/dev/ttyAMA3"
SLAVE_ADDR=3
BAUDRATE=9600
GPIO_CHIP="gpiochip0"
GPIO_PIN=16

# vstup
ACTION=$1
if [ -z "$ACTION" ]; then
	echo "Neni definovana akce. Pouzij modbus.sh reset napriklad"
	exit 1
fi

echo "Přepínám GPIO$GPIO_PIN do režimu VYSÍLÁNÍ (HIGH)..."
sudo gpioset --mode=exit $GPIO_CHIP $GPIO_PIN=1 &

# Počkáme na přepnutí
sleep 0.05

echo "Stav GPIO po akci:"
raspi-gpio get $GPIO_PIN



# ukazka resetu
REGISTER=20535
VALUE=2
echo "Odesílám požadavek na RESET do registru $REGISTER (hodnota $VALUE)..."
mbpoll -m rtu -b $BAUDRATE -P none -s 1 -d 8 -a $SLAVE_ADDR -r $REGISTER $PORT -- $VALUE

echo "Stav GPIO po akci:"
raspi-gpio get $GPIO_PIN

# Killneme přepínání GPIO
echo "Přepínám GPIO$GPIO_PIN zpět do PŘÍJMU (LOW)..."
sudo pkill gpioset
sleep 0.05
sudo gpioset --mode=exit $GPIO_CHIP $GPIO_PIN=0

echo "Stav GPIO po akci:"
raspi-gpio get $GPIO_PIN

echo "✅ Hotovo."
