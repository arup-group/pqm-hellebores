#!/bin/bash

if [ -e /dev/ttyACM0 ]; then 
    echo "Running with data sourced from Pico..."
    ./reader.py | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
else
    echo "Running using generated data..."
    ./rain.py | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
fi

