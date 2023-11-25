#!/bin/bash

# Create a script and store it in the variable $commands
# don't expand any variables until the time comes to run it.
read -r -d '' commands << '_EOF_' 
echo "Waiting 10 seconds to allow network to connect..."
sleep 10
clear

ip_address=$(hostname -I | cut -d ' ' -f 1)
user=$(whoami)
this_script=$(realpath $0)

echo "My IP address:
$ip_address

Connect to me remotely using:
ssh $user@$ip_address

Follow the configuration instructions to install software.
Disable this autorun script by deleting or renaming it.
This script is located at:
$this_script
"

# wait indefinitely
tail -f /dev/null
_EOF_

# Now run the commands in a new terminal window
if [[ -e /usr/bin/lxterminal ]]; then
    /usr/bin/lxterminal -t "REMOTE ACCESS FOR SETUP" -e "$commands"
elif [[ -e /usr/bin/gnome-terminal ]]; then
    /usr/bin/gnome-terminal -t "REMOTE ACCESS FOR SETUP" -- bash -c "$commands"
elif [[ -e /usr/bin/xterm ]]; then
    /usr/bin/xterm -title "REMOTE ACCESS FOR SETUP" -e "$commands"
fi

