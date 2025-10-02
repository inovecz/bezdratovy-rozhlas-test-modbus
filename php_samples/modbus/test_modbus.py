#!/bin/bash

# === Konfigurace ===
PORT="/dev/ttyAMA0"      # UART port
BAUD=9600                # Rychlost
PARITY="none"            # Parita (none, even, odd)
STOPBITS=1
DATABITS=8
SLAVE=55                 # Zjištěná adresa zařízení

# === Barvy ===
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# === Funkce ===
function test_read() {
  local reg=$1
  local name=$2
  local dec_reg=$((reg + 1))  # mbpoll používá 1-based adresaci

  echo -e "\n📥 Čtu registr ${name} (0x$(printf "%04X" $reg) = ${dec_reg})"
  mbpoll -1 -m rtu -b $BAUD -P $PARITY -s $STOPBITS -d $DATABITS -a $SLAVE -r $dec_reg $PORT
}

function test_write() {
  local reg=$1
  local val=$2
  local name=$3
  local dec_reg=$((reg + 1))

  echo -e "\n📤 Zápis do registru ${name} (0x$(printf "%04X" $reg) = ${dec_reg}) ← $val"
  mbpoll -1 -m rtu -b $BAUD -P $PARITY -s $STOPBITS -d $DATABITS -a $SLAVE -r $dec_reg -t 3:int -1 $val $PORT
}

# === Spuštění testů ===

echo -e "\n${GREEN}🧪 Testování Modbus zařízení na adrese $SLAVE přes port $PORT${NC}"

test_read 0x0000 "numAddrRam"
test_read 0x4003 "SlaveAddr"
test_read 0x4036 "Status"

test_write 0x5035 2 "TxControl (spustit vysílání)"

echo -e "\n${GREEN}✅ Hotovo. Sleduj LEDky / výstup / zařízení pro potvrzení aktivity.${NC}"
