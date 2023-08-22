#!/bin/bash

if [ -e /home/pi/pqm-hellebores/pi ]; then
    /home/pi/pqm-hellebores/pi/get_identity.py | xcowsay
else
    ./get_identity.py | xcowsay
fi
