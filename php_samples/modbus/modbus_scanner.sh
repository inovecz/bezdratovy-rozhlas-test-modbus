#!/bin/bash

PORT="/dev/ttyAMA3"
CHIP="gpiochip0"
PIN="16"
REGISTER="16438"  # 0x4036 = Status
LENGTH="0.5"
DELAY="0.05"  # pauza mezi přepínáním

# Seznam rychlostí, které chceme testovat
BAUDRATES=("9600" "19200" "38400" "57600" "115200")

# Seznam slave adres
SLAVES=$(seq 1 55)

echo "Začínám scan..."

for BAUD in "${BAUDRATES[@]}"; do
  echo "Testuji rychlost ${BAUD} baud"

  for SLAVE in $SLAVES; do
    echo -n "  Slave adresa $SLAVE... "

    # DE/RE do režimu vysílání
    gpioset --mode=exit $CHIP $PIN=1
    sleep $DELAY
    
    # Proveď čtení registru
    OUTPUT=$(timeout 2s mbpoll -m rtu -a $SLAVE -P none -s 1 -d 8 -b $BAUD -r $REGISTER $PORT 2>&1)
  #mbpoll -m rtu -b $BAUDRATE -P none -s 1 -d 8 -a $SLAVE_ADDR -r $REGISTER $MBPOLL_ARGS $PORT -- $VALUE
    # DE/RE zpět na příjem
    gpioset $CHIP $PIN=0

    # Zhodnocení výstupu
    if echo "$OUTPUT" | grep -q "Data"; then
      echo "✅ odpověď OK"
      echo "$OUTPUT" | grep "Data" | sed 's/^/      /'
    elif echo "$OUTPUT" | grep -q "Timed out"; then
      echo "❌ timeout"
    else
      echo "⚠️  jiná chyba"
      echo "$OUTPUT" | sed 's/^/      /'
    fi

    sleep 0.1
  done
done

echo "✅ Scan dokončen."
