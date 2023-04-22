#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings



def settings_handler(signum, frame):
    global st
    # read in updated settings.json
    st.get_settings()


def get_sample(i, t, f):
    t = t/1000.0       # seconds
    c0 = int(25000.0*math.sin(2.0*math.pi*f*t) + 1000.0*(random.random()-0.5))
    c1 = int(8000.0*math.sin(2.0*math.pi*f*t) + 200.0*(random.random()-0.5))
    c2 = int(12000.0*math.sin(2.0*math.pi*f*t) + 500.0*(random.random()-0.5))
    c3 = int(6800.0*math.sin(2.0*math.pi*f*t) + 50.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)

def main():
    global st

    # read settings or set defaults into global variables 
    st = settings.Settings()
    st.get_settings()

    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    # we use system clock to figure out when to print out the next sample
    tp = int(time.time()*1000.0/st.interval)
    i=0
    while 1:
        # check the clock and see if it has changed by one sample period
        tn = int(time.time()*1000.0/st.interval)
        if tn != tp:
            tp = tn
            print('{:04x} {:04x} {:04x} {:04x} {:04x}'.format(*get_sample(i, i*st.interval, st.frequency)))
            i = i + 1

if __name__ == '__main__':
    main()




