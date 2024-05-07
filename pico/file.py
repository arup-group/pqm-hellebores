import machine
from machine import Pin
import hashlib
import binascii
import sys
import os
import micropython
import time


pins = {
    'pico_led'    : Pin(25, Pin.OUT),           # the led on the Pico
    'reset_adc'   : Pin(5, Pin.OUT, value=1),   # hardware reset of ADC commanded from Pico (active low)
}


def process_command():
    '''Implements readline from stdin and the following commands: RESET, SAVE [filename] [length],
    SHA256 [filename], RENAME [from_name] [to_name], REMOVE [filename], LISTDIR, START [filename] [args],
    CAT [filename] ''' 
    # Pico LED lights while waiting for commands
    pins['pico_led'].high()
    command_string = sys.stdin.readline()
    pins['pico_led'].low()

    # remove newline and CR and make an array of words
    words = command_string.strip('\n\r').split(' ')
    # remove any empty words (eg caused by duplicate spaces)
    words = [ w for w in words if w != '' ]
    
    command_status = ''
    if len(words) == 0:
        return    # do nothing for blank lines, don't handle as an error
    
    # retrieve the command and the arguments
    command = words[0]
    arguments = words[1:]

    if command == 'RESET' and len(arguments) == 0:
        # reset the ADC
        pins['reset_adc'].low()
        time.sleep(0.1)
        pins['reset_adc'].high()
        time.sleep(0.1)
        # reset the Pico
        machine.reset()
    elif command == 'SAVE' and len(arguments) == 2:
        filename, length = arguments
        try:
            # disable CTRL-C handling on stdin during binary read
            micropython.kbd_intr(-1)
            with open(filename, 'wb') as f:
                f.write(sys.stdin.buffer.read(int(length)))
             # restore CTRL-C
            micropython.kbd_intr(3)
            command_status = 'OK'
        except:
            command_status = f'Failed to save {filename}.'
    elif command == 'SHA256' and len(arguments) == 1:
        filename = arguments[0]
        try:
            with open(filename, 'rb') as f:
                sha = hashlib.sha256(f.read())
            bs = sha.digest()
            # result is a string containing the hex representation
            command_status = binascii.hexlify(bs).decode('utf-8')
        except:
            command_status = f'Failed to determine SHA256 for {filename}.'
    elif command == 'RENAME' and len(arguments) == 2:
        filename_src, filename_dest = arguments
        try:
            os.rename(filename_src, filename_dest)
            command_status = 'OK'
        except:
            command_status = 'Failed to rename file.'
    elif command == 'REMOVE' and len(arguments) == 1:
        filename = arguments[0]
        try:   
            os.remove(filename)
            command_status = 'OK'
        except:
            command_status = 'Failed to remove file.'
    elif command == 'LISTDIR' and len(arguments) == 0:
        try:
            dir_contents = os.listdir()
            command_status = dir_contents
        except:    
            command_status = 'Failed to determine contents of directory.'
    elif command == 'START' and len(arguments) > 0:
        program_file = arguments[0]
        try:
            if len(sys.argv) == 0:
                # we can't assign to sys.argv, but we can extend it
                sys.argv.extend(arguments)
            print(f'Starting {program_file} with sys.argv = {sys.argv}.')
            execfile(program_file)
            command_status = f'Program {program_file} exited normally.'
        except:
            command_status = f'Program {program_file} failed to start or quit with an error.'
    elif command == 'CAT' and len(arguments) == 1:
        program_file = arguments[0]
        try:
            with open(program_file) as f:
                program_code = f.read()
            command_status = program_code
        except:
            command_status = f'Failed to read {program_file}'
    else:
        command_status = f'Error: failed to parse {words}.'
    print(command_status)

   
# Run from here
try:
    print('main.py started on Pico.')
    while True:
        process_command()
except KeyError:
    print('Interrupted.')



