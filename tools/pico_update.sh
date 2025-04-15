#!/bin/bash

# Update Pico microcontroller from files in pico directory

# Find current working directory and absolute paths of script and program file directories
CWD="$(pwd)"
SCRIPT_DIR="$(realpath $(dirname $0))"
PROGRAM_DIR="$(realpath $SCRIPT_DIR/../pqm)"
PICO_DIR="$(realpath $SCRIPT_DIR/../pico)"
PICO_FILES="main.py stream.py"


get_local_sha256 () {
    echo $(shasum -a 256 "$PICO_DIR/$1") | awk '{print $1}'
}

get_pico_sha256 () {
    echo $("$PROGRAM_DIR/pico_control.py" --command "SHA256 $1") | awk '{print $3}'
}

compare_files () {
    sha256_local=$(get_local_sha256 "$1")
    sha256_pico=$(get_pico_sha256 "$2")
    if [[ "$sha256_pico" == "$sha256_local" ]]; then
        echo 0
    else
        echo 1
    fi
}

transfer_file_to_pico () {
    # $1 name of file to send
    file_length="$(ls -l $1 | awk '{print $5}')"
    # transfer the file over to a temporary file
    "$PROGRAM_DIR/pico_control.py" --command "SAVE transfer_file $file_length" --send_file "$1"
    # we only actually overwrite the old file if the temporary file checksum matches the source
    if [[ $(compare_files "$pico_file" transfer_file) ]]; then
        "$PROGRAM_DIR/pico_control.py" --command "RENAME transfer_file $pico_file"
    fi
}

# Hard reset Pico, since it may be streaming and unresponsive to commands
echo "***** UPDATE PICO UTILITY *****"
echo "Resetting Pico."
"$PROGRAM_DIR/pico_control.py" --hard_reset

echo "Comparing local versions of files with those currently on Pico..."
for pico_file in $PICO_FILES; do
    if [[ $(compare_files "$pico_file" "$pico_file") ]]; then
        echo "$pico_file: same version local and Pico, no need to update."
    else
	echo "$pico_file: file versions are different, updating Pico..."
	echo "$pico_file: copying new file over..."
        transfer_file_to_pico "$PICO_DIR/$pico_file"
	echo "$pico_file: checking if the copied file is good."
        if [[ $(compare_files "$pico_file" "$pico_file") ]]; then
            echo "$pico_file: update succeeded."
	else
            echo "$pico_file: update failed, unfortunately."
	fi
    fi
done

# Hard reset Pico again, so that we run the new code
echo "Resetting Pico."
"$PROGRAM_DIR/pico_control.py" --hard_reset
