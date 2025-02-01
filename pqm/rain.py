#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings

HARDWARE_SCALE_FACTORS = [ 4.07e-07, 2.44e-05, 0.00122, 0.0489 ]
AMPLITUDES             = [ 0.000100, 0.4, 0.4, 230.0 ]
NOISE_AMPLITUDES       = [ 0.05, 0.05, 0.05, 0 ]   # as fraction of signal amplitude
SIGNAL = [ math.sqrt(2)*ampl/sf for sf, ampl in zip(HARDWARE_SCALE_FACTORS, AMPLITUDES) ]
NOISE = [ n*a for n,a in zip(NOISE_AMPLITUDES, SIGNAL) ]
FREQUENCY=50.2
TPF = 2*math.pi*FREQUENCY

def get_sample(t):
    """Calculate one sample point per channel."""
    wt = TPF*t/1000.0   # seconds
    c0 = int(SIGNAL[0]*math.sin(wt) + NOISE[0]*(random.random()-0.5))
    c1 = int(SIGNAL[1]*math.sin(wt) + NOISE[1]*(random.random()-0.5))
    c2 = int(SIGNAL[2]*math.sin(wt) + NOISE[2]*(random.random()-0.5))
    c3 = int(SIGNAL[3]*math.sin(wt) + NOISE[2]*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)


def main():
    # read settings from settings.json
    st = settings.Settings(reload_on_signal=False)

    # we use system clock to figure out when to print out the next sample
    ts = time.time()
    c=0
    while True:
        # check the clock and see if it has changed by one sample period
        tn = time.time()
        n = int((tn-ts)*1000.0/st.interval) - c
        # make a block of samples to bring us up to date with current time
        for _ in range(n):
            c0, c1, c2, c3 = get_sample(c*st.interval)
            print(f'{c0 :04x} {c1 :04x} {c2 :04x} {c3 :04x}')
            c += 1
        # sleep a little, for efficiency
        time.sleep(0.02)

if __name__ == '__main__':
    main()




