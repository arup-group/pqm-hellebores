#!/usr/bin/env python3

# Read incoming binary block from stdin and write out in hexadecimal text format
# Incremental index number then one sample for each channel, per line

import sys
import serial
import settings



def main():
    # load settings from settings.json
    # settings aren't used yet, but will be added to adjust ADC
    st = settings.Settings()
    
    try:
        ser = serial.Serial('/dev/ttyACM0')
    except:
        print("reader.py: Couldn't open serial port.", file=sys.stderr)
        sys.exit(1)

    while True:    
        try:
            bs = (ser.read(256).hex())
            # process data in chunks of 8 bytes, or 16 hex digits
            for i in range(0, len(bs), 16):
                print(f'{i//16 :04x} {bs[i:i+4]} {bs[i+4:i+8]} {bs[i+8:i+12]} {bs[i+12:i+16]}')
            sys.stdout.flush()
        except ValueError:
            print('reader.py, main(): Failed to read line.', file=sys.stderr)
    ser.close()



if __name__ == '__main__':
    main()


