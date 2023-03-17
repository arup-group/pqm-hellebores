import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys
from micropython import const

DEBUG_MODE           = const(True)

# Buffer memory
# Advantage if the buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells. However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE          = const(128)                   # number of samples in a buffer
BUFFER_END_BIT_MASK  = const(BUFFER_SIZE - 1)       # bit mask to circulate the buffer pointer
PAGE_FLIP_BIT_MASK   = const(BUFFER_SIZE // 2)      # bit mask to flip the print flag
PAGE1_END            = const(BUFFER_SIZE * 8 // 2)  # bytearray index to end of page 1 (first half of buffer)
PAGE2_END            = const(BUFFER_SIZE * 8)       # bytearray index to end of page 2 (second half of buffer)



# pin setup
pico_led     = machine.Pin(25, Pin.OUT)    # the led on the Pico
board_led    = machine.Pin(15, Pin.OUT)    # the 'buffer' LED on the PCB
cs_adc       = machine.Pin(1, Pin.OUT)     # chip select pin of the ADC
sck_adc      = machine.Pin(2, Pin.OUT)     # serial clock for the SPI interface
sdi_adc      = machine.Pin(3, Pin.OUT)     # serial input to ADC from Pico
sdo_adc      = machine.Pin(0, Pin.IN)      # serial output from ADC to Pico
reset_adc    = machine.Pin(5, Pin.OUT)     # hardware reset of ADC commanded from Pico (active low)
dr_adc       = machine.Pin(4, Pin.IN)      # data ready from ADC to Pico (active low)
reset_me     = machine.Pin(14, Pin.IN)     # hardware reset of Pico (active low, implemented with interrupt handler)

# SPI setup
spi_adc = machine.SPI(0,
                  baudrate   = 6000000,
                  polarity   = 0,
                  phase      = 0,
                  bits       = 8,
                  firstbit   = machine.SPI.MSB,
                  sck        = sck_adc,
                  mosi       = sdi_adc,
                  miso       = sdo_adc)


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
    # The five bits in the middle are the 'register' address inside the ADC
    addr = 0x40 | (reg << 1)
    write_bytes(spi, cs, addr, bs)
    obs = read_bytes(spi, cs, addr, len(bs))
    print("Verify: " + " ".join(hex(b) for b in obs))
    

def setup_adc(spi, cs, reset):
    # Setup the MC3912 ADC
    # deselect the ADC
    cs.value(1)
    
    # reset the adc
    reset.value(0)
    time.sleep(0.1)
    reset.value(1)
    time.sleep(0.1)
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    G = { '32x':0b101, '16x':0b100, '8x':0b011, '4x':0b010, '2x':0b001, '1x':0b000 } 
    g0 = G['32x']    # differential current
    g1 = G['2x']     # current 1
    g2 = G['2x']     # current 2
    g3 = G['1x']     # voltage
    gains = (g3 << 9) + (g2 << 6) + (g1 << 3) + g0 
    bs = [0x00, gains >> 8, gains & 0b11111111]
    print('Setting gain register at 0b to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0b, bytes(bs))
    time.sleep(1)
    
    # Set the status and communication register 0x0c
    bs = [0x88, 0x00, 0x0f]
    print('Setting status and communication register STATUSCOM at 0c to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0c, bytes(bs))
    time.sleep(1)

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets OSR, for sampling speed, OSR speeds as follows:
    # 0x00 = 32:  31.25 kSa/s
    # 0x20 = 64:  15.625 kSa/s
    # 0x40 = 128:  7.8125 kSa/s
    # 0x60 = 256:  3.90625 kSa/s
    # 0x80 = 512:  1.953 kSa/s
    # 0xa0 = 1024:   976 Sa/s
    # 0xc0 = 2048:   488 Sa/s
    # 0xe0 = 4096:   244 Sa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    SSP = { '244':0xe0, '488':0xc0, '976':0xa0, '1.953k':0x80, '3.906k':0x60, '7.812k':0x40, '15.625k':0x20, '31.250k':0x00 }
    bs = [0x24, SSP['7.812k'], 0x50]
    if DEBUG_MODE == True:
        bs[1] = SSP['976']    # slow down sampling for debug mode
    print('Setting configuration register CONFIG0 at 0d to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0d, bytes(bs))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    bs = [0x00, 0x00, 0x00]
    print('Setting configuration register CONFIG1 at 0e to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0e, bytes(bs))
    time.sleep(1)
    
    
# Interrupt handler for data ready pin (this pin is commanded from the ADC)
def adc_read_handler(dr_adc):
    global in_ptr
    # 'anding' the pointer with a bit mask that has binary '1' in the LSBs
    # makes the buffer pointer return to zero without needing an 'if' conditional
    # this means the instruction executes in constant time
    in_ptr = (in_ptr + 1) & BUFFER_END_BIT_MASK
 
        
# Interrupt handler for reset pin (this pin is commanded from Pi GPIO)    
def pico_restart_handler(reset_me):
    machine.reset()
    

# NB print_responder() runs on Core 1.
# It works by detecting the 'print_flag' shared from Core 0 changing value.
# This allows the print operation to synchronise to what is happening on Core 0,
# so that it only tries to print the portion of buffer that is not currently 
# being overwritten.
def print_responder():
    
    # Create memoryview objects that point to each half of the buffer.
    # This avoids having to make a copy of a portion of the buffer every
    # time we print, which would waste time and leak memory that would need GC.
    mv_p1 = memoryview(mv_acq[0:PAGE1_END])
    mv_p2 = memoryview(mv_acq[PAGE1_END:PAGE2_END])
    
    def print_buffer(bs):
        board_led.on()
        if DEBUG_MODE == True:
            # write out the selected portion of buffer as hexadecimal text
            sys.stdout.write(binascii.hexlify(bs))
            sys.stdout.write('\n')
        else:
            # write out the selected portion of buffer as bytes
            sys.stdout.buffer.write(bs)
        board_led.off()
    
    ########################################################
    ######### MAIN LOOP FOR CORE 1 STARTS HERE
    ########################################################
    while running == True:
        # wait while Core 0 is writing to page 1
        while (running == True) and (print_flag == 0):
            continue
        # flag flipped, print 'page 1'
        print_buffer(mv_p1)
        # now wait while Core 0 is writing to page 2
        while (running == True) and (print_flag == PAGE_FLIP_BIT_MASK):
            continue
        # flag flipped, print 'page 2'
        print_buffer(mv_p2)
                
    print('print_responder() exited on Core 1')


def main():
    global mv_acq, running, print_flag, in_ptr

    # Waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # Configure the ADC
    print('Initialising ADC...')
    setup_adc(spi_adc, cs_adc, reset_adc)
    time.sleep(1)

    print('Setting up RESET interrupt...')
    # bind the reset handler to a falling edge transition on the RESET ME pin
    reset_me.irq(trigger = Pin.IRQ_FALLING, handler = pico_restart_handler, hard=True)
    time.sleep(1)
    
    # Initial values for global variables that are shared with second core
    # and interrupt service routine
    running = True              # flag for running each core
 
    # Make an array of memoryview objects that point into an acquire_buffer.
    # this makes it possible to access slices of the buffer without creating new objects
    # or allocating new memory when the main loop is running. In turn this allows us 
    # to switch off the garbage collector, allowing the program to continuously
    # sample without interruptions.
    acquire_buffer = bytearray(BUFFER_SIZE * 8)   # 2 bytes per channel, 4 channels
    mv_acq = memoryview(acquire_buffer)
    # We now create a memoryview reference into each sample or slice of the buffer.
    # Later, the SPI read instruction will write into these memory slices directly.
    mv_cells = []
    for i in range(0, BUFFER_SIZE):
        mv_cells.append(memoryview(mv_acq[i*8 : i*8+8]))
    
    in_ptr = 0               # buffer cell pointer (for DR* interrupt service routine)
    print_flag = 0           # flag to indicate which chunk of the buffer to print


    # The print process runs on Core 1.
    print('Starting the print_responder() process on Core 1...')
    _thread.start_new_thread(print_responder, ())
    time.sleep(1)        # give it some time to initialise
    
    # Disable garbage collector, heap memory won't be automatically recovered.
    # From now on, we must avoid functions that repeatedly allocate memory.
    # eg we use hexlify in DEBUG_MODE, so must leave GC enabled for that case.
    if DEBUG_MODE == False:
        gc.disable()

    print('Setting up the ADC (DR*) interrupt...')
    # Bind the sampler handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)

    # Now command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))

 
    ########################################################
    ######### MAIN LOOP FOR CORE 0 STARTS HERE
    ########################################################
    print('Entering main loop...')
    # Manual garbage collect before we start looping
    gc.collect()
    # Local variable to help us detect when the ISR changes the value of
    # the buffer index in_ptr
    p = 0
    while running == True:
        # wait for the ISR to change the pointer value
        while in_ptr == p:
            continue
        # in_ptr has changed value: immediately read the new data from ADC
        spi_adc.readinto(mv_cells[in_ptr])
        # the pointer is volatile, so capture its value
        p = in_ptr
        # see if we have reached a 'page boundary' in the buffer
        # if so, instruct Core 1 CPU to print it
        # 'anding' the pointer with a bit mask that has binary '1' in the MSB
        # makes the print_flag value 'flip flop' without needing an 'if' conditional
        # this means the instruction will execute in constant time
        print_flag = p & PAGE_FLIP_BIT_MASK
 
    # Tell the ADC to stop sampling
    cs_adc.value(1)
    print('Core 0 exited.')
    
# Run from here
if __name__ == '__main__':
    try:
        main()
    except:
        print('Interrupted -- re-enabling auto garbage collector.')
        running = False
        cs_adc.value(1)
        gc.enable()



