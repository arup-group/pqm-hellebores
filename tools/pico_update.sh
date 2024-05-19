#!/bin/bash

# Update Pico microcontroller from files in pico directory

# Find current working directory and absolute paths of script and program file directories
CWD=$(pwd)
SCRIPT_DIR=$(realpath $(dirname $0))
PROGRAM_DIR=$(realpath $SCRIPT_DIR/../pqm)
PICO_DIR=$(realpath $SCRIPT_DIR/../pico)
PICO_FILES="main.py stream.py"


get_local_sha256 () {
    echo $(sha256sum $PICO_DIR/$1 | cut -d ' ' -f 1)
}

get_pico_sha256 () {
    echo $($PROGRAM_DIR/pico_control.py --command "SHA256 $1" | cut -d ' ' -f 3 | tr -d '\n')
}

transfer_file_to_pico () {
    # $1 name of file to send
    file_length=$(ls -l $1 | cut -d ' ' -f 5)
    $PROGRAM_DIR/pico_control.py --command "SAVE transfer_file $file_length" --send_file "$1"
    echo "Checking to see if the transfer was successful."
    sha256_local=$(get_local_sha256 "$pico_file")
    sha256_transfer=$(get_pico_sha256 "transfer_file")
    # we only actually overwrite the old file if the transfer checksum matches the source
    if [[ "$sha256_transfer" == "$sha256_local" ]]; then
        $PROGRAM_DIR/pico_control.py --command "RENAME transfer_file $pico_file"
    fi
}

# Hard reset Pico, since it may be streaming and unresponsive to commands
echo "***** UPDATE PICO UTILITY *****"
echo "Resetting Pico."
$PROGRAM_DIR/pico_control.py --hard_reset

for pico_file in $PICO_FILES; do
    echo "Comparing local versions of files with those currently on Pico"
    sha256_local=$(get_local_sha256 "$pico_file")
    sha256_pico=$(get_pico_sha256 "$pico_file")
    if [[ "$sha256_pico" == "$sha256_local" ]]; then
        echo "$pico_file: same version local and Pico, no need to update."
    else
	echo "$pico_file: file versions are different, updating Pico..."
	echo "$pico_file: copying new file over..."
        transfer_file_to_pico "$PICO_DIR/$pico_file"
	echo "$pico_file: checking if the copied file is good."
        sha256_final=$(get_pico_sha256 "$pico_file")
        if [[ "$sha256_final" == "$sha256_local" ]]; then
            echo "$pico_file: update succeeded."
	else
            echo "$pico_file: update failed, unfortunately."
	fi
    fi
done

# Hard reset Pico again, so that we run the new code
echo "Resetting Pico."
$PROGRAM_DIR/pico_control.py --hard_reset


