import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys


BUFFER_SIZE = 1024   # samples

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
                  baudrate = 6000000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = machine.Pin(2),
                  mosi = machine.Pin(3),
                  miso = machine.Pin(0))

def reset_adc_chip():
    reset_adc.value(0)
    time.sleep(0.1)
    reset_adc.value(1)
    
    
    
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
    reset_adc_chip()
   
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # binary codes 101=32x, 100=16x, 011=8x, 010=4x, 001=2x, 000=1x
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    GAIN1  = 0b000
    GAIN2  = 0b001
    GAIN4  = 0b010
    GAIN8  = 0b011
    GAIN16 = 0b100
    GAIN32 = 0b101
    gain0 = GAIN32
    gain1 = GAIN32
    gain2 = GAIN32
    gain3 = GAIN1
    gains_combined = (gain3 << 9) + (gain2 << 6) + (gain1 << 3) + gain0
    gain_lsb = gains_combined & 0b11111111
    gain_hsb = gains_combined >> 8
    print("Setting gain register 0x0b to 0x00, " + hex(gain_hsb) + ", " + hex(gain_lsb) + ".")
    set_and_verify_adc_register(spi, cs, 0x0b, bytes([0x00, gain_hsb, gain_lsb]))
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
    set_and_verify_adc_register(spi, cs, 0x0d, bytes([0x24,0x60,0x50]))
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
    global read_buffer, ring_buffer, in_ptr
    spi_adc.readinto(read_buffer)
    ring_buffer[in_ptr*8 : in_ptr*8+8] = read_buffer
    in_ptr = (in_ptr + 1) & 0b1111111111    # % BUFFER_SIZE
    
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


def main():
    global ring_buffer, in_ptr, out_ptr
    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    initialise()
    
    # configure the interrupt handler
    # bind the handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)

    # ******* MAKE ANOTHER irq HANDLER HERE, TO LISTEN FOR THE CM/SM* PIN CHANGING POLARITY
    # dr_cmsm.irq(trigger = Pin.IRQ_HIGH, handler = adc_read_handler, hard=True)
    
    #  disable automatic garbage collection to improve performance
    # may not need to do this anymore now that we have hard interrupts
    # gc.disable()

    
    while True:
        # until we have 2 cores working, cannot print out while sampling, so
        # every circulation of the buffer, stop sampling and print all of it out
        if in_ptr == 0:
            # stop reading ADC
            dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = simple_handler)
            # illuminate the indicator LED
            boardled.value(1)
            # print the buffer contents
            print(binascii.hexlify(ring_buffer))
            # gc.collect()
            boardled.value(0)
            # re-enable ADC reads
            dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler)
            # now wait until in_ptr has advanced
            while in_ptr == 0:
                1


# Buffer memory visible to both threads
# single contiguous mutable bytearray for previous samples
ring_buffer = bytearray(BUFFER_SIZE * 8)
# temporary buffer for one sample
read_buffer = bytearray(8)

in_ptr = 0
out_ptr = 0

# run from here
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted -- re-enabling auto garbage collector.')
        gc.enable()
        


