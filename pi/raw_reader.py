#!/usr/bin/env python3

# Read incoming data block from stdin and convert to line based format (one line per sample)

import sys
import serial



def main():
    try:
        ser = serial.Serial('/dev/ttyACM0')
    except:
        print("Couldn't open serial port.", file=sys.stderr)
        sys.exit(1)

    while 1:    
        try:
            print(ser.readline())
        except ValueError:
            print('reader.py, main(): Failed to read "' + line + '".', file=sys.stderr)
    ser.close()



if __name__ == '__main__':
    main()


