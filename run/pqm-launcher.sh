#!/bin/bash

#                              _                        _                   _
#  _ __   __ _ _ __ ___       | | __ _ _   _ _ __   ___| |__   ___ _ __ ___| |__
# | '_ \ / _` | '_ ` _ \ _____| |/ _` | | | | '_ \ / __| '_ \ / _ \ '__/ __| '_ \
# | |_) | (_| | | | | | |_____| | (_| | |_| | | | | (__| | | |  __/ | _\__ \ | | |
# | .__/ \__, |_| |_| |_|     |_|\__,_|\__,_|_| |_|\___|_| |_|\___|_|(_)___/_| |_|
# |_|       |_|
#
#
# If we've just booted, wait for network connection to be established
if [[ $(cat /proc/uptime | cut -d '.' -f 1) -lt 60 ]]; then
    sleep 10
fi

# Repository options. If one repository is not available, provides option
# to switch to an alternative.
REPO_1="https://github.com/arup-group/pqm-hellebores.git"
REPO_2="https://github.com/adam4521/pqm-hellebores.git"

# Late Bookworm only
# Sends signal to on screen keyboard session
HIDE_KEYBOARD="gdbus call --session --dest sm.puri.OSK0 --object-path /sm/puri/OSK0 --method sm.puri.OSK0.SetVisible false"
SHOW_KEYBOARD="gdbus call --session --dest sm.puri.OSK0 --object-path /sm/puri/OSK0 --method sm.puri.OSK0.SetVisible true"

# Now get other configuration information from local system
# Get path information
CWD="$(pwd)"
SOFTWARE_PATH="$(realpath $(dirname $0)/..)"

# Network, identity and version information
IP_ADDRESS="$(hostname -I | cut -d ' ' -f 1)"
MAC_ADDRESS="$(ip -oneline link | sed -rn 's/.+?wl.+?ether ([a-f0-9:]+).*/\1/p')"
USER="$(whoami)"
IDENTITY="$(cat "$SOFTWARE_PATH/configuration/identity" 2>/dev/null || echo "PQM-0")"
VERSION="$(cat "$SOFTWARE_PATH/VERSION")"

# Repository information
# Change to home directory temporarily for git commands
cd "$SOFTWARE_PATH"
GIT_REMOTE="$(git remote get-url origin)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
GIT_HEAD="$(git rev-parse HEAD)"
# Revert working directory
cd "$CWD"

# Check for failure to retrieve a config value, and substitute 'Unknown' instead
# of empty string
for CF in VERSION GIT_HEAD IP_ADDRESS MAC_ADDRESS; do
    declare -n config_param="$CF"
    if [[ "$config_param" == "" ]]; then
        config_param="Unknown"
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



access_log() {
    zenity --text-info \
           --title="Power Quality Meter: error log" \
           --filename="$TEMP/error.log" \
           --ok-label "Copy to clipboard" \
           --width=600 --height=400
    clicked=$?
    if [[ $clicked -eq 0 ]]; then
        cat "$TEMP/error.log" | xclip -selection "clip"
    fi
}


fetch_from_repo() {
    # 1. Run commands in visible terminal window
    # $HIDE_KEYBOARD hides the wayland keyboard so that the terminal is
    # fully visible
    # Explicitly turn OFF pipefail so that our final manual 'exit \$STATUS'
    # is what controls the terminal's exit code, not the 'tee' pipeline tool.
    x-terminal-emulator -e bash -c "
        set +o pipefail

        {
            STATUS=0

            echo 'Updating software to Github branch origin/$GIT_BRANCH HEAD...'
            sleep 1
            $HIDE_KEYBOARD

            # Step A: Attempt to change directory
            cd '$SOFTWARE_PATH' || STATUS=1

            # Step B: Fetch updates
            git fetch origin || STATUS=1

            # Step C: Hard reset (Executes even if git fetch threw an error)
            git reset --hard origin/$GIT_BRANCH || STATUS=1

            sleep 2

            exit \$STATUS

        } 2>&1 | tee -a '$TEMP/error.log'

        exit \${PIPESTATUS[0]}
    "

    # 2. Check the exit status code of the terminal window
    if [ $? -ne 0 ]; then
        echo "Error: One or more steps failed during the software update process." >> $TEMP/error.log
        return 1
    fi

    return 0
}


