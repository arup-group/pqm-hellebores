#!/bin/bash

# Update Pico microcontroller from files in pico directory

# Find current working directory and absolute paths of script and program file directories
CWD=$(pwd)
SCRIPT_DIR=$(realpath $(dirname $0))
PROGRAM_DIR=$(realpath $SCRIPT_DIR/../pqm)
PICO_DIR=$(realpath $SCRIPT_DIR/../pico)



echo "Getting versions of files currenly on Pico"
VERSIONS_PICO=$($PROGRAM_DIR/pico_control.py "SHA256 main.py"; $PROGRAM_DIR/pico_control.py "SHA256 main.py")
echo $VERSIONS_PICO



