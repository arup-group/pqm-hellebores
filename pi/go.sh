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

WAVEFORM_PIPE=/tmp/pqm-hellebores/waveform_pipe
ANALYSIS_PIPE=/tmp/pqm-hellebores/analysis_pipe
ERROR_LOG_FILE=/tmp/pqm-hellebores/error.log

# If they don't already exist, create named pipes (fifos) to receive data from
# the waveform and calculation processes
for PIPE_FILE in $WAVEFORM_PIPE $ANALYSIS_PIPE; do
    if [[ ! -e $PIPE_FILE ]]; then
        mkfifo $PIPE_FILE
        if [[ $? -ne 0 ]]; then
            echo "There was an error creating a pipe file."
            echo "Check your filesystem supports this."
            exit 1
        fi
    fi
done

# Start the data pipeline, output feeding the two named pipes
# Clear old log file
rm $ERROR_LOG_FILE
# Duplicate stderr file descriptor 2 to 4
# then redirect 2 to file
exec 4>&2 2>$ERROR_LOG_FILE

if [[ $have_pico -eq 1 ]]; then
    echo "Running with data sourced from Pico..."
    READER="./reader.py"
else
    echo "Running using previously captured data..."
    READER="./rain_bucket.py ../sample_files/laptop1.out"
fi

# Run the capture and analysis, feeding two pipe files,
# passing both pipes as parameters to the GUI
$READER \
| ./scaler.py \
| tee >(./analyser.py > $ANALYSIS_PIPE) \
| ./trigger.py | ./mapper.py > $WAVEFORM_PIPE &

./hellebores.py $WAVEFORM_PIPE $ANALYSIS_PIPE

# The program finished. NB Programs in the data pipeline all
# terminate when the pipeline is broken

# Capture the exit code from hellebores.py
# We'll check it's status shortly
exit_code=$?

# Restore stderr file descriptor 2 from saved state on 4
exec 2>&4 4>&-

# Now check the exit code from hellebores.py
# 2: Restart
if [[ $exit_code -eq 2 ]]; then
    # Flush serial interface
    # open the serial port for reading on a new file descriptor,
    # drain of data, and then close
    if [[ $have_pico -eq 1 ]]; then
        exec 5</dev/ttyACM0
        while read -t 0 -u 11 discard; do echo "Flushing serial port..."; done
        exec 5>&-
    fi
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
    echo "Here's the error log file $ERROR_LOG_FILE, hope it helps:"
    cat $ERROR_LOG_FILE
    sleep 60
    exit $exit_code
fi

# 0: Exit normally
echo "Exited."


