#!/bin/bash

if [ -e /home/pi/pqm-hellebores/pi ]; then
    cd /home/pi/pqm-hellebores/pi
fi    
./get_identity.py | xcowsay
