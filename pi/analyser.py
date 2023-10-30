#!/usr/bin/env python3

# Calculate electrical parameters

import sys
import signal
import settings


def main():
    st = settings.Settings()

    i = 0
    for line in sys.stdin:
        line = line.rstrip()
        # print only one line in 7812 (1 per second, approx)
        if i == 0:
            print(line)
        i = (i + 1) % 7812
    print('Finished calculations.')

if __name__ == '__main__':
    main()


