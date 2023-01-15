#!/usr/bin/env python3

# Read incoming data block from stdin and convert to line based format (one line per sample)

import sys
import binascii


def main():
    for line in sys.stdin:
        try:
            # tweak: remove 2 characters at the beginning and 3 from the end of line
            line = line[4:-7]
            for i in range(0, len(line), 16):
                print('{:04x} {} {} {} {}'.format(i//16 , line[i : i+4],\
                                                          line[i+4 : i+8],\
                                                          line[i+8 : i+12],\
                                                          line[i+12 : i+16]))
        except ValueError:
            print('reader.py, main(): Failed to read "' + line + '".', file=sys.stderr)
 


if __name__ == '__main__':
    main()


