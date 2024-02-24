#!/usr/bin/env python3

import RPi.GPIO as gp
import time

MODE_PIN = 13

gp.setmode(gp.BCM)
gp.setup(MODE_PIN, gp.OUT)

try:
    # Set the mode select pin high for 60 seconds
    gp.output(MODE_PIN, True)
    time.sleep(60)
    gp.output(MODE_PIN, False)
    gp.cleanup()

except:
    # exit correctly
    gp.cleanup()




