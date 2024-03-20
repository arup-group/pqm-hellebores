#!/usr/bin/env python3

# Read incoming binary block from stdin and write out in hexadecimal text format
# Incremental index number then one sample for each channel, per line

import sys
import serial
import settings

BUFFER_SIZE = 32
BLOCK_SIZE = BUFFER_SIZE * 8
SERIAL_PORTS = ['/dev/ttyACM0', '/dev/ttyUSB0',
                'COM4', 'COM3', 'COM2', 'COM1',
                '/dev/ttyS4', '/dev/ttyS3', '/dev/ttyS2', '/dev/ttyS1']
 
 
def read_and_print(ser):
    # sometimes (rarely) there is a serial read error.
    # this can be caused by the getty terminal process trying to read/write
    # the serial port. We allow up to 5 successive re-tries.
    retries = 5
    while retries > 0:    
        try:
            bs = (ser.read(BLOCK_SIZE).hex())
            # process data as lines of 8 bytes, or 16 hex characters
            for i in range(0, BLOCK_SIZE*2, 16):
                print(f'{i//16 :04x} {bs[i:i+4]} {bs[i+4:i+8]} {bs[i+8:i+12]} {bs[i+12:i+16]}')
            sys.stdout.flush()
            retries = 5

        except ValueError:
            print('reader.py, read_and_print(): The data was not correct or complete.', file=sys.stderr)
        except OSError:
            print('reader.py, read_and_print(): Failed to read from serial port.', file=sys.stderr)
            retries = retries - 1
    print('reader.py, read_and_print(): Read error was persistent, exiting loop.', file=sys.stderr)


def main():
    # load settings from settings.json
    # settings aren't used yet, but could be added to adjust ADC
    st = settings.Settings(reload_on_signal=False)
    connection_made = False
    # try a selection of serial ports
    for port in SERIAL_PORTS:
        try:
            # if we've previously made a connection, but the read loop was broken,
            # quit here rather than trying a different port
            if connection_made:
                break
            # try the port
            print(f"reader.py, main(): Trying port {port}.", file=sys.stderr)
            ser = serial.Serial(port)
            connection_made = True
            # read the data
            print(f"reader.py, main(): Connected.", file=sys.stderr)
            read_and_print(ser)
        except:
            print(f"reader.py, main(): Serial error.", file=sys.stderr)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()


if __name__ == '__main__':
    main()


