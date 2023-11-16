#!/bin/bash

sleep 10
ssid=$(iwgetid)
ip_address=$(hostname -I | cut -d ' ' -f 1)

echo My wifi network details:
echo $ssid
echo 
echo My IP address:
echo $ip_address
echo
echo Connect to me remotely using:
echo ssh $(whoami)@$ip_address
echo
echo Follow the configuration instructions to install software.
echo When finished, disable this bootstrap script by deleting or renaming it.
echo The script is located at:
echo $(realpath $0)



