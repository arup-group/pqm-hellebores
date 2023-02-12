import time
import machine
import binascii
import _thread
import sys
import random
import gc

# Using this article for hints
# https://bytesnbits.co.uk/multi-thread-coding-on-the-raspberry-pi-pico-in-micropython/

BUFFER_SIZE = 16   # samples

# pin and SPI setup
led = machine.Pin(25, machine.Pin.OUT)

# Buffer memory visible to both threads
# single contiguous mutable bytearray for previous samples
ring_buffer = bytearray(BUFFER_SIZE * 8)
in_ptr = 0             # buffer pointer used for charging the buffer
print_signal = ''      # flag variable to indicate which portion of the buffer to print
running = True         # flag variable to indicate if the program has terminated

def generate_data():
    global ring_buffer, in_ptr, print_signal
    ring_buffer[in_ptr:in_ptr+1] = random.randrange(65535).to_bytes(2, 'big')   
    ring_buffer[in_ptr+1:in_ptr+2] = random.randrange(65535).to_bytes(2, 'big')   
    ring_buffer[in_ptr+2:in_ptr+3] = random.randrange(65535).to_bytes(2, 'big')   
    ring_buffer[in_ptr+3:in_ptr+4] = random.randrange(65535).to_bytes(2, 'big')   
    in_ptr = (in_ptr+1) % (BUFFER_SIZE*8)
    # Indicate to the other thread when it's time to print
    if in_ptr == BUFFER_SIZE*4:
        print_signal = 'a'
    elif in_ptr == 0:
        print_signal = 'b'


def print_data():
    global ring_buffer, print_signal, running
    while running == True:
        # Select the correct portion of buffer
        if print_signal == 'a':
            print_signal = ''
            print(binascii.hexlify(ring_buffer[0:BUFFER_SIZE*4]))
        elif print_signal == 'b':
            print_signal = ''
            print(binascii.hexlify(ring_buffer[BUFFER_SIZE*4:BUFFER_SIZE*8]))
        # There may be issues with automatic GC on Core 1
        gc.collect()


def main():
    _thread.start_new_thread(print_data, ())
    while 1:
        generate_data()
        time.sleep(0.001)


# run from here
if __name__ == '__main__':
    try:
        print('Waiting for 5 seconds.')
        time.sleep(5)
        print('Proceeding...')
        main()
    except KeyboardInterrupt:
        running = False
        print('Interrupted')
        


