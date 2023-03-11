import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys


# Buffer memory visible to both threads
BUFFER_SIZE = 256          # number of samples in a buffer
BUFFER_SIZE_BIT_MASK = BUFFER_SIZE * 8 - 1    # bit mask to circulate the buffer pointer


# pin and SPI setup
led = machine.Pin(25, Pin.OUT)
boardled = machine.Pin(15, Pin.OUT)
cs_adc = machine.Pin(1, Pin.OUT)
#sck_adc = machine.Pin(2, Pin.OUT)
#sdo_adc = machine.Pin(0, Pin.IN)
#sdi_adc = machine.Pin(3, Pin.OUT)
reset_adc = machine.Pin(5, Pin.OUT)
dr_adc = machine.Pin(4, Pin.IN)
reset_me = machine.Pin(14, Pin.IN)


spi_adc = machine.SPI(0,
                  baudrate = 6000000,
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
    set_and_verify_adc_register(spi, cs, 0x0d, bytes([0x24,0x60,0x50]))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    print("Setting configuration register CONFIG1 at 0x0e to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0e, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    
# interrupt handler for data ready pin
def adc_read_handler(dr_adc):
    global spi_buffer, active_buffer, in_ptr
    spi_adc.readinto(spi_buffer)
    active_buffer[in_ptr : in_ptr+8] = spi_buffer
    in_ptr = (in_ptr + 8) & BUFFER_SIZE_BIT_MASK    # % BUFFER_SIZE * 8


# interrupt handler for reset pin (commanded from Pi)    
def pico_restart(reset_me):
    machine.reset()
    
    
def initialise():
    # configure the ADC
    setup_adc(spi_adc, cs_adc, reset_adc)


# This function runs in Core 1
def print_data():
    global buffer1, buffer2, print_signal, running, for_real
    last_print_signal = 0
    while running == True:
        if print_signal == last_print_signal:
            continue
        # print signal has changed
        last_print_signal = print_signal
        if print_signal == 1:
            boardled.on()
            if for_real == True:
                sys.stdout.buffer.write(buffer1)
            else:
                sys.stdout.write('1')
            time.sleep(0.3)
            boardled.off()
        elif print_signal == 2:
            boardled.on()
            if for_real == True:
                sys.stdout.buffer.write(buffer2)
            else:
                sys.stdout.write('2')
            time.sleep(0.3)
            boardled.off()
        # There may be issues with automatic GC on Core 1
        # let's not allocate memory here
        # gc.collect()


def main():
    global buffer1, buffer2, print_signal, active_buffer, spi_buffer, in_ptr, running, for_real
    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    print('Initialising ADC...')
    initialise()

    time.sleep(5)
    print('Allocating bytearray buffers and setting flags...')    
    # two contiguous mutable bytearrays for samples
    buffer1 = bytearray(BUFFER_SIZE * 8)  # 2 bytes per channel, 4 channels
    buffer2 = bytearray(BUFFER_SIZE * 8)
    active_buffer = buffer1     # pointer to the currently active buffer

    spi_buffer = bytearray(8)   # temporary buffer for reading one sample via SPI
    in_ptr = 0                  # buffer cell pointer
    running = True              # flag for stopping the program in both cores
    print_signal = 0            # flag for core 0 to tell core 1 that it's time to print a buffer
    for_real = False            # flag to optionally run the program without trashing the terminal with binary data

    # the printing runs in parallel with the acquisition
    _thread.start_new_thread(print_data, ())  # Start Core 1 (printing)
   
    print('Setting up hardware interrupts...')
    # configure the interrupt handlers
    # bind the sampler handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=False)
    # bind the reset handler to a falling edge transition on the RESET ME pin
    reset_me.irq(trigger = Pin.IRQ_FALLING, handler = pico_restart, hard=True)
    time.sleep(5)

    # command ADC to repeatedly refresh ADC registers, by holding CS* low
    # pico will successively read these registers
    # each time the DR* pin is activated
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))

    print('Entering main loop...')
    while running == True:

        if in_ptr == 0:
            # time to flip the buffers and print
            if active_buffer == buffer1:
                active_buffer = buffer2
                print_signal = 1
            else:
                active_buffer = buffer1
                print_signal = 2

            # now wait until in_ptr has advanced
            while in_ptr == 0:
                1

 

# run from here
if __name__ == '__main__':
    try:
        main()
    except:
        print('Interrupted -- re-enabling auto garbage collector.')
        running = False
        cs_adc.value(1)
        gc.enable()
        


