#!/bin/bash

this_script=$(realpath $0)
version=$(../pqm/version.py)
ip_address='1.2.3.4'
user='pi'

read -r -d '' message << _EOF_
Remote: ssh $user@$ip_address

$version
_EOF_

selection="init"
selection=$(zenity --title="Power Quality Monitor Launcher" --width=500 --info --text="$message" --ok-label='Start' --extra-button='Software Update' --extra-button='Pico Update' --extra-button='Reboot' --extra-button='Shutdown' --extra-button='Quit')
if [[ "$?" == "1" && "$selection" == "" ]]; then
    selection="Cancel"
fi
case $selection in
    "")
	echo "Starting power quality monitor"
	;;
    "Start")
	echo "Starting PQM run script"
	;;
    "Software Update")
        echo "Updating software"
        ;;
    "Pico Update")
        echo "Updating Pico microcontroller"
        ;;
    "Reboot")
        echo "Rebooting system"
        ;;
    "Shutdown")
        echo "Shutting down system. WAIT for green light on rear of Pi to stop flashing BEFORE powering down"
        ;;
    "Cancel")
        echo "Cancelling"
	exit 1
        ;;	
    "Quit")
	echo "Quiting"
	exit 1
	;;
esac
exec $this_script

