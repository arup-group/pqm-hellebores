#!/usr/bin/env python3

# 
#                     _                       
#  _ __ ___  __ _  __| | ___ _ __ _ __  _   _ 
# | '__/ _ \/ _` |/ _` |/ _ \ '__| '_ \| | | |
# | | |  __/ (_| | (_| |  __/ | _| |_) | |_| |
# |_|  \___|\__,_|\__,_|\___|_|(_) .__/ \__, |
#                                |_|    |___/ 
# 
# Read incoming binary block from stdin and write out in hexadecimal text format
# Incremental index number then one sample for each channel, per line

import sys
import serial
import serial.tools.list_ports

BUFFER_SIZE = 32
BLOCK_SIZE = BUFFER_SIZE * 8
 
 
def find_serial_device():
    '''determines the serial port that the Pico is connected to. On Ubuntu/Raspberry
    Pi, serial ports are in the form '/dev/ttyUSBx' where x is an integer 0-7.
    On Windows, serial ports are in the form 'COMx' where x is an integer 1-8'''
    ports = serial.tools.list_ports.comports()
    port_name = None
    for port in ports:
        description = port.description
        if 'board in fs mode' in description.lower() or 'serial' in description.lower():
            print(f'Found {port.description}.', file=sys.stderr)
            port_name = port.device
            break
    return port_name
 

def read_and_print(ser):
    '''Reads binary data from serial port, and prints as hexadecimal text to stdout.
    Sometimes (rarely) there is a serial read error. This can be caused by the getty
    terminal process trying to read/write the serial port. We allow up to 5 successive
    re-tries before quitting.'''
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
    '''This program needs the Pico to have been set into streaming mode by the 
    pico_control.py program first.'''
    port_name = find_serial_device()
    if port_name:
        try:
            ser = serial.Serial(port_name)
            print(f"reader.py, main(): Connected.", file=sys.stderr)
            read_and_print(ser)
        except OSError:
            print(f"reader.py, main(): Serial error.", file=sys.stderr)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()


if __name__ == '__main__':
    main()


