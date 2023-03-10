import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys




# pin and SPI setup
led = machine.Pin(25, Pin.OUT)
boardled = machine.Pin(15, Pin.OUT)
cs_adc = machine.Pin(1, Pin.OUT)
#sck_adc = machine.Pin(2, Pin.OUT)
#sdo_adc = machine.Pin(0, Pin.IN)
#sdi_adc = machine.Pin(3, Pin.OUT)
reset_adc = machine.Pin(5, Pin.OUT)
dr_adc = machine.Pin(4, Pin.IN)


spi_adc = machine.SPI(0,
                  baudrate = 8000000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = machine.Pin(2),
                  mosi = machine.Pin(3),
                  miso = machine.Pin(0))


def write_bytes(spi, cs, addr, bs):
    cs.value(0)
    spi.write(bytes([addr & 0b11111110]) + bs) # for writing, make sure lowest bit is cleared
    cs.value(1)
        
def read_bytes(spi, cs, addr, n):
    cs.value(0)
    spi.write(bytes([addr | 0b00000001])) # for reading, make sure lowest bit is set
    obs = spi.read(n)
    cs.value(1)
    return obs



# convert two's complement 24 bit binary to signed integer
def binary_to_signed_int(bs):
    v = int.from_bytes(bs, 'big')
    if bs[0] & (1<<7):    # negative number if most significant bit is set
        # adjust for negative number
        v = v - (1 << len(bs)*8)
    return v

def set_and_verify_adc_register(spi, cs, reg, bs):
    # The actual address byte leads with binary 01 and ends with the read/write bit (1 or 0).
    # The five bits in the middle are the 'register' address
    addr = 0x40 | (reg << 1)
    write_bytes(spi, cs, addr, bs)
    obs = read_bytes(spi, cs, addr, len(bs))
    print("Verify: " + " ".join(hex(b) for b in obs))
    

def setup_adc(spi, cs, reset):
    # Setup the MC3912 ADC
    # deselect the ADC
    cs_adc.value(1)
    
    # reset the adc
    reset_adc.value(0)
    time.sleep(0.1)
    reset_adc.value(1)
    time.sleep(0.1)
   
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # binary codes 101=32x, 100=16x, 011=8x, 010=4x, 001=2x, 000=1x
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000 
    print("Setting gain register 0x0b to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0b, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    # Set the status and communication register 0x0c
    print("Setting status and communication register STATUSCOM at 0x0c to 0x88, 0x00, 0x0f.")
    set_and_verify_adc_register(spi, cs, 0x0c, bytes([0x88,0x00,0x0f]))
    time.sleep(1)

    # Set the configuration register CONFIG0 at 0x0d
    print("Setting configuration register CONFIG0 at 0x0d to 0x24, 0x60, 0x50.")
    # 1st byte sets various ADC modes
    # 2nd byte sets OSR, for sampling speed: 0x20 = 15.625kSa/s, 0x40 = 7.8125kSa/s, 0x60 = 3.90625kSa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    set_and_verify_adc_register(spi, cs, 0x0d, bytes([0x24,0x40,0x50]))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    print("Setting configuration register CONFIG1 at 0x0e to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0e, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    
def read_all_adcs(spi, cs, dr):
    cs.value(0)
    spi.write(bytes([0b01000001]))
    acq = spi.read(8)   # bring back all readings (8 bytes)
    cs.value(1)
    return acq


def value_gauge(v, low, high):
    # scale readings over 50 characters
    out = '|'
    v_pos = round((v - low)/(high - low) * 50)
    for i in range(0, v_pos):
        out = out + '-'
    out = out + '>'
    for i in range(v_pos+1, 51):
        out = out + ' '
    out = out + '|'
    return out

def convert_to_channels(acq):
    raw = [0,0,0,0]
    signed_int = [0,0,0,0]
    # split up and process the readings
    for i in range(0,4):
        ch = acq[i*2 : i*2+2]
        raw[i] = int.from_bytes(ch, 'big')
        signed_int[i] = binary_to_signed_int(ch)
    return (raw, signed_int)           

# interrupt handler for data ready pin
def adc_read_handler(dr_adc):
    global read_buffer, writing_buffer, in_ptr
    spi_adc.readinto(read_buffer)
    writing_buffer[in_ptr*8 : in_ptr*8+8] = read_buffer
    in_ptr = (in_ptr + 1) & 512    # % BUFFER_SIZE*8
    
def simple_handler(dr_adc):
    # do nothing
    1
    
def initialise():
    # configure the ADC
    setup_adc(spi_adc, cs_adc, reset_adc)

    # command ADC to repeatedly read ADC registers, by holding CS* low
    # spi read commands will successively read these registers
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))


