#!/usr/bin/env python3
# Copyright 2024 Arup
# MIT License

# Controls Pico via communicating with primitive command interface running in 'main.py'
# on Pico, that implements a limited number of text commands.

# On Ubuntu and similar systems, the serial ports have root user permissions.
# To change this, add ordinary user to the 'dialout' security group.
# sudo usermod -a -G dialout $USER

# Example command line invocations:
#
# Commands to start the Pico ADC streamer program with and without paramaters
#     ./pico_control.py --command="START stream.py 1x 1x 1x 1x 7.812k asm_thumb"
#     ./pico_control.py --command="START stream.py"
#
# Reset Pico via USB serial
#     ./pico_control.py --ctrl_c --no_response
#
# Reset Pico via GPIO and Pico interrupt handler
#     ./pico_control.py --hard_reset --no_response
#
# Manage files stored on the Pico flash disk
#     ./pico_control.py --command="RENAME stream.py stream_old.py"
#     ./pico_control.py --command="SAVE stream.py [length]" --send_file="stream.py"
#     ./pico_control.py --command="SHA256 stream.py"
#     ./pico_control.py --command="CAT stream.py"
#     ./pico_control.py --command="LISTDIR"
#     ./pico_control.py --command="REMOVE stream_old.py"
#
# Describe the machine and firmware level, and activate the bootloader to provide
# mass storage mode to load new firmware
#     ./pico_control.py --command="MACHINE"
#     ./pico_control.py --command="VERSION"
#     ./pico_control.py --command="BOOTLOADER"
#     ./pico_control.py --command="RESET


import time
import sys
import os
import argparse
import serial
import serial.tools.list_ports


class Pico_control:

    def __init__(self):
        self.ser = None
        self.port_name = None


    def find_serial_device(self):
        '''Determines the serial port that the Pico is connected to. On Ubuntu/Raspberry
        Pi, serial ports are in the form '/dev/ttyUSBx' or '/dev/ttyACMx', where x is an
        integer 0-7. On Windows, serial ports are in the form 'COMx' where x is an integer 1-8'''
        ports = serial.tools.list_ports.comports()
        for port in ports:
            description = port.description
            if 'board in fs mode' in description.lower() or 'serial' in description.lower():
                self.port_name = port.device
                break
        if self.port_name == None:
            print(f'{time.ctime()}: pico_control.py, Pico_control.find_serial_device(): '
                  f'Unable to find Pico on available serial ports.', file=sys.stderr)
            return False
        else:
            return True


    def connect(self):
        '''Connects to serial port with re-try and backoff in case other services are
        trying to probe the port.'''
        sleeping = [ 0.2, 0.3, 0.5, 1.0, 2.0 ]
        MAX_TRIES = 5
        this_try = 0
        # try to connect five times
        try:
            connection_success = False
            while this_try < MAX_TRIES:
                self.ser = serial.Serial(self.port_name, timeout=None)
                if self.ser.is_open:
                    connection_success = True
                    break
                time.sleep(sleeping[this_try])
                this_try = this_try + 1

        except:
            # Catches anything that goes wrong, then proceeds directly to finally block.
            pass

        finally:
            if connection_success:
                print(f'{time.ctime()} pico_control.py, Pico_Control:connect(): '
                      f'Connected to {self.port_name}.', file=sys.stderr)
                return True
            else:
                print(f'{time.ctime()}: pico_control.py, Pico_control.connect(): '
                      f'Failed to connect serial interface.', file=sys.stderr)
                return False


    def disconnect(self):
        try:
            if self.ser:
                self.ser.close()
            return True
        except:
            print(f'{time.ctime()}: pico_control.py, Pico_control.disconnect(): '
                  f'Error attempting to disconnect serial interface.', file=sys.stderr)
            return False


    def soft_reset(self):
        '''Pico software is configured to execute a hardware reset from software, if
        it is running and receives a CTRL-C (SIGINT) \x03 character'''
        try:
            self.ser.write(b'\x03')
            return True
        except:
            print(f'{time.ctime()}: pico_control.py, Pico_control.soft_reset(): '
                  f'Serial port to Pico is not open.', file=sys.stderr)
            return False
 

    def hard_reset(self):
        '''The Pico software has a hardware interrupt configured to monitor pin 6.
        When a rising edge is detected, the ISR will stop and restart the software.
        Running this function will cycle pin 6 thus triggering the reset routine.'''
        try:
            # We import on demand, so that the rest of the program will work on
            # non Raspberry Pi hardware
            import RPi.GPIO as gp
            RESET = 6
            gp.setmode(gp.BCM)
            gp.setup(RESET, gp.OUT)
            # make sure we start asserted low
            gp.output(RESET, False)
            # raise high to trigger the Pico ISR with a rising edge
            gp.output(RESET, True)
            # the Pico verifies that the signal remains asserted high for a period of time
            time.sleep(0.2)
            # return low
            gp.output(RESET, False)
            # We leave the output asserted low to enhance signal integrity on
            # the connection between Pi and Pico (both are ground referenced, but
            # have different power supply regulator sources).
            # If we need to release the GPIO, use gp.cleanup() however this will
            # leave the connection with a pull-high via a resistor in the Pi.
            return True
        except ModuleNotFoundError:
            print(f'{time.ctime()}, pico_control.py, Pico_control.hard_reset(): '
                  f'will only work on PQM hardware.', file=sys.stderr)
            return False


    def send_command(self, command):
        '''Writes the command to the serial interface'''
        try:
            command += '\n'
            self.ser.write(command.encode('utf-8'))
            return True
        except:
            print(f'{time.ctime()}: pico_control.py, Pico_control.send_command(): '
                  f'Serial port to Pico is not open.', file=sys.stderr)
            return False


    def send_file(self, filename):
        '''Writes the contents of a file to the serial interface.'''
        try:
            with open(filename, 'rb') as f:
                file_contents = f.read()
            self.ser.write(file_contents)
            return True
        except:
            print(f'{time.ctime()}, pico_control.py, Pico_control.send_file(): '
                  f'failed to send the contents of {filename}.')
            return False


    def receive_response(self):
        '''Receives response from serial. In case of short pauses, we try reading a
        few times before exiting. We break out immediately Pico says it is going to
        send a binary data stream.'''
        wait_attempts = 20            # wait up to 2 seconds for something to arrive
        response = ''
        try:
            while wait_attempts > 0:
                if self.ser.in_waiting:
                    _response = self.ser.readline().decode('utf-8').strip('\r\n')
                    wait_attempts = 10    # wait up to 1 second after we have got something
                    response += _response + '\n'
                    if _response == '**** STARTING BINARY STREAM ****':
                        break
                else:
                    time.sleep(0.1)
                    wait_attempts -= 1
        except:
            print(f'{time.ctime()}, pico_control.py, Pico_control.send_file(): '
                  f'failed to send the contents of {filename}.')
        finally:
            return response


