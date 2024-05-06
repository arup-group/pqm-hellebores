#!/usr/bin/env python3

# Read incoming binary block from stdin and write out in hexadecimal text format
# Incremental index number then one sample for each channel, per line

import sys
import serial
import select
import settings
import serial.tools.list_ports

BUFFER_SIZE = 32
BLOCK_SIZE = BUFFER_SIZE * 8
 
 
# on Ubuntu/Raspberry Pi, serial ports are in the form '/dev/ttyUSBx' where x is an integer 0-7
# on Windows, serial ports are in the form 'COMx' where x is an integer 1-8
def find_serial_device():
    ports = serial.tools.list_ports.comports()
    port_name = None
    for port in ports:
        description = port.description
        if 'board in fs mode' in description.lower():
            print(f'Found {port.description}.', file=sys.stderr)
            port_name = port.device
            break
    return port_name
 

def is_already_streaming(ser):
    # if we are already streaming, there should be at least one block of buffered data
    # waiting in the input stream. If not, then the select function will return empty
    # and we know that the input is blocking (empty).
    # if we are not already streaming, this test has the side effect of ensuring
    # that the input stream is drained properly before we tell Pico to go into streaming
    # mode
    for i in range(BLOCK_SIZE):
        if select.select([ser], [], [], 0)[0] != []:
            bs = ser.read(1)
            is_streaming = True
        else:
            is_streaming = False
            break
    return is_streaming


def enter_streaming_mode(ser):
    ser.write(bytes('STREAM\n', 'utf-8')) 
    ser.flush()


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
    port_name = find_serial_device()
    if port_name:
        try:
            ser = serial.Serial(port_name)
            print(f"reader.py, main(): Connected.", file=sys.stderr)
            # pico starts up in command mode by default, to allow debugging and special modes
            if not is_already_streaming(ser):
                enter_streaming_mode(ser)
            read_and_print(ser)
        except OSError:
            print(f"reader.py, main(): Serial error.", file=sys.stderr)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()


if __name__ == '__main__':
    main()


