#!/bin/bash

# Get configuration information from local system
software_path=$(realpath $(dirname $0)/..)
identity=$(cat $software_path/configuration/identity 2>/dev/null)
if [[ "$identity" == "" ]]; then identity="PQM-0"; fi
version=$(cat $software_path/VERSION 2>/dev/null)
if [[ "$version" == "" ]]; then version="Unknown"; fi
git_head=$(git rev-parse HEAD)
ip_address=$(hostname -I | cut -d ' ' -f 1)
mac_address=$(ip -oneline link | sed -rn 's/.+?wlp.+?ether ([a-f0-9:]+).*/\1/p')
user=$(whoami)

# Set directory for temporary files
for TD in "/run/shm/pqm-hellebores" "/tmp/pqm-hellebores" ""; do
    [[ -e $TD ]] || mkdir $TD
    if [[ $? -eq 0 ]]; then
        export TEMP=$TD
        break
    fi
done

# Format string for information box
read -r -d '' information << _EOF_
<tt><small>
Identity:             <b>$identity</b>
Software version:     <b>$version</b>
Git HEAD:             <b>$git_head</b>
IP address:           <b>$ip_address</b>
MAC address wlan:     <b>$mac_address</b>
Software path:        <b>$software_path</b>
Temporary files:      <b>$TEMP</b>
Connect remotely:     <b>ssh $user@$ip_address</b>
Download CSV data:    <b>scp $user@$ip_address:$TEMP/*csv .</b>
</small></tt>
_EOF_

# Run zenity app to display dialog box with buttons
result=$(zenity --info \
                --width=780 \
                --title 'Launcher: Power Quality Meter' \
                --text "$information" \
                --ok-label 'START' \
                --extra-button 'Exit' \
                --extra-button 'Software update' \
                --extra-button 'Pico update' \
                --extra-button 'Reboot' \
                --extra-button 'Shutdown')

# Process selected command, then relaunch the script
case "$result" in
    "Exit")
        exit 0;;
    "")
        echo "Starting PQM software."
        ../run/go.sh
        exec $0;;
    "Software update")
        git fetch origin
        git reset --hard origin/main
        exec $0;;
    *)
        echo $result
        exec $0;;
esac
