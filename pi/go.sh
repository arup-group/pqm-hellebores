#!/bin/bash

# Run the program
if [ -e /dev/ttyACM0 ]; then 
    echo "Running with data sourced from Pico..."
    cd /home/pi/pqm-hellebores/pi
    ./reader.py | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
else
    echo "Running using generated data..."
    ./rain_bucket.py laptop1.out | ./scaler.py | ./trigger.py | ./mapper.py | ./hellebores.py
fi

# The program finished.
# Now check the exit code in case we need to do anything
exit_code=$?
if [ $exit_code -eq 2 ]; then
    # Reset the Pico and restart the app
    echo "Resetting Pico..."
    ./pico_reset.py
    echo "Restarting $0..."
    exec $0
elif [ $exit_code -eq 3 ]; then
    # Update software and restart the app
    echo "Updating software from repository..."
    git pull
    echo "Restarting $0..."
    exec $0 
elif [ $exit_code -eq 4 ]; then
    # Shut down system
    echo "Shutting down system..."
    exec sudo shutdown -h now
elif [ $exit_code -ne 0 ]; then
    # We have no idea what happened
    echo "The program quit with an unexpected exit code $exit_code. Not good."
fi

echo "Exited."


