#!/bin/bash

# NB sudo apt install xcowsay
SCRIPT_DIR=$(realpath $(dirname $0))
$SCRIPT_DIR/get_identity.py | xcowsay
