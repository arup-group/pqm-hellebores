#!/bin/bash

if [ -e /dev/ttyACM0 ]; then 
    echo "Running with data sourced from Pico..."
    cd /home/pi/pqm-hellebores/pi
    ./reader.py | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
else
    echo "Running using generated data..."
    ./rain_bucket.py laptop1.out | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
fi

