#!/usr/bin/env python3

# Read incoming binary block from stdin and convert to hexadecimal format

import sys
import serial
import binascii



def main():
    try:
        ser = serial.Serial('/dev/ttyACM0')
    except:
        print("Couldn't open serial port.", file=sys.stderr)
        sys.exit(1)

    while 1:    
        try:
            bs = ser.read(128)
            sys.stdout.buffer.write(binascii.hexlify(bs))
            sys.stdout.write('\n')
            sys.stdout.flush()
        except ValueError:
            print('reader.py, main(): Failed to read "' + line + '".', file=sys.stderr)
    ser.close()



if __name__ == '__main__':
    main()


