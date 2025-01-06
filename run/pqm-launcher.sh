#!/bin/bash

# Get path information
CWD=$(pwd)
SOFTWARE_PATH=$(realpath $(dirname $0)/..)

# Change to home directory for project, we'll change back on exit
cd $SOFTWARE_PATH

# If we've just booted, wait for network connection to be established
if [[ $(cat /proc/uptime | cut -d '.' -f 1) -lt 60 ]]; then
    sleep 10
fi

# Now get other configuration information from local system
IDENTITY=$(cat $SOFTWARE_PATH/configuration/identity 2>/dev/null)
if [[ "$IDENTITY" == "" ]]; then IDENTITY="PQM-0"; fi
VERSION=$(cat $SOFTWARE_PATH/VERSION)
GIT_HEAD=$(git rev-parse HEAD)
IP_ADDRESS=$(hostname -I | cut -d ' ' -f 1)
MAC_ADDRESS=$(ip -oneline link | sed -rn 's/.+?wlan0.+?ether ([a-f0-9:]+).*/\1/p')
USER=$(whoami)

# Check for failure to retrieve a config value, and substitute 'Unknown' instead
# of empty string
for CF in VERSION GIT_HEAD IP_ADDRESS MAC_ADDRESS; do
    declare -n config_param=$CF
    if [[ "$config_param" == "" ]]; then
        config_param=Unknown
    fi
done

# Set directory for temporary files
for TD in "/run/shm/pqm-hellebores" "/tmp/pqm-hellebores" "$SOFTWARE_PATH"; do
    [[ -e $TD ]] || mkdir $TD
    if [[ $? -eq 0 ]]; then
        export TEMP=$TD
        break
    fi
done

# Format string for information box
read -r -d '' information << _EOF_
<tt><small>
Identity:             <b>$IDENTITY</b>
Software version:     <b>$VERSION</b>
Git HEAD:             <b>$GIT_HEAD</b>
IP address:           <b>$IP_ADDRESS</b>
MAC address wlan:     <b>$MAC_ADDRESS</b>
Software path:        <b>$SOFTWARE_PATH</b>
Temporary files:      <b>$TEMP</b>
Connect remotely:     <b>ssh $USER@$IP_ADDRESS</b>
Download CSV data:    <b>scp $USER@$IP_ADDRESS:$TEMP/*csv .</b>
</small></tt>
_EOF_

# Run zenity app to display dialog box with buttons
result=$(zenity --info \
                --width=680 \
                --title "Launcher: Power Quality Meter" \
                --text "$information" \
                --ok-label "START" \
                --extra-button "Software update" \
                --extra-button "Pico update" \
                --extra-button "Shutdown")

# The primary/ok button does not return a value,
# so for clarity in the switch logic, we set one here
# and also catch the window cancel button
error_status=$?
if [[ "$result" == "" ]]; then
    if [[ $error_status -ne 0 ]]; then
        result="EXIT"
    else
        result="START"
    fi
fi

# Process selected command, exec $0 relaunches the script
case "$result" in
    "START")
        echo "Starting PQM software."
        $SOFTWARE_PATH/run/go.sh
        exec $0;;
    "EXIT")
        echo "Exiting launcher.";;
    "Software update")
        echo "Updating software."
        git fetch origin
        git reset --hard origin/main
        exec $0;;
    "Pico update")
        echo "Pico update not implemented."
        exec $0;;
    "Shutdown")
        echo "Shutting down system."
        sudo shutdown -h now;;
    *)
        echo "Not implemented: $result"
        exec $0;;
esac

cd $CWD
exit 0
