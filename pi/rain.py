#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings



def get_sample(i, t, f):
    t = t/1000.0       # seconds
    c0 = int(25000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
    c1 = int(8000.0*math.sin(2.0*math.pi*f*t) + 2.0*(random.random()-0.5))
    c2 = int(200.0*math.sin(2.0*math.pi*f*t) + 5.0*(random.random()-0.5))
    c3 = int(5000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)


def main():
    # read settings from settings.json
    st = settings.Settings(lambda: None)

    # we use system clock to figure out when to print out the next sample
    tp = int(time.time()*1000.0/st.interval)
    i=0
    while True:
        # check the clock and see if it has changed by one sample period
        tn = int(time.time()*1000.0/st.interval)
        if tn != tp:
            tp = tn
            t, c0, c1, c2, c3 = get_sample(i, i*st.interval, st.frequency)
            print(f'{t :04x} {c0 :04x} {c1 :04x} {c2 :04x} {c3 :04x}')
            i = i + 1

if __name__ == '__main__':
    main()




