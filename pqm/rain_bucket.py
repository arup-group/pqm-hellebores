#!/usr/bin/env python3

import math
import random
import time
import sys
import signal
import settings
import os

# NB path is relative to the location of this program file
DEFAULT_SAMPLE_FILE = '../sample_files/simulated.out'


def generate(sample_file):
    # read settings from settings.json
    st = settings.Settings(reload_on_signal=False)

    # read in the whole of the sample file
    try:
        with open(sample_file) as f:
            rain_bucket = f.read().split('\n')
    except:
        print('rain_bucket.py: error opening or reading sample data file', file=sys.stderr)
        sys.exit(1)

    # we use system clock to figure out when to print out the next sample
    samples_previous = int(time.time()*1000.0/st.interval)
    i=0
    imax = len(rain_bucket) - 2
    while True:
        # check the clock and see if it has increased by at least one sample period
        # since we last printed out some samples
        samples_now = int(time.time()*1000.0/st.interval)
        new_samples = samples_now - samples_previous
        # if it has, print out more samples
        while new_samples > 0:
            print(rain_bucket[i % imax])
            i = i + 1
            new_samples = new_samples - 1
        samples_previous = samples_now


def main():
    # we use the sample file name on the command line, if provided
    # otherwise a default one
    if len(sys.argv) > 1:
        sample_file = sys.argv[1]
    else:
        # figure out the actual path of the sample file, regardless of the current
        # working directory
        sample_file = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                        DEFAULT_SAMPLE_FILE))
    generate(sample_file)


if __name__ == '__main__':
    main()




