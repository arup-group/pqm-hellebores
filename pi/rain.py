#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import json


# set up constants
freq = 50.0                                   # Hertz
sample_rate = 7812.5                          # samples/second
sample_period_ns = 1000000000.0/sample_rate   # in nanoseconds


def get_settings():
    global freq, sample_rate, sample_period_ns
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        freq = js['frequency']
        sample_rate = js['sample_rate']
        sample_period_ns = 1000000000.0/sample_rate
    except:
        print("rain.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
   

def settings_handler(signum, frame):
    # read in updated settings.json
    get_settings()


def get_sample(i, t, f):
    t = t/1000000000.0       # seconds
    c0 = int(25000.0*math.sin(2.0*math.pi*f*t) + 1000.0*(random.random()-0.5))
    c1 = int(8000.0*math.sin(2.0*math.pi*f*t) + 200.0*(random.random()-0.5))
    c2 = int(12000.0*math.sin(2.0*math.pi*f*t) + 500.0*(random.random()-0.5))
    c3 = int(6800.0*math.sin(2.0*math.pi*f*t) + 500.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)

def main():
    # read settings or set defaults into global variables 
    get_settings()

    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    # we use high resolution system clock to figure out when to print out
    # the next sample iteration
    tp = int(time.monotonic_ns()/sample_period_ns)
    i=0
    while 1:
        # check the clock and see if it has changed by one sample period
        tn = int(time.monotonic_ns()/sample_period_ns)
        if tn != tp:
            tp = tn
            print('{:04x} {:04x} {:04x} {:04x} {:04x}'.format(*get_sample(i, i*sample_period_ns, freq)))
            i = i + 1

if __name__ == '__main__':
    main()




