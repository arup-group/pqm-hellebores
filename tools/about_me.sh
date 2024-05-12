#!/bin/bash

ip_address=$(hostname -I | cut -d ' ' -f 1)
user=$(whoami)
software_dir=$(realpath $(dirname $0)/..)
identity=[[$(tr -d '\n' < $software_dir/configuration/identity) || 'not defined']]

read -r -d '' message << _EOF_
My IP address:
$ip_address

Connect to me remotely using:
ssh $user@$ip_address

My identity:
$identity

This script is located at:
$(realpath $0)
_EOF_

zenity --title="ABOUT POWER QUALITY METER" --width=500 --info --text="$message"


