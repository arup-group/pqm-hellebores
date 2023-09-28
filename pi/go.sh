#!/bin/bash

# Figure out if we are running on real hardware or not
if [[ -e /dev/ttyACM0 ]]; then 
    have_pico=1
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
# Restart
if [[ $exit_code -eq 2 ]]; then
    # Pico not recovering from this step!
    #if [[ $have_pico -eq 1 ]]; then
    #    # Reset the Pico
    #    echo "Resetting Pico..."
    #    ./pico_reset.py
    #    sleep 10
    #fi
    # Flush serial interface
    # open the serial port for reading on file descriptor 3
    # drain it of data and then close
    3</dev/ttyACM0
    while read -t 0 -u 3 discard; do echo "Flushing serial port..."; done
    exec 3>&-
    # Trampoline: reload the launch script and run again
    echo "Restarting $0..."
    exec $0

# Software update
elif [[ $exit_code -eq 3 ]]; then
    clear
    echo "Updating software from repository..."
    git pull
    # Trampoline: reload the launch script and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    exec $0 

# Shutdown
elif [[ $exit_code -eq 4 ]]; then
    echo "Shutting down system..."
    exec sudo shutdown -h now

# We have no idea what happened
elif [[ $exit_code -ne 0 ]]; then
    echo "The program quit with an unexpected exit code $exit_code. Not good."
fi

echo "Exited."


