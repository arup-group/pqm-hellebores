#!/usr/bin/env python3

import RPi.GPIO as gp
import time

# The Pico software has a hardware interrupt configured to monitor pin 6.
# When a falling edge is detected, the ISR will stop and restart the software.

# Running this script will cycle pin 6 thus triggering the reset routine.
RESET = 6

gp.setmode(gp.BCM)
gp.setup(RESET, gp.OUT)
time.sleep(1)
gp.output(RESET, False)
time.sleep(1)
gp.output(RESET, True)
time.sleep(1)
gp.cleanup()




