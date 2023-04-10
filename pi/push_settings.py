#!/usr/bin/env python3

import os
import sys


def signal_other_processes():
    # send a signal to everyone to update their settings
    if sys.platform == 'linux':
        os.system("pkill -f --signal=SIGUSR1 'python3 ./rain.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./reader.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./scaler.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./trigger.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./mapper.py'")


signal_other_processes()

    
