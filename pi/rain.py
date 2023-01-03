#!/usr/bin/env python3

import math
import random
import time


FREQ = 60.0
SAMPLE_RATE = 15625


def get_sample(i, t):
    t = t/1000000000.0
    c1 = int(25000.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random()-0.5))
    c2 = int(8000.0*math.sin(2.0*math.pi*FREQ*t) + 50.0*(random.random()-0.5))
    c3 = int(12000.0*math.sin(2.0*math.pi*FREQ*t) + 50.0*(random.random()-0.5))
    c4 = int(2000.0*math.sin(2.0*math.pi*FREQ*t) + 10.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (i & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff, c4 & 0xffff)

def main():
    delta_t_ns = 1000000000.0/SAMPLE_RATE   
    t0 = time.monotonic_ns()
    i = 0

    while 1:
        t = i*delta_t_ns              # next sample time
        tn = time.monotonic_ns()          # high resolution time check
        if tn-t0 >= t:
            print('{:04x} {:04x} {:04x} {:04x} {:04x}'.format(*get_sample(i, t)))
            i = i + 1


if __name__ == '__main__':
    main()




