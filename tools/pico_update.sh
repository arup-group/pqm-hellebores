#!/bin/bash

# Update Pico microcontroller from files in pico directory

# Find current working directory and absolute paths of script and program file directories
SCRIPT_DIR="$(realpath $(dirname $0))"
PROGRAM_DIR="$(realpath $SCRIPT_DIR/../pqm)"
PICO_DIR="$(realpath $SCRIPT_DIR/../pico)"

"$PROGRAM_DIR/pico_control.py" --push_file_if_needed="$PICO_DIR/main.py"
"$PROGRAM_DIR/pico_control.py" --push_file_if_needed="$PICO_DIR/stream.py"

# Hard reset Pico again, so that we now run the new code
echo "Resetting Pico."
"$PROGRAM_DIR/pico_control.py" --hard_reset
