#!/usr/bin/env python3

import math
import random
import time


BUFFER_LENGTH = 8192
FREQ = 60.0
SAMPLE_RATE = 15625

index = 0
delta_t_ns = 1000000000.0/SAMPLE_RATE   


    
def get_sample(t):
    t = t/1000000000.0
    c1 = int(25000.0*math.sin(2.0*math.pi*FREQ*t) + 100.0*(random.random()-0.5))
    c2 = int(8000.0*math.sin(2.0*math.pi*FREQ*t) + 50.0*(random.random()-0.5))
    c3 = int(12000.0*math.sin(2.0*math.pi*FREQ*t) + 50.0*(random.random()-0.5))
    c4 = int(2000.0*math.sin(2.0*math.pi*FREQ*t) + 10.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (index & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff, c4 & 0xffff)

def main():
    global index
    while 1:
        t_ns = time.monotonic_ns()        # high resolution time check
        t_sample_ns = index*delta_t_ns    # next sample time
        if t_ns >= index*delta_t_ns:
            print('{:04x} {:04x} {:04x} {:04x} {:04x}'.format(*get_sample(t_sample_ns)))
            index = index+1


if __name__ == '__main__':
    main()




