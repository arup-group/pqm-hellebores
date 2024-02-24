#!/usr/bin/env python3

import RPi.GPIO as gp
import time

# The Pico software has a hardware interrupt configured to monitor pin 6.
# When a falling edge is detected, the ISR will stop and restart the software.
# The entry point of the software includes a pause, at least 30 seconds
# which in some scenarios allows the Pico to be investigated using the REPL
# in thonny.

# Running this script will cycle pin 6 thus triggering the reset routine.

gp.setmode(gp.BCM)
gp.setup(6, gp.OUT)
time.sleep(1)
gp.output(6, False)
time.sleep(1)
gp.output(6, True)
time.sleep(1)
gp.cleanup()




