#!/usr/bin/env python3

# Convert incoming integer samples to floating point and apply scaling factors 

import sys

def main():
    for line in sys.stdin:
        try:
            # do stuff
            print(line)
        except ValueError:
            # if stuff goes wrong, deal with it here
            1


if __name__ == '__main__':
    main()


