#!/usr/bin/env python3

# Read incoming binary block from stdin and convert to hexadecimal format

import sys
import serial
import binascii
import signal
import settings


# settings aren't used yet, but will be added to adjust ADC
def settings_handler(signum, frame):
    global st
    st.get_settings()


def main():
    global st
    # load settings from settings.json
    st = settings.Settings()
    st.get_settings()
    
    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    try:
        ser = serial.Serial('/dev/ttyACM0')
    except:
        print("Couldn't open serial port.", file=sys.stderr)
        sys.exit(1)

    while 1:    
        try:
            data_block = (ser.read(256).hex())
            # process data in chunks of 8 bytes, or 16 hex digits
            for i in range(0, len(data_block), 16):
                print('{:04x} {} {} {} {}'.format(i//16, data_block[i:i+4], \
                                                         data_block[i+4:i+8], \
                                                         data_block[i+8:i+12], \
                                                         data_block[i+12:i+16]))
            sys.stdout.flush()
        except ValueError:
            print('reader.py, main(): Failed to read "' + line + '".', file=sys.stderr)
    ser.close()



if __name__ == '__main__':
    main()


