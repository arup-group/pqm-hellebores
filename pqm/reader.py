#!/usr/bin/env python3

# Read incoming binary block from stdin and write out in hexadecimal text format
# Incremental index number then one sample for each channel, per line

import sys
import serial
import settings



def main():
    # load settings from settings.json
    # settings aren't used yet, but could be added to adjust ADC
    st = settings.Settings(reload_on_signal=False)
    
    try:
        ser = serial.Serial('/dev/ttyACM0')
    except:
        print("reader.py: Couldn't open serial port.", file=sys.stderr)
        sys.exit(1)

    # sometimes (rarely) there is a serial read error.
    # this can be caused by the getty terminal process trying to read/write
    # the serial port. We allow up to 5 successive re-tries.
    retries = 5
    while True:    
        try:
            bs = (ser.read(256).hex())
            # process data in chunks of 8 bytes, or 16 hex digits
            for i in range(0, len(bs), 16):
                print(f'{i//16 :04x} {bs[i:i+4]} {bs[i+4:i+8]} {bs[i+8:i+12]} {bs[i+12:i+16]}')
            sys.stdout.flush()
            retries = 5
        except ValueError:
            print('reader.py, main(): The data was not correct or complete.', file=sys.stderr)
        except OSError:
            print('reader.py, main(): Failed to read from serial port.', file=sys.stderr)
            retries = retries - 1
            if retries == 0:
                print('reader.py, main(): Read error was persistent, quitting.', file=sys.stderr)
                break

    ser.close()



if __name__ == '__main__':
    main()

