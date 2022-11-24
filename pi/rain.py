#!/usr/bin/env python3


import math
import random

BUFFER_LENGTH = 8192
FREQ = 60.0
DELTA_T = 0.000294       # derived from (reciprocal of) sample rate
ROLLOVER = 1000000       # we make N where N * DELTA_T is an integer

index = 0


def make_capture():
    frame = []
    global index
    for s in range(0, BUFFER_LENGTH):
        t = DELTA_T * index
        v1 = int(1500.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random() - 0.5)) << 8
        v2 = int(1500.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random() - 0.5)) << 8
        v3 = int(1500.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random() - 0.5)) << 8
        v4 = int(1500.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random() - 0.5)) << 8
        frame.append((index % 65536, v1, v2, v3, v4))
        # we make sure when we rollover the index, the result of the 'sin' function
        # is not affected, so there is no discontinuity in the generator
        if index < ROLLOVER:
            index = index + 1
        else:
            index = 0
    return frame


def main():
    while 1:
        frame = make_capture()
        for e in frame:
            print('{:5d} {:8d} {:8d} {:8d} {:8d}'.format(*e))



if __name__ == '__main__':
    main()




