#!/bin/bash

# Increase the number of file descriptors that we can have in the current shell
ulimit -n 2048

# Find current working directory and absolute paths of script and program file directories
CWD="$(pwd)"
SCRIPT_DIR="$(realpath $(dirname $0))"
PROGRAM_DIR="$(realpath $SCRIPT_DIR/../pqm)"

# Change to the program directory
cd "$PROGRAM_DIR"

# Activate the virtual environment, if we have one
if [[ -e "$SCRIPT_DIR/../.venv" ]]; then
    source "$SCRIPT_DIR/../.venv/bin/activate"
fi

# Suppress the pygame import support message
export PYGAME_HIDE_SUPPORT_PROMPT=hide

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
for TD in "/run/shm" "/tmp"; do
    # if the location is available
    if [[ -d "$TD" ]]; then
        # create a program temporary directory in the temporary files area
        if [[ ! -d "$TD/pqm-hellebores" ]]; then
            mkdir "$TD/pqm-hellebores"
        fi
        # create a local symbolic link if we don't already have one
        if [[ ! -e "$PROGRAM_DIR/../output_files" ]]; then
            ln -s "$TD/pqm-hellebores" "$PROGRAM_DIR/../output_files"
        fi
        export TEMP="$TD/pqm-hellebores"
        # exit loop at the first TD location that works
        break
    fi
done

# if both attempts failed, quit with an error
if [[ -z "$TEMP" ]]; then
    echo "$0: Couldn't create temporary directory, check filesystem or write permissions, quitting." 1>&2
    exit 1
fi

# set up the working files
# NB the special variable $$ contains the PID of the current process
WAVEFORM_PIPE="$TEMP/waveform_pipe"
ANALYSIS_PIPE="$TEMP/analysis_pipe"
ANALYSIS_LOG_FILE="$TEMP/pqm.$$.csv"
ERROR_LOG_FILE="$TEMP/error.log"

# Clear old log file
[[ -e "$ERROR_LOG_FILE" ]] && rm "$ERROR_LOG_FILE"
# stderr file descriptor is number 2. Duplicate this file descriptor 2 to 4
# (ie save a copy of it) then redirect 2 to file, so that we catch error
# messages in a log file
exec 4>&2 2>"$ERROR_LOG_FILE"

# If they don't already exist, create named pipes (fifos) to receive data from
# the waveform and calculation processes
for PIPE_FILE in "$WAVEFORM_PIPE" "$ANALYSIS_PIPE"; do
    [[ -e "$PIPE_FILE" ]] || mkfifo "$PIPE_FILE"
    if [[ $? -ne 0 ]]; then
        echo "$0: There was an error creating a pipe file. Check your filesystem supports this." 1>&2
        exit 1
    fi
done

# Display the version information and settings that will be used initially
./version.py && echo ""
./settings.py && echo ""

# Run the capture and analysis, feeding two pipe files,
# then pass both pipes as parameters to the GUI
echo "Starting processing..."
echo "Measurement source   : $READER"
echo "Analysis log file    : $ANALYSIS_LOG_FILE"
echo "Waveform pipe file   : $WAVEFORM_PIPE"
echo "Analysis pipe file   : $ANALYSIS_PIPE"

####
# This is where we actually start the programs
# The incoming data is split (using 'tee') into two pipelines that feed analysis and waveform
# processes simultaneously.
# Note that the analysis pipeline is further split by another instance of tee so that analysis
# results are stored in a file as well as sent onwards, via $ANALYSIS_PIPE, to hellebores.py
# hellebores.py reads both $WAVEFORM_PIPE and $ANALYSIS_PIPE all the time, to keep the
# pipelines moving.
####

# Reset the Pico and start streaming.
if $real_hardware; then
    ./pico_control.py --hard_reset
    ./pico_control.py --command "START stream.py 1x 1x 1x 1x 7.812k" --no_response
fi

# Plumbing, pipe, pipe, pipe...
"$READER" \
    | ./scaler.py | tee >(./framer.py > "$WAVEFORM_PIPE") \
        | ./analyser.py | tee >(./analysis_to_csv.py > "$ANALYSIS_LOG_FILE") > "$ANALYSIS_PIPE" &

# hellebores.py GUI reads from both the waveform and analysis pipes...
./hellebores.py --waveform_file="$WAVEFORM_PIPE" --analysis_file="$ANALYSIS_PIPE"

# Because hellebores.py is running in the foreground, this script blocks (waits here) until it
# exits. The reader, scaler, analysis and waveform programs all terminate at the point
# that their pipeline connections are broken/closed.

# Capture the exit code from hellebores.py
# We'll check it's status shortly
exit_code=$?

# Restore stderr file descriptor 2 from saved state on 4, then delete fd 4
exec 2>&4 4>&-

# Now check the exit code
# 2: Restart
if [[ $exit_code -eq 2 ]]; then
    # Trampoline: reload the launch script (this file) and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    cd "$CWD"
    exec "$0"

# 3: Software update
elif [[ $exit_code -eq 3 ]]; then
    clear
    # If we're on a named branch use that, otherwise use main
    branch=$(git rev-parse --abbrev-ref HEAD)
    if [[ $? -ne 0 ]]; then
        branch="main"
    fi
    echo "Updating software to Github $branch branch HEAD..."
    git fetch origin
    git reset --hard "origin/$branch"
    # Trampoline: reload the launch script and run again
    echo "Restarting $0 in 5s..."
    sleep 5
    cd "$CWD"
    exec $0

# 4: Shutdown
elif [[ $exit_code -eq 4 ]]; then
    echo "Shutting down system..."
    exec sudo shutdown -h now

# Some other exit code: We have no idea what happened
elif [[ $exit_code -ne 0 ]]; then
    echo "The program quit with an unexpected exit code $exit_code. Not good."
    echo "Here's the error log file $ERROR_LOG_FILE, hope it helps :-)"
    cat "$ERROR_LOG_FILE"
    sleep 60
    cd "$CWD"
    exit $exit_code
fi

# 0: Exit normally
cd "$CWD"
echo "Exited."


