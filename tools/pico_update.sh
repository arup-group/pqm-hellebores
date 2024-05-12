#!/bin/bash

# Update Pico microcontroller from files in pico directory

# Find current working directory and absolute paths of script and program file directories
CWD=$(pwd)
SCRIPT_DIR=$(realpath $(dirname $0))
PROGRAM_DIR=$(realpath $SCRIPT_DIR/../pqm)
PICO_DIR=$(realpath $SCRIPT_DIR/../pico)


for pico_file in main.py stream.py; do
    echo "Comparing local versions of files with those currently on Pico"
    version_local=$(sha256sum $PICO_DIR/$pico_file | cut -d ' ' -f 1)
    version_pico=$($PROGRAM_DIR/pico_control.py --command "SHA256 $pico_file" | cut -d ' ' -f 3 | tr -d '\n')
    echo $pico_file:
    echo $version_local
    echo $version_pico
    if [[ "$version_pico" == "$version_local" ]]; then
        echo "Same version local and Pico, no need to update."
    else
	echo "Different versions, updating Pico..."
	file_length=$(ls -l $PICO_DIR/$pico_file | cut -d ' ' -f 5)
	echo $file_length
	$PROGRAM_DIR/pico_control.py --command "SAVE $pico_file $file_length"
        $PROGRAM_DIR/pico_control.py --send_file "$PICO_DIR/$pico_file"
        version_pico=$($PROGRAM_DIR/pico_control.py --command "SHA256 $pico_file" | cut -d ' ' -f 3 | tr -d '\n')
	if [ "$version_pico" == "$version_local" ]; then
            echo "Update succeeded."
	else
            echo "Update failed, unfortunately."
	fi
    fi
done


