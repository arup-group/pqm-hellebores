#!/usr/bin/env python3

# Convert incoming integer samples to floating point and apply scaling factors 

import sys
import signal
import json


def get_settings():
    global sf0, sf1, sf2, sf3, interval
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        sf0 = js['scale_c0']
        sf1 = js['scale_c1']
        sf2 = js['scale_c2']
        sf3 = js['scale_c3']
        interval = 1000.0/js['sample_rate']
    except:
        print("scaler.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
        sf0 = 0.01
        sf1 = 0.03
        sf2 = 0.05
        sf3 = 0.05
        interval = 1000.0/7812.5   # milliseconds

  
def settings_handler(signum, frame):
    get_settings()


def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)


def scale(sample, i, interval, sf0, sf1, sf2, sf3):
    return (interval*i,\
             from_twos_complement(sample[1])*sf0,\
             from_twos_complement(sample[2])*sf1,\
             from_twos_complement(sample[3])*sf2,\
             from_twos_complement(sample[4])*sf3)


def main():
    global sf0, sf1, sf2, sf3, interval
    get_settings()
    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    i = 0   # sample index
    for line in sys.stdin:
        line = line.rstrip()
        try:
            sample = scale([int(w.strip(), base=16) for w in line.split()],\
                              i, interval, sf0, sf1, sf2, sf3)
        except ValueError:
            print('scaler.py, main(): Failed to read "' + line + '".', file=sys.stderr)
        print('{:12.4f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(*sample))
        i = i + 1



if __name__ == '__main__':
    main()


