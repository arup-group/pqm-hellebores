#!/usr/bin/env python3

# Calculate electrical parameters

import sys
import signal
import settings


def main():
    st = settings.Settings()

    for line in sys.stdin:
        line = line.rstrip()
        print(line)

    print('Finished calculations.')

if __name__ == '__main__':
    main()


