import machine
import hashlib
import binascii
import sys
import os
import micropython



def save_file(filename, length):
    try:
        with open(filename, 'wb') as f:
            # disable CTRL-C handling on stdin during binary read
            micropython.kbd_intr(-1)
            f.write(sys.stdin.buffer.read(length))
            # restore CTRL-C
            micropython.kbd_intr(3)
        status = True
    except:
        status = False
    return status


def get_sha256(filename):
    try:
        with open(filename, 'rb') as f:
            sha = hashlib.sha256(f.read())
            bs = sha.digest()
            # value is a string containing the hex representation
            sha256_value = binascii.hexlify(bs).decode('utf-8')
    except:
        sha256_value = ''
    return sha256_value


def rename(filename_src, filename_dest):
    try:
        os.rename(filename_src, filename_dest)
        status = True
    except:
        status = False
    return status


def remove(filename):
    try:
        os.remove(filename)
        status = True
    except:
        status = False
    return status


def listdir(filename):
    try:
        dir_contents = os.listdir()
        status = dir_contents
    except:
        status = ''
    return status


def process_commands():

    while True:
        # Pico LED lights while waiting for commands
        pins['pico_led'].on()
        command_string = sys.stdin.readline()
        pins['pico_led'].off()

        # remove newline and CR and make an array of words
        words = command_string.strip('\n\r').split(' ')
        # remove any empty words (eg caused by duplicate spaces)
        words = [ w for w in words if w != '' ]
        
        command_status = 'OK'
        if len(words) == 0:
            continue    # do nothing for blank lines, don't handle as an error
        
        # retrieve the command and the arguments
        command = words[0]
        if len(words) > 1:
            arguments = words[1:]
        else:
            arguments = []

        if command == 'RESET' and len(arguments) == 0:
            machine.reset()
        elif command == 'SAVE' and len(arguments) == 2:
            filename, length = arguments
            if save_file(filename, length):
                command_status = 'OK'
            else:
                command_status = 'Failed to save file.'
        elif command == 'SHA256' and len(arguments) == 1:
            filename = arguments[0]
            sha256_value = get_sha256(filename)
            if sha256_value != '':
                command_status = sha256_value
            else:
                command_status = f'Failed to determine SHA256 for {filename}.'
        elif command == 'RENAME' and len(arguments) == 2:
            filename_src, filename_dest = arguments
            if rename(filename_src, filename_dest):
                command_status = 'OK'
            else
                command_status = 'Failed to rename file.'
        elif command == 'REMOVE' and len(arguments) == 1:
            filename = arguments[0]
            if remove(filename):
                command_status = 'OK'
            else:
                command_status = 'Failed to remove file.'
        elif command == 'LISTDIR' and len(arguments) == 0:
            dir_contents = listdir()
            if dir_contents != '':
                command_status = dir_contents
            else:
                command_status = 'Failed to determine contents of directory.'
        else:
            command_status = f'Error: failed to parse {words}'

   
# Run from here
try:
    print('file.py started on Pico.')
    process_commands()
except KeyError:
    print('Interrupted.')



