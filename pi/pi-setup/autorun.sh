#!/bin/bash

sleep 10

ip_address=$(hostname -I | cut -d ' ' -f 1)
user=$(whoami)

read -r -d '' message << _EOF_
My IP address:
$ip_address

Connect to me remotely using:
ssh $user@$ip_address

Follow the configuration instructions to install software.
Disable this autorun script by deleting or renaming it.

This script is located at:
$(realpath $0)
_EOF_

zenity --title="REMOTE ACCESS FOR SETUP" --width=500 --info --text="$message"


