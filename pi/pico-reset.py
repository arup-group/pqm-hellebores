#!/usr/bin/env python3

import RPi.GPIO as gp
import time

gp.setmode(gp.BCM)
gp.setup(6, gp.OUT)
gp.output(6, False)
time.sleep(1)
gp.output(6, True)
time.sleep(1)
gp.output(6, False)
time.sleep(1)
gp.output(6, True)
time.sleep(1)
gp.cleanup()




