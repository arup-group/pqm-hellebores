#!/usr/bin/env python3

# Resample input stream to a different sample interval

import sys

RESAMPLE_INTERVAL = 1.0    # milliseconds

 
def interpolate(sample0, sample1, t):
    t0 = sample0[0]
    t1 = sample1[0]
    t_frac = (t - t0) / (t1 - t0)
    if t_frac < 0.0 or t_frac > 1.0:
        print('resampler.py: Out of bounds error in interpolate()', file=sys.stderr)
    return (t, (1 - t_frac)*sample0[1] + t_frac*sample1[1],\
               (1 - t_frac)*sample0[2] + t_frac*sample1[2],\
               (1 - t_frac)*sample0[3] + t_frac*sample1[3],\
               (1 - t_frac)*sample0[4] + t_frac*sample1[4])

def main():
    # read first line to set up initial sample time
    s0 = [float() for w in sys.stdin.readline().split()]
    s1 = []
    # set initial output index, this will increment with each output line
    oi = int(s0[0]/RESAMPLE_INTERVAL) + 1

    for line in sys.stdin:
        line = line.rstrip()
        try:
            s1 = [float(w) for w in line.split()]
        except:
            print('Failed to read line "' + line + '".', file=sys.stderr)
        t = oi*RESAMPLE_INTERVAL
        if s1[0] > t:
            print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(*interpolate(s0, s1, t)))
            oi = oi + 1
        s0 = s1


if __name__ == '__main__':
    main()