def display_update(ch, acq):
    # convert to signed integers
    r, s = convert_to_channels(acq)
    # print state of selected channel to console
    print(f'CH{ch} ' + value_gauge(s[ch], -32768, 32767) + f' {r[ch]:04x} {s[ch]:5d}', end='\r')


# This function runs in Core 1
def print_data():
    global buffer1, buffer2, print_signal, running, led
    while running == True:
        # Print the correct portion of buffer
        if print_signal == 'b1':
            print_signal = ''
            boardled.on()
            sys.stdout.write(binascii.hexlify(buffer1))
            boardled.off()
        elif print_signal == 'b2':
            print_signal = ''
            boardled.on()
            sys.stdout.write(binascii.hexlify(buffer2))
            boardled.off()
        # There may be issues with automatic GC on Core 1
        gc.collect()


def main():
    global buffer1, buffer2, print_signal, writing_buffer, in_ptr, running
    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    initialise()
 
    # fill ring buffers with dummy data
    for i in range(len(buffer1)):
        buffer1[i] = i % 256
        buffer2[i] = (i+50) % 256

    # the printing runs in parallel with the acquisition
    _thread.start_new_thread(print_data, ())  # Start Core 1 (printing)
   
    # configure the interrupt handler
    # bind the handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)

     
    while running == True:
        # until we have 2 cores working, cannot print out while sampling, so
        # every circulation of the buffer, stop sampling and print all of it out
        # print raw binary data
        # loop through every 2-byte integer value in the buffer, and convert to 4x hex characters
        #for i in range(0,BUFFER_SIZE*8,2):
        #    j = i*4
        #    v = current_buffer[i]*256 + current_buffer[i+1]   # get integer from 2 bytes
        #    output_buffer[j:j+3] = hex_mapper[v:v+3]          # copy hex bytestring from appropriate offset

        if in_ptr == 0:
            # stop reading ADC
            # dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = simple_handler)
            # illuminate the indicator LED
            #boardled.value(1)
            # print the buffer contents
            #sys.stdout.write(binascii.hexlify(reading_buffer))
            # flip the buffers
            if writing_buffer == buffer1:
                writing_buffer = buffer2
                print_signal = 'b1'
            else:
                writing_buffer = buffer1
                print_signal = 'b2'
            # gc.collect()
            #boardled.value(0)
            # re-enable ADC reads
            #dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler)
            # now wait until in_ptr has advanced
            while in_ptr == 0:
                1

 

# Buffer memory visible to both threads
BUFFER_SIZE = 64   # samples
# two contiguous mutable bytearrays for samples
buffer1 = bytearray(BUFFER_SIZE * 8)  # 2 bytes per channel, 4 channels
buffer2 = bytearray(BUFFER_SIZE * 8)
writing_buffer = buffer1
#output_buffer = bytearray(BUFFER_SIZE * 8 * 2)
#hex_mapper = bytearray(65536 * 2)


#for i in range(65536):
#    hex_mapper[i*2:i*2+3] = [ h+39 if h>57 else h for h in [ ((i & 0xf000) >> 12) + 48, \
#                                                             ((i & 0x0f00) >> 8) + 48, \
#                                                             ((i & 0x00f0) >> 4) + 48, \
#                                                             (i & 0x000f) + 48 ]]

# temporary buffer for one sample
read_buffer = bytearray(8)

in_ptr = 0
out_ptr = 0
running = True
print_signal = ''

# run from here
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted -- re-enabling auto garbage collector.')
        gc.enable()
        


