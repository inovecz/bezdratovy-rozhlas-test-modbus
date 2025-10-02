for addr in {1..60}; do
	echo "zkousim $addr"
	sudo gpioset --mode=exit gpiochip0 16=1&
	sleep 0.05 
	mbpoll -m rtu -b 57600 -P none -s 1 -d 8 -a $addr -r 1 /dev/ttyAMA3 -1 -q && echo "Reagjuje adresa $addr"
	sudo pkill gpioset
	sleep 0.05
done
