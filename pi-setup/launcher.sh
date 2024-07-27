#!/bin/bash


configuration=$(cd ../pqm; python -c 'import settings; s=settings.Settings(); print(f"{s.identity}_{s.cal_offsets}_{s.cal_gains}")' 2>/dev/null)
identity=$(echo $configuration | cut -d "_" -f 1)
cal_offsets=$(echo $configuration | cut -d "_" -f 2)
cal_gains=$(echo $configuration | cut -d "_" -f 3)
ip_address=$(hostname -I | cut -d ' ' -f 1)
mac_address=$(ip link | sed -rn 's/.+?ether ([a-f0-9:]+).*/\1/p')
user=$(whoami)
software_path=$(realpath $(dirname $0)/..)

read -r -d '' information << _EOF_
<tt><big>
Identity:                <b>$identity</b>
Calibration offsets:      <b>$cal_offsets</b>
Calibration gains:       <b>$cal_gains</b>
IP address:              <b>$ip_address</b>
MAC address ether:       <b>$mac_address</b>
Connect remotely:        <b>ssh $user@$ip_address</b>
Software path:           <b>$software_path</b>
</big></tt>
_EOF_


result=$(zenity --info --width=500 \
                       --title 'Power Quality Meter' \
                       --text "$information" \
                       --ok-label Start \
                       --extra-button 'Software update' \
                       --extra-button 'Pico update' \
                       --extra-button Restart \
                       --extra-button Shutdown)

echo $result
if [[ $result != '' ]]; then
    exec $0
else
    echo Exited.
fi
