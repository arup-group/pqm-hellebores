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
REPO_1="git@github.com:arup-group/pqm-hellebores.git"
REPO_2="git@github.com:adam4521/pqm-hellebores.git"

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

pico_update() {
    x-terminal-emulator -e \
        "echo 'Updating software stored on Pico...'; \
        $SOFTWARE_PATH/tools/pico_update.sh; \
        sleep 5"
    exec "$0"
}

software_update() {
    # DON'T run this option on a development computer
    # it will overwrite local changes and ruin your day
    result=$(zenity --info \
        --title "Power Quality Meter: software update" \
        --text "The updater will check to see if $GIT_REMOTE is reachable. If you \
encounter issues, check internet connection is good and try updating again. If the repository \
is not available, you can try to 'switch remote'..." \
        --ok-label "Software update" \
        --extra-button "Switch remote")

    error_status=$?
    if [[ "$result" == "" ]]; then
        if [[ $error_status -ne 0 ]]; then
            result="EXIT"
        else
            result="UPDATE"
        fi
    fi

    case "$result" in
        "EXIT")
            echo "Exiting launcher.";;
        "UPDATE")
            if git ls-remote "$GIT_REMOTE" &> /dev/null; then
                x-terminal-emulator -e \
                    "echo 'Updating software to Github branch origin/$GIT_BRANCH HEAD...'; \
                    cd $SOFTWARE_PATH; \
                    git fetch origin; \
                    git reset --hard origin/$GIT_BRANCH; \
                    sleep 5"
            else
                zenity --info \
                    --title "Power Quality Meter: software update" \
                    --text "Repository $GIT_REMOTE is not reachable. No update took place." \
                    --ok-label "OK"
            fi
            exec "$0";;
        "Switch remote")
            if [[ "$GIT_REMOTE" == "$REPO_1" ]]; then
                git remote set-url origin "$REPO_2"
            elif [[ "$GIT_REMOTE" == "$REPO_2" ]]; then
                git remote set-url origin "$REPO_1"
            fi
            exec "$0";;
    esac
}

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
    "Software update")
        software_update;;
    "Pico update")
        pico_update;;
    "Shutdown")
        echo "Shutting down system."
        sudo shutdown -h now;;
    *)
        echo "Not implemented: $result"
        exec "$0";;
esac


exit 0
