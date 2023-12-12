#!/usr/bin/env python3

import os
import sys

# send a signal to everyone to update their settings
if os.name == 'posix':
    os.system("pkill --signal=SIGUSR1 -f 'python3 \./.*\.py'")
else:
    print(f"This doesn't work on {os.name}", file=sys.stderr)


    
