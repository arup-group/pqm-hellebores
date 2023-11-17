#!/bin/bash

sleep 10

ip_address=$(hostname -I | cut -d ' ' -f 1)
user=$(whoami)
this_script=$(realpath $0)

message="My IP address:
$ip_address

Connect to me remotely using:
ssh $user@$ip_address

Follow the configuration instructions to install software.
Disable this bootstrap script by deleting or renaming it.
The script is located at:
$this_script
"

# display the output in a terminal window and wait indefinitely
lxterminal -t "REMOTE ACCESS FOR SETUP" -e "echo \"$message\"; tail -f /dev/null"

