#!/usr/bin/env python3

# Convert incoming integer samples to floating point and apply scaling factors 

import sys

SF0 = 0.01
SF1 = 0.03
SF2 = 0.05
SF3 = 0.05
INTERVAL = 1000.0/7812.5   # milliseconds


def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)


def scale(sample, i, interval, sf0, sf1, sf2, sf3):
    return (interval*i,\
             from_twos_complement(sample[1])*sf0,\
             from_twos_complement(sample[2])*sf1,\
             from_twos_complement(sample[3])*sf2,\
             from_twos_complement(sample[4])*sf3)


def main():
    i = 0   # sample index
    for line in sys.stdin:
        line = line.rstrip()
        try:
            sample = scale([int(w.strip(), base=16) for w in line.split()],\
                              i, INTERVAL, SF0, SF1, SF2, SF3)
        except ValueError:
            print('scaler.py, main(): Failed to read "' + line + '".', file=sys.stderr)
        print('{:12.4f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(*sample))
        i = i + 1



if __name__ == '__main__':
    main()


