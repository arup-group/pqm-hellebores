#!/bin/bash

# Figure out if we are running on real hardware or not
if [[ -e /dev/ttyACM0 ]]; then 
    have_pico=1
else
    have_pico=0
fi

# Change working directory to the directory of this script
DIRNAME=$(realpath $(dirname $0))
cd $DIRNAME

# Generate MD5 checksum of the program files and store it in environment variable
# The environment variables are accessible from within the application
# This allows us to reliably check if program versions on different devices are the same
MD5SUM=$(cat go.sh rain_bucket.py reader.py scaler.py trigger.py mapper.py \
             hellebores.py hellebores_constants.py hellebores_waveform.py \
             hellebores_multimeter.py ../pico/spi-dual-core.py | md5sum | cut -d ' ' -f 1)
VERSION=$(cat ../VERSION)
echo Running in $DIRNAME
echo Version $VERSION
echo MD5 checksum $MD5SUM

# If they don't already exist, create named pipes (fifos) to receive data from
# the waveform and calculation processes
for PIPE_FILE in waveform_stream calculation_stream; do
    if [[ ! -e $PIPE_FILE ]]; then
        mkfifo $PIPE_FILE
        if [[ $? -ne 0 ]]; then
            echo "There was an error creating a pipe file."
            echo "Check your filesystem supports this."
            exit 1
        fi
    fi
done

# Start the pipeline
# Waveform points are sent via standard output (fd 1) and
# calculation data is redirected via fd 3
if [[ $have_pico -eq 1 ]]; then
    echo "Running with data sourced from Pico..."
    ./reader.py | ./scaler.py \
    | tee >(./calculate.py &>3) \
    | ./trigger.py | ./mapper.py | ./hellebores.py
else
    echo "Running using generated data..."
    ./rain_bucket.py ../sample_files/laptop1.out | ./scaler.py \
    | tee >(./calculate.py &>3) \
    | ./trigger.py | ./mapper.py | ./hellebores.py
fi

# The program finished. NB All programs in the data pipeline
# terminate when the pipeline is broken

# Capture the exit code in case we need to do anything special
exit_code=$?

# Now check the exit code
# 2: Restart
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
    # drain fd 3 of data, and then close
    3</dev/ttyACM0
    while read -t 0 -u 3 discard; do echo "Flushing serial port..."; done
    exec 3>&-
    # Trampoline: reload the launch script and run again
    echo "Restarting $0..."
    exec $0

# 3: Software update
elif [[ $exit_code -eq 3 ]]; then
    clear
    echo "Updating software from repository..."
    git pull
    # Trampoline: reload the launch script and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    exec $0 

# 4: Shutdown
elif [[ $exit_code -eq 4 ]]; then
    echo "Shutting down system..."
    exec sudo shutdown -h now

# Some other exit code: We have no idea what happened
elif [[ $exit_code -ne 0 ]]; then
    echo "The program quit with an unexpected exit code $exit_code. Not good."
fi

# 0: Exit normally
echo "Exited."


