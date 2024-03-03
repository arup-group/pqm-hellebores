#!/usr/bin/env python3

import RPi.GPIO as gp
import time

MODE_PIN = 13

gp.setmode(gp.BCM)
gp.setup(MODE_PIN, gp.OUT)

try:
    # Set the mode select pin high for 300 seconds
    gp.output(MODE_PIN, True)
    time.sleep(300)

except KeyError:
    print('Interrupted.')

finally:
    # exit correctly
    gp.output(MODE_PIN, False)
    gp.cleanup()

