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
    'reset_me'    : Pin(14, Pin.IN)             # reset and restart Pico (active low)
}


def configure_reset_interrupt(mode='enable'):
    '''Implements hardware interrupt on pin 14 that cause the Pico to restart'''
    if mode == 'enable':
        pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: machine.reset(), hard=True)
    elif mode == 'disable':
        pins['reset_me'].irq(handler = None)


def read_command():
    '''Read command from remote terminal. String is returned without CRLF'''
    command_string = ''
    # Pico LED lights while waiting for commands
    pins['pico_led'].high()
    while True:
        # We read characters individually so that we can echo them back to the
        # controlling terminal as we receive them.
        # To achieve consistent behaviour on incoming line endings, need to
        # read from the binary buffer rather than the text one.
        c = sys.stdin.buffer.read(1).decode('utf-8')
        # ignore the \r character if present
        if c == '\r':
            continue
        # echo what we received back to the controlling terminal
        sys.stdout.write(c)
        # break out of the loop at end of line
        if c == '\n':
            break
        command_string += c
    pins['pico_led'].low()
    return command_string


def process_command(command_string):
    '''Implements the following commands: RESET, SAVE [filename] [length],
    SHA256 [filename], RENAME [from_name] [to_name], REMOVE [filename],
    LISTDIR, START [filename] [args], CAT [filename]''' 

    # make an array of words
    words = command_string.split(' ')
    # remove any empty words (eg caused by duplicate spaces)
    words = [ w for w in words if w != '' ]
    
    command_status = ''
    # do nothing for blank lines, don't handle as an error
    if len(words) == 0:
        return
    
    # retrieve the command and the arguments
    command = words[0]
    arguments = words[1:]

    # switch through the expected command key words
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
            remaining = int(length)
            # we read in chunks of no more than 1024 bytes, so that we
            # don't run out of memory
            CHUNK = 1024
            with open(filename, 'wb') as f:
                while remaining > 0:
                    if remaining > CHUNK:
                        f.write(sys.stdin.buffer.read(CHUNK))
                    else:
                        f.write(sys.stdin.buffer.read(remaining))
                    remaining -= CHUNK
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
            # sys is the only variable we export to the next process
            execfile(program_file)
            command_status = f'Program {program_file} exited normally.'
        except:
            command_status = f'Program {program_file} failed to start or quit with an error.'
    elif command == 'CAT' and len(arguments) == 1:
        filename = arguments[0]
        try:
            with open(filename) as f:
                file_contents = f.read()
            command_status = file_contents
        except:
            command_status = f'Failed to read {filename}'
    else:
        command_status = f'Error: failed to parse {words}.'
    print(command_status)

   
# Run from here
try:
    print('main.py started on Pico.')
    configure_reset_interrupt('enable')
    while True:
        command_string = read_command()
        process_command(command_string)
except KeyError:
    print('Interrupted.')
finally:
    pins['pico_led'].low()
    configure_reset_interrupt('disable')


