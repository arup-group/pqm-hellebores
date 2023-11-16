#!/bin/bash

# Change working directory to the directory of this script
PROGRAM_DIR=$(realpath $(dirname $0))
cd $PROGRAM_DIR

# Generate MD5 checksum of the program files and store it in environment variable
# The environment variables are accessible from within the application
# This allows us to reliably check if program versions on different PQMs are the same
export MD5SUM=$(cat go.sh rain_bucket.py reader.py scaler.py trigger.py mapper.py \
                hellebores.py hellebores_constants.py hellebores_waveform.py \
                hellebores_multimeter.py ../pico/spi-dual-core.py | md5sum | cut -d ' ' -f 1)
export VERSION=$(cat ../VERSION)

# TEMP_DIR: settings.json, error.log and named pipes will be stored here
# /run/shm is preferred, because it is mounted as RAM disk
for TD in "/run/shm/pqm-hellebores" "/tmp/pqm-hellebores"; do
    [[ -e $TD ]] || mkdir $TD
    if [[ $? -eq 0 ]]; then
        export TEMP_DIR=$TD
        break
    fi
done
# if both attempts failed, quit with an error
if [[ -z $TEMP_DIR ]]; then
    echo "Check filesystem or write permissions, quitting."
    exit 1
fi

# set up the working files
WAVEFORM_PIPE=$TEMP_DIR/waveform_pipe
ANALYSIS_PIPE=$TEMP_DIR/analysis_pipe
MEASUREMENT_LOG_FILE=$TEMP_DIR/pqm.$$.csv
ERROR_LOG_FILE=$TEMP_DIR/error.log


# If they don't already exist, create named pipes (fifos) to receive data from
# the waveform and calculation processes
for PIPE_FILE in $WAVEFORM_PIPE $ANALYSIS_PIPE; do
    [[ -e $PIPE_FILE ]] || mkfifo $PIPE_FILE
    if [[ $? -ne 0 ]]; then
        echo "There was an error creating a pipe file."
        echo "Check your filesystem supports this."
        exit 1
    fi
done

# Figure out if we are running on real hardware or not
if [[ -e /dev/ttyACM0 ]]; then
    have_pico=true
    READER="./reader.py"
else
    have_pico=false
    READER="./rain_bucket.py ../sample_files/simulated.out"
fi

echo "Working directory    : $PROGRAM_DIR"
echo "Temporary files      : $TEMP_DIR"
echo "Version              : $VERSION"
echo "MD5 checksum         : $MD5SUM"
echo "Measurement data     : $READER"

# Start the data pipeline, output feeding the two named pipes
# Clear old log file
[[ -e $ERROR_LOG_FILE ]] && rm $ERROR_LOG_FILE
# Duplicate stderr file descriptor 2 to 4
# then redirect 2 to file
exec 4>&2 2>$ERROR_LOG_FILE

# Run the capture and analysis, feeding two pipe files,
# then pass both pipes as parameters to the GUI
echo "Starting processing..."

# Plumbing, pipe, pipe, pipe...
$READER \
    | ./scaler.py \
        | tee >(./analyser.py | tee $MEASUREMENT_LOG_FILE > $ANALYSIS_PIPE) \
            | ./trigger.py \
                | ./mapper.py \
                    > $WAVEFORM_PIPE &

./hellebores.py $WAVEFORM_PIPE $ANALYSIS_PIPE

# Capture the exit code from hellebores.py
# We'll check it's status shortly
exit_code=$?

echo "Finished processing."

# Restore stderr file descriptor 2 from saved state on 4
exec 2>&4 4>&-

# Now check the exit code
# 2: Restart
if [[ $exit_code -eq 2 ]]; then
    # Flush serial interface
    # open the serial port for reading on a new file descriptor,
    # drain of data, and then close
    if $have_pico; then
        exec 5</dev/ttyACM0
        while read -t 0 -u 5 discard; do echo "Flushing serial port..."; done
        exec 5>&-
    fi
    # Trampoline: reload the launch script (this file) and run again
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
    echo "Here's the error log file $ERROR_LOG_FILE, hope it helps :-)"
    cat $ERROR_LOG_FILE
    sleep 60
    exit $exit_code
fi

# 0: Exit normally
echo "Exited."


