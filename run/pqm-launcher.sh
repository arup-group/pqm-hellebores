#!/bin/bash

# Get path information
CWD="$(pwd)"
SOFTWARE_PATH="$(realpath $(dirname $0)/..)"

# Change to home directory for project, we'll change back on exit
cd "$SOFTWARE_PATH"

# If we've just booted, wait for network connection to be established
if [[ $(cat /proc/uptime | cut -d '.' -f 1) -lt 60 ]]; then
    sleep 10
fi

# Repository options. If one repository is not available, provides option
# to switch to an alternative.
REPO_1='https://github.com/arup-group/pqm-hellebores.git'
REPO_2='https://github.com/adam4521/pqm-hellebores.git'

# Now get other configuration information from local system
IDENTITY="$(cat $SOFTWARE_PATH/configuration/identity 2>/dev/null)"
if [[ "$IDENTITY" == "" ]]; then IDENTITY="PQM-0"; fi
VERSION="$(cat $SOFTWARE_PATH/VERSION)"
GIT_REMOTE="$(git remote get-url origin)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
GIT_HEAD="$(git rev-parse HEAD)"
IP_ADDRESS="$(hostname -I | cut -d ' ' -f 1)"
MAC_ADDRESS="$(ip -oneline link | sed -rn 's/.+?wlan0.+?ether ([a-f0-9:]+).*/\1/p')"
USER="$(whoami)"

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
    [[ -e "$TD" ]] || mkdir "$TD"
    if [[ $? -eq 0 ]]; then
        export TEMP="$TD"
        break
    fi
done

# Format string for information box
read -r -d '' information << _EOF_
<tt><small>
Identity:             <b>$IDENTITY</b>
Software version:     <b>$VERSION</b>
Git remote:           <b>$GIT_REMOTE</b>
Git branch:           <b>$GIT_BRANCH</b>
Git HEAD:             <b>$GIT_HEAD</b>
IP address:           <b>$IP_ADDRESS</b>
MAC address wlan:     <b>$MAC_ADDRESS</b>
Software path:        <b>$SOFTWARE_PATH</b>
Temporary files:      <b>$TEMP</b>
Connect remotely:     <b>ssh $USER@$IP_ADDRESS</b>
Download CSV data:    <b>scp $USER@$IP_ADDRESS:$TEMP/*csv .</b>
</small></tt>
_EOF_


# Late Bookworm only
HIDE_KEYBOARD="gdbus call --session --dest sm.puri.OSK0 --object-path /sm/puri/OSK0 --method sm.puri.OSK0.SetVisible false"
SHOW_KEYBOARD="gdbus call --session --dest sm.puri.OSK0 --object-path /sm/puri/OSK0 --method sm.puri.OSK0.SetVisible true"


access_logs() {
    result=$(zenity --info \
                    --title "Power Quality Meter: access logs" \
                    --width=500 --height=200 \
                    --text "Software logs will open in a text editor. Logs are cached in RAMdisk \
and don't persist across a reboot or power cycle." \
                    --ok-label "Cancel" \
                    --extra-button "Software update log" \
                    --extra-button "Error log")
    case "$result" in
        "Error log")
            xdg-open "$TEMP/error.log" & $HIDE_KEYBOARD;;
        "Software update log")
            xdg-open "$TEMP/update.log" & $HIDE_KEYBOARD;;
        *)
            echo "Returning to main menu.";;
    esac
}


fetch_from_repo() {
    # pkill -USR1 wvkbd hides the wayland keyboard so that the termrinal is
    # fully visible
    x-terminal-emulator -e bash -c "
        {
            echo 'Updating software to Github branch origin/$GIT_BRANCH HEAD...'
            $HIDE_KEYBOARD
            cd $SOFTWARE_PATH
            git fetch origin
            git reset --hard origin/$GIT_BRANCH
            sleep 2
        } 2>&1 | tee -a '$TEMP/update.log'
    "
}


pico_update() {
    x-terminal-emulator -e bash -c "
        {
            echo 'Updating software stored on Pico...'
            $HIDE_KEYBOARD
            $SOFTWARE_PATH/tools/pico_update.sh
            sleep 2
        } 2>&1 | tee -a '$TEMP/update.log'
    "
}


software_update() {
    # DON'T run this option on a development computer
    # it will overwrite local changes and ruin your day
    result=$(zenity --info \
                    --title "Power Quality Meter: software update" \
                    --width=500 --height=200 \
                    --text "Upstream: $GIT_REMOTE\n\nIf you encounter issues, check \
internet connection is good and try updating again. If you determine that the repository \
is not available, use the 'Special...' option to switch remote.\n\nWAIT FOR REMOTE FETCH \
AND LOCAL UPDATE (PICO) TO COMPLETE." \
                    --ok-label "Cancel" \
                    --extra-button "Special..." \
                    --extra-button "UPDATE")
    case "$result" in
        "UPDATE")
            if git ls-remote "$GIT_REMOTE" &> /dev/null; then
                fetch_from_repo; pico_update
                message="Update finished."
            else
                message="Repository $GIT_REMOTE wasn't reachable. No update took place."
            fi
            zenity --info \
                   --title "Power Quality Meter: software update" \
                   --width=500 --height=200 \
                   --text "$message" \
                   --ok-label "OK";;
        "Special...")
            case $GIT_REMOTE in
                "$REPO_1")
                    columns="TRUE $REPO_1 FALSE $REPO_2";;
                "$REPO_2")
                    columns="FALSE $REPO_1 TRUE $REPO_2";;
                *)
                    columns="FALSE $REPO_1 FALSE $REPO_2";;
            esac
            repository=$(zenity --title="Special" \
                                --width=500 --height=200 \
                                --list --text='Select upstream Git repository'\
                                --column='Selection' --column='Upstream repository' $columns \
                                --radiolist)
            case "$repository" in
                "$REPO_1")
                    git remote set-url origin "$REPO_1"
                    echo "Upstream repository changed to $REPO_1";;
                "$REPO_2")
                    git remote set-url origin "$REPO_2"
                    echo "Upstream repository changed to $REPO_2";;
                *)
                    echo "Upstream repository $GIT_REMOTE unchanged.";;
            esac
            echo "Returning to main menu.";;
        *)
            echo "Returning to main menu.";;
    esac
}

# Run zenity app to display dialog box with buttons
result=$(zenity --info \
                --title "Power Quality Meter: Launcher" \
                --width=680 \
                --text "$information" \
                --ok-label "START" \
                --extra-button "Software update..." \
                --extra-button "Logs..." \
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

# Process selected command, exec $0 relaunches the script.
# For software update and Pico update, we launch a terminal so that we can
# monitor the progress and outcome.
cd "$CWD"
case "$result" in
    "START")
        echo "Starting PQM software."
        "$SOFTWARE_PATH/run/go.sh"
        exec "$0";;
    "EXIT")
        echo "Exiting launcher.";;
    "Software update...")
        software_update
        exec "$0";;
    "Logs...")
        access_logs
        exec "$0";;
    "Shutdown")
        echo "Shutting down system."
        sudo shutdown -h now;;
    *)
        echo "Not implemented: $result"
        exec "$0";;
esac


exit 0
