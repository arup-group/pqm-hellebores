#!/bin/bash

# Figure out if we are running on real hardware or not
# if we are, we disable the getty service for the serial port
# as this can sometimes (infrequently) interfere with the communications
if [[ -e /dev/ttyACM0 ]]; then 
    have_pico=1
    sudo systemctl stop serial-getty@USB0.service
else
    have_pico=0
fi

# Run the program
if [[ $have_pico -eq 1 ]]; then
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
if [[ $exit_code -eq 2 ]]; then
    # Pico not recovering from this step!
    #if [[ $have_pico -eq 1 ]]; then
    #    # Reset the Pico
    #    echo "Resetting Pico..."
    #    ./pico_reset.py
    #    sleep 10
    #fi
    # Flush serial interface
    # open the serial port for reading on file descriptor 2
    # and then empty it
    2</dev/ttyACM0
    while read -t 0 -u 2 discard; do echo "Flushing serial port..."; done
    # Trampoline: reload the current script and run again
    echo "Restarting $0..."
    exec $0

elif [[ $exit_code -eq 3 ]]; then
    # Update software and restart the app
    echo "Updating software from repository..."
    git pull
    # Trampoline: reload the current script and run again
    echo "Restarting $0..."
    exec $0 

elif [[ $exit_code -eq 4 ]]; then
    # Shut down system
    echo "Shutting down system..."
    exec sudo shutdown -h now

elif [[ $exit_code -ne 0 ]]; then
    # We have no idea what happened
    echo "The program quit with an unexpected exit code $exit_code. Not good."
fi

echo "Exited."


