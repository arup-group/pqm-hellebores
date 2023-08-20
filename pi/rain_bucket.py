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
    try:
        with open(sys.argv[1]) as f:
            rain_bucket = f.read().split('\n')
    except:
        print('rain_bucket.py: error opening or reading sample data file', file=sys.stderr)
        sys.exit(1)

    # we use system clock to figure out when to print out the next sample
    tp = int(time.time()*1000.0/st.interval)
    i=0
    imax = len(rain_bucket) - 1
    while True:
        # check the clock and see if it has changed by one sample period
        tn = int(time.time()*1000.0/st.interval)
        if tn != tp:
            tp = tn
            print(rain_bucket[i % imax])
            i = i + 1

if __name__ == '__main__':
    main()




