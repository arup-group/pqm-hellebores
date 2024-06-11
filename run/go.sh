#!/bin/bash

# Find current working directory and absolute paths of script and program file directories
CWD=$(pwd)
SCRIPT_DIR=$(realpath $(dirname $0))
PROGRAM_DIR=$(realpath $SCRIPT_DIR/../pqm)

# Change to the program directory
cd $PROGRAM_DIR

# Activate the virtual environment, if we have one
if [[ -e $SCRIPT_DIR/../venv ]]; then
    source $SCRIPT_DIR/../venv/bin/activate
fi

# Figure out if we are running on real hardware or not
grep --ignore-case raspberry '/sys/firmware/devicetree/base/model' &> /dev/null
if [[ $? -eq 0 ]]; then
    real_hardware=true
    READER="./reader.py"
else
    real_hardware=false
    READER="./rain_chooser.py"
fi

# TEMP: settings.json, error.log and named pipes will be stored here
# /run/shm is preferred, because it is mounted as RAM disk
for TD in "/run/shm/pqm-hellebores" "/tmp/pqm-hellebores"; do
    [[ -e $TD ]] || mkdir $TD
    if [[ $? -eq 0 ]]; then
        export TEMP=$TD
        break
    fi
done
# if both attempts failed, quit with an error
if [[ -z $TEMP ]]; then
    echo "Check filesystem or write permissions, quitting."
    exit 1
fi

# set up the working files
# NB the special variable $$ contains the PID of the current process
WAVEFORM_PIPE=$TEMP/waveform_pipe
ANALYSIS_PIPE=$TEMP/analysis_pipe
MEASUREMENT_LOG_FILE=$TEMP/pqm.$$.csv
ERROR_LOG_FILE=$TEMP/error.log


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


# Start the data pipeline, output feeding the two named pipes
# Clear old log file
[[ -e $ERROR_LOG_FILE ]] && rm $ERROR_LOG_FILE
# Duplicate stderr file descriptor 2 to 4
# then redirect 2 to file
exec 4>&2 2>$ERROR_LOG_FILE

# Display the version infomation and settings that will be used initially
./version.py
./settings.py

# Run the capture and analysis, feeding two pipe files,
# then pass both pipes as parameters to the GUI
echo "Starting processing..."
echo "Measurement source: $READER"

####
# This is where we actually start the programs
# The incoming data is split (using 'tee') into two pipelines that feed analysis and waveform
# processes simultaneously.
# Note that the analysis pipeline is further split by another instance of tee so that analysis
# results are stored in a file as well as sent onwards, via $ANALYSIS_PIPE, to hellebores.py
# hellebores.py reads both $WAVEFORM_PIPE and $ANALYSIS_PIPE all the time, to keep the
# pipelines moving.
####

# Reset the Pico, flush out serial buffer that may be in an inconsistent state and start streaming.
if $real_hardware; then
    ./pico_control.py --command "CAT main.py" --hard_reset > /dev/null
    ./pico_control.py --command "START stream.py 1x 1x 1x 1x 7.812k" --no_response
fi

# analyser.py needs to run with an increased input pipe buffer, to avoid stalling the sample
# stream while doing calculations.
#ANALYSER="stdbuf --input=4M nice --adjustment=10 ./analyser.py"
ANALYSER="./analyser.py"

# Plumbing, pipe, pipe, pipe...
$READER \
    | ./scaler.py \
        | tee >($ANALYSER | tee $MEASUREMENT_LOG_FILE > $ANALYSIS_PIPE) \
            | ./trigger.py | ./mapper.py > $WAVEFORM_PIPE &

./hellebores.py $WAVEFORM_PIPE $ANALYSIS_PIPE
# Because hellebores.py is running in the foreground, this script blocks (waits) until it finishes.
# The reader, scaler, analysis and waveform programs also terminate at that point because their
# pipeline connections are broken/closed.

# Capture the exit code from hellebores.py
# We'll check it's status shortly
exit_code=$?

echo "Finished processing."

# Restore stderr file descriptor 2 from saved state on 4, and delete fd 4
exec 2>&4 4>&-

# Now check the exit code
# 2: Restart
if [[ $exit_code -eq 2 ]]; then
    # Trampoline: reload the launch script (this file) and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    cd $CWD
    exec $0

# 3: Software update
elif [[ $exit_code -eq 3 ]]; then
    clear
    echo "Updating software to Github main branch HEAD..."
    git fetch origin
    git reset --hard origin/main
    # Trampoline: reload the launch script and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    cd $CWD
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
    cd $CWD
    exit $exit_code
fi

# 0: Exit normally
cd $CWD
echo "Exited."


