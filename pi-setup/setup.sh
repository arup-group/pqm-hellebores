#!/bin/bash

# Copyright 2024 Arup
# MIT License
#
#
#          _                    _     
# ___  ___| |_ _   _ _ __   ___| |__  
#/ __|/ _ \ __| | | | '_ \ / __| '_ \ 
#\__ \  __/ |_| |_| | |_) |\__ \ | | |
#|___/\___|\__|\__,_| .__(_)___/_| |_|
#                   |_|               
#
# Setup of pqm-hellebores and dependencies on Raspberry Pi systems
#


detect_installation_directory () {
    SCRIPT_DIR=$(realpath $(dirname $0))
    INSTALLATION_DIR=$(realpath $SCRIPT_DIR/../)
}


create_venv_with_dependencies () {
    cd $INSTALLATION_DIR &&
    python3 -m venv venv &&
    source venv/bin/activate &&
    python3 -m pip install -r requirements.txt &&
    deactivate
    if [[ "$?" != "0" ]]; then
        echo "Failed in create_venv_with_dependencies"
    fi
}

set_identity () {
    # NB pass in a parameter with the required identity
    echo "$1" > $INSTALLATION_DIR/configuration/identity &&
    hostnamectl set-hostname $1
    if [[ "$?" != "0" ]]; then
        echo "Failed in set_identity"
    fi
}

install_blueman () {
    yes | sudo apt install blueman
    if [[ "$?" != "0" ]]; then
        echo "Failed in install_blueman"
    fi
} 

create_shortcuts () {
    cd $INSTALLATION_DIR &&
    cp ./pi-setup/find-me.desktop /home/pi/.local/share/applications &&
    cp ./pi-setup/hellebores.desktop /home/pi/.local/share/applications
    if [[ "$?" != "0" ]]; then
        echo "Failed in create_shortcuts"
    fi
}

add_autostart () {
    cd $INSTALLATION_DIR &&
    cp ./pi-setup/pqm.desktop /home/pi/.config/autostart
    if [[ "$?" != "0" ]]; then
        echo "Failed in add_autostart"
    fi
}


hostname=`hostname`
echo "About to set up pqm-hellebores on $hostname."
echo "*******************************************************************"
echo "NB This script must be run with elevated permissions,"
echo "eg sudo $0, to complete some configuration tasks."
echo "*******************************************************************"
echo ""
echo "This script will perform the following steps:"
echo "1. Work out the pqm-hellebores installation directory relative to"
echo "the location of this file."
echo "2. Create a virtual environment and install the dependencies."
echo "3. Set the device identity and hostname."
echo "4. Install the blueman bluetooth file manager client."
echo "5. Add shortcuts to the pi desktop menu."
echo "6. Add the launcher to the desktop autostart folder."
echo ""
read -p "Press 'y' to continue, or another key to exit. " decision

if [[ "$decision" == "y" ]]; then
    read -p "Enter desired identity of the device (eg PQM-1): " identity
    echo "Starting installation, look out for error messages that"
    echo "indicate an incomplete installation."
    echo "1. Detect installation directory."
    detect_installation_directory
    echo "Setting up using $INSTALLATION_DIR, NB wait to complete..."
    echo "2. Creating virtual environment with dependencies."
    create_venv_with_dependencies
    echo "3. Setting identity."
    set_identity $identity
    echo "4. Installing the bluetooth file manager client."
    install_blueman
    echo "5. Creating menu shortcuts."
    create_shortcuts
    echo "6. Adding entry to autostart directory."
    add_autostart
    echo "Completed installation script."
else
    echo "Quitting without doing anything."
fi


