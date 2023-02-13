import time
import machine
import binascii
import _thread
import sys
import gc

# Using this article for hints
# https://bytesnbits.co.uk/multi-thread-coding-on-the-raspberry-pi-pico-in-micropython/

BUFFER_SIZE = 32   # samples



# Buffer memory visible to both threads
# single contiguous mutable bytearray for previous samples
# These variables are in global namespace and are available to both CPU cores
led = machine.Pin(25, machine.Pin.OUT)
ring_buffer = bytearray(BUFFER_SIZE * 8)
in_ptr = 0             # buffer pointer used for charging the buffer
print_signal = ''      # flag variable to indicate which portion of the buffer to print
running = True         # flag variable to indicate if the program has terminated
sample_value = 0       # dummy data for storing into the buffer


# This function runs periodically in Core 0
def generate_data():
    global ring_buffer, in_ptr, print_signal, sample_value
    ring_buffer[in_ptr:in_ptr+1] = sample_value.to_bytes(2, 'big')   
    ring_buffer[in_ptr+1:in_ptr+2] = sample_value.to_bytes(2, 'big')   
    ring_buffer[in_ptr+2:in_ptr+3] = sample_value.to_bytes(2, 'big')   
    ring_buffer[in_ptr+3:in_ptr+4] = sample_value.to_bytes(2, 'big')   
    in_ptr = (in_ptr+1) % (BUFFER_SIZE*8)
    sample_value = (sample_value+1) % 65536
    # Indicate to the other thread when it's time to print
    if in_ptr == BUFFER_SIZE*4:
        print_signal = 'a'
    elif in_ptr == 0:
        print_signal = 'b'



# This function runs in Core 1
def print_data():
    global ring_buffer, print_signal, running, led
    while running == True:
        # Print the correct portion of buffer
        if print_signal == 'a':
            print_signal = ''
            led.on()
            print(binascii.hexlify(ring_buffer[0:BUFFER_SIZE*4]))
            led.off()
        elif print_signal == 'b':
            print_signal = ''
            led.on()
            print(binascii.hexlify(ring_buffer[BUFFER_SIZE*4:BUFFER_SIZE*8]))
            led.off()
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
        # Flag to Core 1 that it's time to stop!
        running = False
        print('Interrupted')
        


