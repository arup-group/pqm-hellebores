#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings



def main():
    # read settings from settings.json
    st = settings.Settings()

    # read in the whole of the sample file
    with open('test_data.out') as f:
        rain_bucket = f.read().split('\n')


    # we use system clock to figure out when to print out the next sample
    tp = int(time.time()*1000.0/st.interval)
    i=0
    while True:
        # check the clock and see if it has changed by one sample period
        tn = int(time.time()*1000.0/st.interval)
        if tn != tp:
            tp = tn
            t, c0, c1, c2, c3 = rain_bucket[i % 78125].split()
            print(f'{t :04s} {c0 :04s} {c1 :04s} {c2 :04s} {c3 :04s}')
            i = i + 1

if __name__ == '__main__':
    main()