def get_command_args():
    cmd_parser = argparse.ArgumentParser(description='Communicate with command server on Pico microcontroller.')
    cmd_parser.add_argument('--hard_reset', action='store_true', help='Toggles GPIO pin to reset the Pico via interrupt service')
    cmd_parser.add_argument('--ctrl_c', action='store_true', help='Send a CONTROL-C to Pico.')
    cmd_parser.add_argument('--command', help='Send a command string to Pico')
    cmd_parser.add_argument('--send_file', help='Send contents of file to Pico')
    cmd_parser.add_argument('--no_response', action='store_true', help='Transmit only, do not attempt to read response from Pico')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return (program_name, args)


def main():
    '''Reads command line and resets Pico and/or sends a command to the primitive
    server program running on Pico at startup.'''
    _, args = get_command_args()
    # Get an instance of Pico_control object
    pico = Pico_control()
    # if hard reset is requested, attempt to reset Pico before checking to
    # see if the serial interface is up/exists 
    if args.hard_reset:
        pico.hard_reset()
        time.sleep(2)
    pico.find_serial_device()
    if pico.port_name:
        try:
            # this order of processing allows 'SAVE' command to precede file transfer
            # in a combined command line
            pico.connect()
            if args.ctrl_c:
                pico.soft_reset()
                time.sleep(2)
            if args.command:
                pico.send_command(args.command)
            if args.send_file:
                pico.send_file(args.send_file)
            if not args.no_response:
                print(pico.receive_response(), end='')
        except OSError:
            print(f'{time.ctime()}, pico_control.py, main(): '
                  f'Serial comms error.', file=sys.stderr)
            sys.exit(1)
        finally:
            # make sure we have closed the port if it was opened
            if 'pico' in locals():
                pico.disconnect()


if __name__ == '__main__':
    main()


