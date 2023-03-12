import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys

DEBUG_MODE = True

# Buffer memory
BUFFER_SIZE = 512                            # number of samples in a buffer
BUFFER_SIZE_BIT_MASK = BUFFER_SIZE * 8 - 1   # bit mask to circulate the buffer pointer
BUFFER_START_A = 0                           # beginning of 1st half of ring buffer
BUFFER_START_B = (BUFFER_SIZE * 8) // 2      # beginning of 2nd half


# pin and SPI setup
led = machine.Pin(25, Pin.OUT)             # this is the led on the Pico
boardled = machine.Pin(15, Pin.OUT)        # this is the 'buffer' LED on the PCB
cs_adc = machine.Pin(1, Pin.OUT)
sck_adc = machine.Pin(2, Pin.OUT)
sdi_adc = machine.Pin(3, Pin.OUT)
sdo_adc = machine.Pin(0, Pin.IN)
reset_adc = machine.Pin(5, Pin.OUT)
dr_adc = machine.Pin(4, Pin.IN)
reset_me = machine.Pin(14, Pin.IN)


spi_adc = machine.SPI(0,
                  baudrate = 6000000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = sck_adc,
                  mosi = sdi_adc,
                  miso = sdo_adc)


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
# this function runs in Core 1
def adc_read_handler(dr_adc):
    global spi_buffer, ring_buffer, in_ptr, buffer_boolean
    spi_adc.readinto(spi_buffer)
    ring_buffer[in_ptr : in_ptr+8] = spi_buffer
    # 'anding' the pointer with a bit mask makes the buffer pointer
    # return to zero without needing an 'if' conditional
    in_ptr = (in_ptr + 8) & BUFFER_SIZE_BIT_MASK    # BUFFER_SIZE * 8 - 1
    buffer_boolean = in_ptr & BUFFER_START_B        # flips polarity when we switch halves

        
# interrupt handler for reset pin (commanded from Pi)    
def pico_restart(reset_me):
    machine.reset()
    
    
def initialise():
    # configure the ADC
    setup_adc(spi_adc, cs_adc, reset_adc)


def print_buffer(buffer_section):
    if buffer_section == 1:
        boardled.on()
        if DEBUG_MODE == True:
            sys.stdout.buffer.write('1\n')
        else:
            # write out the first half of the buffer
            sys.stdout.buffer.write(ring_buffer[:BUFFER_START_B])
        boardled.off()
    elif buffer_section == 2:
        boardled.on()
        if DEBUG_MODE == True:
            sys.stdout.buffer.write('2\n')
        else:
            # write out the second half of the buffer
            sys.stdout.buffer.write(ring_buffer[BUFFER_START_B:])
        boardled.off()


# Runs on Core 1
def print_responder():
    print('Core 1 print_responder() starting, hello...')
    while running == True:
        while buffer_boolean == True:
            continue
        print_buffer(2)
        while buffer_boolean == False:
            continue
        print_buffer(1)        
    print('print_responder() exited on Core 1')


def main():
    global running, spi_buffer, ring_buffer, in_ptr, buffer_boolean
    running = True
    in_ptr = 0
    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    print('Initialising ADC...')
    initialise()
    time.sleep(1)

    print('Setting up RESET interrupt...')
    # configure the interrupt handlers
    # bind the reset handler to a falling edge transition on the RESET ME pin
    reset_me.irq(trigger = Pin.IRQ_FALLING, handler = pico_restart, hard=True)
    time.sleep(1)
        
    spi_buffer = bytearray(8)   # temporary buffer for reading one sample via SPI
    ring_buffer = bytearray(BUFFER_SIZE * 8)  # 2 bytes per channel, 4 channels
    in_ptr = 0                  # buffer cell pointer
    buffer_boolean = 0          # indicates which half of buffer is active (writing)
    # now command ADC to repeatedly refresh ADC registers, by holding CS* low
    # pico will successively read these registers
    # each time the DR* pin is activated
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))

    # the print process runs on Core 1
    print('Starting the print process on Core 1...')
    _thread.start_new_thread(print_responder, ())  # Start Core 1 (printing)
    #time.sleep(1)

    print('Setting up the ADC (DR*) interrupt...')
    # bind the sampler handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=False)

    # a do nothing loop now runs in idle time until the program is stopped
    print('Entering main loop...')
            
    while running == True:
        continue
    # finish sampling
    cs_adc.value(1)
    print('Core 0 exited.')
    
# run from here
if __name__ == '__main__':
    try:
        main()
    except:
        print('Interrupted -- re-enabling auto garbage collector.')
        running = False
        cs_adc.value(1)
        gc.enable()
        


