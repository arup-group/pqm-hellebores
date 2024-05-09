#!/usr/bin/env python3
# Copyright 2024 Arup
# MIT License

# Controls Pico via communicating with primitive command interface running in 'main.py'
# on Pico, that implements a limited number of text commands.

# On Ubuntu and similar systems, the serial ports have root user permissions.
# To change this, add ordinary user to the 'dialout' security group.
# sudo usermod -a -G dialout $USER

import time
import sys
import os
import argparse
import serial
import serial.tools.list_ports


def find_serial_device():
    '''Determines the serial port that the Pico is connected to. On Ubuntu/Raspberry
    Pi, serial ports are in the form '/dev/ttyUSBx' or '/dev/ttyACMx', where x is an
    integer 0-7. On Windows, serial ports are in the form 'COMx' where x is an integer 1-8'''
    ports = serial.tools.list_ports.comports()
    port_name = None
    for port in ports:
        description = port.description
        if 'board in fs mode' in description.lower() or 'serial' in description.lower():
            print(f'Found {port.description}.', file=sys.stderr)
            port_name = port.device
            break
    return port_name
 

def get_command_args():
    global program_name
    cmd_parser = argparse.ArgumentParser(description='Communicate with command server on Pico microcontroller.')
    cmd_parser.add_argument('--hard_reset', action='store_true', help='Toggles GPIO pin to reset the Pico via interrupt service')
    cmd_parser.add_argument('--ctrl_c', action='store_true', help='Send a CONTROL-C to Pico.')
    cmd_parser.add_argument('--command', help='Send a command string to Pico')
    cmd_parser.add_argument('--send_file', help='Send contents of file to Pico')
    cmd_parser.add_argument('--no_response', action='store_true', help='Transmit only, do not attempt to read response from Pico')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return args


def hard_reset():
    '''The Pico software has a hardware interrupt configured to monitor pin 6.
    When a falling edge is detected, the ISR will stop and restart the software.
    Running this function will cycle pin 6 thus triggering the reset routine.'''
    try:
        # We import on demand, so that the rest of the program will work on
        # non Raspberry Pi hardware
        import RPi.GPIO as gp
        RESET = 6
        gp.setmode(gp.BCM)
        gp.setup(RESET, gp.OUT)
        time.sleep(0.1)
        gp.output(RESET, False)
        time.sleep(0.1)
        gp.output(RESET, True)
        gp.cleanup()
    except ModuleNotFoundError:
        print(f'{program_name}, hard_reset(): will only work on Raspberry Pi hardware.', file=sys.stderr)
    

def send_command(ser, command):
    '''Writes the command to the serial interface'''
    command += '\n'
    ser.write(command.encode('utf-8'))


def send_file(ser, filename):
    '''Writes the contents of a file to the serial interface.'''
    try:
        with open(filename, 'rb') as f:
            file_contents = f.read()
        ser.write(file_contents)
    except OSError:
        print(f'{program_name}, send_file(): failed to send the contents of {filename}.')
 

def receive_response(ser):
    '''Receives response from serial. In case of short pauses, we try reading a
    few times before exiting'''
    wait_attempts = 20
    while wait_attempts > 0:
        while ser.in_waiting:
            response = ser.readline().decode('utf-8').strip('\r\n')
            print(response)
            wait_attempts = 20
        time.sleep(0.1)
        wait_attempts -= 1


def main():
    '''Reads command line and resets Pico and/or sends a command to the primitive
    server program running on Pico at startup.'''
    global program_name
    args = get_command_args()
    # if hard reset is requested, attempt to reset Pico before checking to
    # see if the serial interface is up/exists 
    if args.hard_reset:
        hard_reset()
        time.sleep(0.1)
    port_name = find_serial_device()
    if port_name:
        try:
            ser = serial.Serial(port_name)
            if args.ctrl_c:
                ser.write(b'\x03')
            if args.command:
                send_command(ser, args.command)
            if args.send_file:
                send_file(ser, args.send_file)
            if not args.no_response:
                receive_response(ser)
        except OSError:
            print(f'{program_name}, main(): Serial comms error.', file=sys.stderr)
            sys.exit(1)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()


if __name__ == '__main__':
    main()


