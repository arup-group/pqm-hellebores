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
# One sample for each channel, per line

import sys
import serial
import serial.tools.list_ports

BUFFER_SIZE = 128
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
 

def connect(port_name):
    '''Connects to serial port with re-try and backoff in case other services are
    trying to probe the port.'''
    sleeping = [ 0.2, 0.3, 0.5, 1.0, 2.0 ]
    this_try = 0
    # try to connect five times
    while this_try < 5:
        ser = serial.Serial(port_name)
        if ser.is_open:
            print(f"reader.py, main(): Connected.", file=sys.stderr)
            # discard anything hanging around in the hardware buffer
            ser.reset_input_buffer()
            return ser
        time.sleep(sleeping[this_try])
        this_try = this_try + 1
    print(f"reader.py, main(): Failed to connect to serial port.", file=sys.stderr)
    raise serial.SerialException


def read_and_print(ser):
    '''Reads binary data from serial port, and prints as hexadecimal text to stdout.
    Sometimes (rarely) there is a serial read error.'''
    bs = bytearray(BLOCK_SIZE)
    retries = 5
    this_try = 0
    while this_try < retries:
        try:
            # read exactly BLOCKSIZE bytes into bytearray buffer
            ser.readinto(bs)
            # process data as lines of 8 bytes, or 16 hex characters
            hexstr = bs.hex()
            for i in range(0, BLOCK_SIZE*2, 16):
                print(f'{hexstr[i:i+4]} {hexstr[i+4:i+8]} {hexstr[i+8:i+12]} {hexstr[i+12:i+16]}')
            retries = 5

        except ValueError:
            print('reader.py, read_and_print(): The data was not correct or complete.', file=sys.stderr)
        except (IOError, OSError):
            print('reader.py, read_and_print(): Failed to read from serial port.', file=sys.stderr)
            retries = retries + 1
    print('reader.py, read_and_print(): Read error was persistent, exiting loop.', file=sys.stderr)
    raise serial.SerialException


def main():
    '''This program needs the Pico to have been set into streaming mode by the 
    pico_control.py program first.'''
    port_name = find_serial_device()
    if port_name:
        try:
            ser = connect(port_name)
            read_and_print(ser)
        except:
            print(f"reader.py, main(): serial comms error, exiting.", file=sys.stderr)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()
    else:
        print("reader.py, main(): Couldn't find a suitable serial port, exiting.", file=sys.stderr)


if __name__ == '__main__':
    main()


