#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings

FREQUENCY=50.2


def make_sample(t, fs, noise):
    """time, list of tuples (freqency, magitude, phase) and noise magnitude"""
    t = t/1000.0       # convert milliseconds to seconds
    sout = 0
    for f in fs:
        (freq, mag, ph) = f
        sout = sout + mag*math.sin(math.pi*(2*freq*t + ph/180.))
    sout = sout + noise*(random.random()-0.5)
    return sout


def get_sample(i, t, f):
    c0 = int(make_sample(t, [(f, 25000.0, 0.0)], 100.0))
    c1 = int(make_sample(t, [(f, 8000.0, 0.0), (3*f, 3000.0, 30.0/3)], 10.0))
    c2 = int(make_sample(t, [(f, 200.0, 0.0)], 5.0))
    c3 = int(make_sample(t, [(f, 5000.0, 0.0)], 10.0))
    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)


#def get_sample(i, t, f):
#    """integer sample number, time, frequency, magnitude and phase tuples"""
#    t = t/1000.0       # seconds
#    c0 = int(25000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
#    c1 = int(8000.0*math.sin(2.0*math.pi*f*t) + 2.0*(random.random()-0.5))
#    c2 = int(200.0*math.sin(2.0*math.pi*f*t) + 5.0*(random.random()-0.5))
#    c3 = int(5000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
#    # the '& 0xffff' truncates negative numbers to fit in 16 bits
#    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)
#

def main():
    # read settings from settings.json
    st = settings.Settings(reload_on_signal=False)

    # we use system clock to figure out when to print out the next sample
    samples_previous = int(time.time()*1000.0/st.interval)
    i=0
    while True:
        # check the clock and see if it has changed by one sample period
        samples_now = int(time.time()*1000.0/st.interval)
        new_samples = samples_now - samples_previous
        while new_samples > 0:
            t, c0, c1, c2, c3 = get_sample(i, i*st.interval, FREQUENCY)
            print(f'{t :04x} {c0 :04x} {c1 :04x} {c2 :04x} {c3 :04x}')
            i = i + 1
            new_samples = new_samples - 1
        samples_previous = samples_now


if __name__ == '__main__':
    main()