pico_update() {
    # 1. Run commands in visible terminal window
    x-terminal-emulator -e bash -c "
        set +o pipefail

        {
            STATUS=0

            echo 'Updating software stored on Pico...'
            sleep 1
            $HIDE_KEYBOARD

            # Update Pico microcontroller
            $SOFTWARE_PATH/tools/pico_update.sh || STATUS=1
            sleep 2

            exit \$STATUS

         } 2>&1 | tee -a '$TEMP/update.log'

        exit \${PIPESTATUS[0]}
    "
    # 2. Check the exit status code of the terminal window
    if [ $? -ne 0 ]; then
        echo "Error: One or more steps failed during the Pico update process." >> $TEMP/error.log
        return 1
    fi

    return 0
}


software_update() {
    # DON'T run this option on a development computer
    # it will overwrite local changes and ruin your day
    # Save current working directory and restore on return
    local CWD="$(pwd)"
    cd "$SOFTWARE_PATH"
    while true; do
        GIT_REMOTE="$(git remote get-url origin)"
        text=$(echo "Upstream: $GIT_REMOTE \n\nIf you encounter issues, check \
internet connection is good and try updating again. If you determine that the repository \
is not available, use the 'Special...' option to switch remote. \n\nWAIT FOR REMOTE FETCH \
AND LOCAL UPDATE (PICO) TO COMPLETE." | fold -s -w 60)
        result=$(zenity --info \
                        --title "Power Quality Meter: software update" \
                        --text "$text" \
                        --ok-label "Cancel" \
                        --extra-button "Special..." \
                        --extra-button "UPDATE" \
                        --width=500)
        case "$result" in
            "UPDATE")
                if git ls-remote "$GIT_REMOTE" &> /dev/null; then
                    STATUS=0
                    fetch_from_repo || STATUS=1
                    pico_update || STATUS=1
                    if [[ $STATUS -eq 0 ]]; then
                        message="Update finished."
                    else
                        message="There were errors during the update."
                    fi
                else
                    message=$(echo "Repository $GIT_REMOTE wasn't reachable. No update took place." | fold -s -w 60)
                fi
                echo "$message" >> $TEMP/error.log
                zenity --info \
                       --title "Power Quality Meter: software update" \
                       --text "$message" \
                       --ok-label "OK" \
                       --width=200
                break;;
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
                                    --text="Select upstream Git repository"\
                                    --list \
                                    --column="Selection" --column="Upstream repository" $columns \
                                    --radiolist \
                                    --width=500 --height=300)
                case "$repository" in
                    "$REPO_1")
                        git remote set-url origin "$REPO_1"
                        echo "Upstream repository changed to $REPO_1" >> $TEMP/error.log;;
                    "$REPO_2")
                        git remote set-url origin "$REPO_2"
                        echo "Upstream repository changed to $REPO_2" >> $TEMP/error.log;;
                    *)
                        echo "Upstream repository $GIT_REMOTE unchanged." >> $TEMP/error.log;;
                esac;;
            *)
                # Returns to main menu
                break;;
        esac
        # Loops to software update menu
   done
   # Restore working directory
   cd "$CWD"
}

# Run zenity app to display dialog box with buttons
result=$(zenity --info \
                --title "Power Quality Meter: launcher" \
                --text "$information" \
                --ok-label "Shutdown" \
                --extra-button "Software update..." \
                --extra-button "View log..." \
                --extra-button "START" \
                --width=680)
# The primary/ok button does not return a value,
# so for clarity in the switch logic, we set one here
# and also catch the window cancel button
error_status=$?
if [[ "$result" == "" ]]; then
    if [[ $error_status -ne 0 ]]; then
        result="EXIT"
    else
        result="Shutdown"
    fi
fi

# Process selected command, exec $0 relaunches the script.
# For software update and Pico update, we launch a terminal so that we can
# monitor the progress and outcome.
case "$result" in
    "START")
        echo "Starting PQM software." >> $TEMP/error.log
        "$SOFTWARE_PATH/run/go.sh"
        exec "$0";;
    "EXIT")
        echo "Exiting launcher." >> $TEMP/error.log;;
    "Software update...")
        software_update
        exec "$0";;
    "View log...")
        access_log
        exec "$0";;
    "Shutdown")
        echo "Shutting down system." >> $TEMP/error.log
        sudo shutdown -h now;;
    *)
        echo "Not implemented: $result" >> $TEMP/error.log
        exec "$0";;
esac


exit 0
