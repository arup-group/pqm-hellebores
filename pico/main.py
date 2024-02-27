import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys
from micropython import const


# constants are defined with the const() compilation hint to optimise performance
SPI_CLOCK_RATE  = const(8000000) 
DEBUG           = const(False)
SYNC_BYTES      = const(b'\x00\x00\x00\x00\x00\x00\x00\x00')
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# for performance optimisation, we hold shared information between the two
# CPU cores in a 'state' variable that is 12 bits wide
# 'state' is a bit field that holds the sample pointer and some mode flags
# MSB 0000xxxx:  mode flags 0001=QUIT, 0010=RESET, 0100=COMMAND, 1000=STREAMING
# LSB 0yyyyyyy:  sample pointer 0 to 127
# The following mask definitions enable us to perform certain assignments and tests
# on the state variable
QUIT          = const(0b000100000000)
RESET         = const(0b001000000000)
COMMAND       = const(0b010000000000)
STREAMING     = const(0b100000000000)
SAMPLE_MASK   = const(0b000001111111)
PAGE1         = const(0b100000000000)
PAGE2         = const(0b100001000000)
WRAP_MASK     = const(0b111101111111)

# Buffer memory
# Advantage if the buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE          = const(128)                # number of samples in a buffer
BUFFER_END_BIT_MASK  = const(BUFFER_SIZE - 1)    # 0b1111111 bit mask to circulate the buffer pointer
PAGE_FLIP_BIT_MASK   = const(BUFFER_SIZE // 2)   # 0b1000000 bit mask to flip the print flag


# pin setup
pico_led_pin     = machine.Pin(25, Pin.OUT)    # the led on the Pico
buffer_led_pin   = machine.Pin(15, Pin.OUT)    # the 'buffer' LED on the PCB
cs_adc_pin       = machine.Pin(1, Pin.OUT)     # chip select pin of the ADC
sck_adc_pin      = machine.Pin(2, Pin.OUT)     # serial clock for the SPI interface
sdi_adc_pin      = machine.Pin(3, Pin.OUT)     # serial input to ADC from Pico
ado_adc_pin      = machine.Pin(0, Pin.IN)      # serial output from ADC to Pico
reset_adc_pin    = machine.Pin(5, Pin.OUT)     # hardware reset of ADC commanded from Pico (active low)
dr_adc_pin       = machine.Pin(4, Pin.IN)      # data ready from ADC to Pico (active low)
reset_me_pin     = machine.Pin(14, Pin.IN)     # hardware reset of Pico (active low, implemented with interrupt handler)
mode_select_pin  = machine.Pin(26, Pin.IN)     # switch between streaming (LOW) and command mode (HIGH)


def configure_adc_spi_interface(sck_adc_pin, sdi_adc_pin, ado_adc_pin):
    global spi_adc_interface
    spi_adc_interface = machine.SPI(0,
                                    baudrate   = SPI_CLOCK_RATE,
                                    polarity   = 0,
                                    phase      = 0,
                                    bits       = 8,
                                    firstbit   = machine.SPI.MSB,
                                    sck        = sck_adc_pin,
                                    mosi       = sdi_adc_pin,
                                    miso       = ado_adc_pin)

def write_bytes(cs_adc_pin, addr, bs):
    global spi_adc_interface
    cs_adc_pin.value(0)
    spi_adc_interface.write(bytes([addr & 0b11111110]) + bs) # for writing, make sure lowest bit is cleared
    cs_adc_pin.value(1)
        
def read_bytes(cs_adc_pin, addr, n):
    global spi_adc_interface
    cs_adc_pin.value(0)
    spi_adc_interface.write(bytes([addr | 0b00000001])) # for reading, make sure lowest bit is set
    obs = spi_adc_interface.read(n)
    cs_adc_pin.value(1)
    return obs


def set_and_verify_adc_register(cs_adc_pin, reg, bs):
    global spi_adc_interface
    # The actual address byte leads with binary 01 and ends with the read/write bit (1 or 0).
    # The five bits in the middle are the 'register' address inside the ADC
    addr = 0x40 | (reg << 1)
    write_bytes(cs_adc_pin, addr, bs)
    obs = read_bytes(cs_adc_pin, addr, len(bs))
    if DEBUG:
        print("Verify: " + " ".join(hex(b) for b in obs))
    

def reset_adc(cs_adc_pin, reset_adc_pin):
    # deselect the ADC
    cs_adc_pin.value(1)
    # cycle the reset pin
    reset_adc_pin.value(0)
    time.sleep(0.1)
    reset_adc_pin.value(1)


# gains are in order of hardware channel: differential current, low range current, full range current, voltage
# refer to MCP3912 datasheet for behaviour of all the settings configured here
def setup_adc(cs_adc_pin, reset_adc_pin, adc_settings):
    global spi_adc_interface
    # Setup the MCP3912 ADC
    reset_adc(cs_adc_pin, reset_adc_pin)
    
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
        gain_bits = (G[adc_settings['gains'][3]] << 9) \
                  + (G[adc_settings['gains'][2]] << 6) \
                  + (G[adc_settings['gains'][1]] << 3) \
                  + G[adc_settings['gains'][0]] 
    except KeyError:
        gain_bits = (G['1x'] << 9) + (G['1x'] << 6) + (G['1x'] << 3) + G['1x']
    bs = [0x00, gain_bits >> 8, gain_bits & 0b11111111]
    if DEBUG:
        print('Setting gain register at 0b to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_and_verify_adc_register(cs_adc_pin, 0x0b, bytes(bs))
    
    # Set the status and communication register 0x0c
    # required bytes are:
    # ******* 0x98 = 0b10011000: 10 READ address increments on TYPES, 0 WRITE address does not increment ******,
    # ******* 1 DR_HIZ* DR is logic high when idle, 1 DR_LINK only 1 DR pulse is generated *******,
    # 0x88 = 0b10001000: 10 READ address increments on TYPES, 0 WRITE address does not increment,
    # 0 DR_HIZ* DR is high impedance when idle, 1 DR_LINK only 1 DR pulse is generated,
    # 0 WIDTH_CRC is 16 bit, 00 WIDTH_DATA is 16 bits
    # 0x00 = 0b00000000: 0 EN_CRCCOM CRC is disabled, 0 EN_INT CRC interrupt is disabled
    # 0x0f = 0b00001111: 1111 DRSTATUS data ready status bits for individual channels  
    bs = [0x88, 0x00, 0x0f]
    if DEBUG:
        print('Setting status and communication register STATUSCOM at 0c to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_and_verify_adc_register(cs_adc_pin, 0x0c, bytes(bs))

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets sampling rate via over-sampling ratio (OSR), possible OSR settings are as follows:
    # 0x00 = 32:  31.25 kSa/s
    # 0x20 = 64:  15.625 kSa/s
    # 0x40 = 128:  7.8125 kSa/s
    # 0x60 = 256:  3.90625 kSa/s
    # 0x80 = 512:  1.953 kSa/s
    # 0xa0 = 1024:   976 Sa/s
    # 0xc0 = 2048:   488 Sa/s
    # 0xe0 = 4096:   244 Sa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    osr_table = { '244':0xe0, '488':0xc0, '976':0xa0, '1.953k':0x80, '3.906k':0x60, '7.812k':0x40, '15.625k':0x20, '31.250k':0x00 }
    try:
        bs = [0x24, osr_table[adc_settings['sample_rate']], 0x50]
    except KeyError:
        bs = [0x24, osr_table['7.812k'], 0x50]
    if DEBUG:
        bs = [0x24, osr_table['976'], 0x50]   # SLOW DOWN sampling rate for debug mode
        print('Setting configuration register CONFIG0 at 0d to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_and_verify_adc_register(cs_adc_pin, 0x0d, bytes(bs))

    # Set the configuration register CONFIG1 at 0x0e
    bs = [0x00, 0x00, 0x00]
    if DEBUG:
        print('Setting configuration register CONFIG1 at 0e to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_and_verify_adc_register(cs_adc_pin, 0x0e, bytes(bs))
    
    
 
def configure_interrupts(reset_me_pin, mode_select_pin):
    # we need this helper function, because we can't easily assign to global variable
    # within a lambda expression
    def set_mode(required_mode):
        global state
        state = required_mode
    # we use hard interrupt for the DR* pin in STREAMING mode for timing reasons (configured elsewhere)
    # for these other interrupts, timing is less critical so we use soft interrupts
    reset_me_pin.irq(trigger = Pin.IRQ_FALLING, handler = lambda reset_me_pin: set_mode(RESET), hard=False)
    mode_select_pin.irq(trigger = Pin.IRQ_FALLING, handler = lambda mode_select_pin: set_mode(STREAMING), hard=False)
    mode_select_pin.irq(trigger = Pin.IRQ_RISING, handler = lambda mode_select_pin: set_mode(COMMAND), hard=False)


def configure_buffer_memory():
    global mv_acq, mv_cells
    # Make an array of memoryview objects that point into an acquire_buffer.
    # this makes it possible to access slices of the buffer without creating new objects
    # or allocating new memory when the main loop is running. In turn this allows us 
    # to switch off the garbage collector, allowing the program to continuously
    # sample without interruptions.
    # 2 bytes per channel, 4 channels
    mv_acq = memoryview(bytearray(BUFFER_SIZE * 8))
    # We now create a memoryview reference into each sample or slice of the buffer.
    # Later, the SPI read instruction will write into these memory slices directly.
    mv_cells = []
    for i in range(0, BUFFER_SIZE):
        mv_cells.append(memoryview(mv_acq[i*8 : i*8+8]))

        
# Interrupt handler for data ready pin (this pin is commanded from the ADC)
def adc_read_handler(_):
    global state
    # 'anding' the pointer with a bit mask that has binary '1' in the LSBs
    # makes the buffer pointer circulate to zero without needing an 'if' conditional
    # this means the instruction executes in constant time
    state = (state + 1) & WRAP_MASK


def start_adc():
    global spi_adc_interface
    if DEBUG:
        print('Starting the ADC...')
    # Bind the sampler handler to a falling edge transition on the DR pin
    dr_adc_pin.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)
    # Command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    cs_adc_pin.value(0)
    spi_adc_interface.write(bytes([0b01000001]))

def stop_adc():
    # Tell the ADC to stop sampling
    if DEBUG:
        print('Stopping the ADC...')
    dr_adc_pin.irq(handler=None)
    cs_adc_pin.value(1)


def print_buffer(bs):
    buffer_led_pin.on()
    if DEBUG:
        sys.stdout.write('\n')
        gc.collect()
    else:
        # write out the selected portion of buffer as bytes
        sys.stdout.buffer.write(bs)
        # the synchronisation string can possibly be used if the Pi is having trouble
        # with byte alignment
        #sys.stdout.buffer.write(SYNC_BYTES)
    buffer_led_pin.off()

########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
def streaming_loop_core_1():
    global state, spi_adc_interface, mv_cells
    # make a local variable to track the previous value of state
    p_state = state
    while state & STREAMING:
        if state != p_state:
            spi_adc_interface.readinto(mv_cells[state & SAMPLE_MASK])
            p_state = state
    if DEBUG:
        print('streaming_loop_core_1() exited')

#########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
def streaming_loop_core_0():    
    global state, mv_acq
    # Create memoryview objects that point to each half of the buffer.
    # This avoids having to make a copy of a portion of the buffer every
    # time we print -- this would waste time and leak memory that would need GC.
    page_break = BUFFER_SIZE * 8 // 2
    # divide the circular buffer into two pages
    mv_p1 = memoryview(mv_acq[:page_break])
    mv_p2 = memoryview(mv_acq[page_break:])
 
    while state & STREAMING:
        # wait while Core 1 is writing to page 1
        while state & PAGE1 == PAGE1:
            continue
        print_buffer(mv_p1)
        # wait while Core 1 is writing to page 2
        while state & PAGE2 == PAGE2:
            continue
        print_buffer(mv_p2)
    if DEBUG:
        print('streaming_loop_core_0() exited')


def process_command():
    # can insert code here to read commands from stdin, to receive new settings
    # assemble into the dictionary structure as below
    adc_settings = DEFAULT_ADC_SETTINGS
    time.sleep(0.2)
    return adc_settings


def main():
    global state, spi_adc_interface

    # adc_settings can be changed in COMMAND mode
    adc_settings = DEFAULT_ADC_SETTINGS

    # Wait for 30 seconds, provides debug opportunity to return pico to REPL if it is crashing 
    if DEBUG:
        print('PICO starting up.')
        print('Waiting for 30 seconds...')
    # Illuminate the green LED on Pico, while we're waiting
    pico_led_pin.on()
    time.sleep(30)
    pico_led_pin.off()

    if DEBUG:
        print('Configuring SPI interface to ADC.')
    configure_adc_spi_interface(sck_adc_pin, sdi_adc_pin, ado_adc_pin)

    if DEBUG:
        print('Configuring buffer memory.')
    configure_buffer_memory()

    if DEBUG:
        print('Configuring interrupts.')
    # NB, the DR (data ready) interrupt is configured elsewhere when we enter and exit
    # streaming mode
    configure_interrupts(reset_me_pin, mode_select_pin)

    # start with streaming mode and buffer pointer zero
    state = STREAMING
 
    if DEBUG:
        print('Entering mode switch loop.')

    # test all of the mode flags in turn
    while not state & QUIT:
        if state & STREAMING:
            if DEBUG:
                print('Entering streaming mode...')
            setup_adc(cs_adc_pin, reset_adc_pin, adc_settings)
            # we don't want GC pauses while streaming
            gc.disable()
            # start the ADC hardware interrupt (data ready pin DR*)
            start_adc(spi_adc_interface)
            # start the steaming loops on the two CPU cores
            _thread.start_new_thread(streaming_loop_core_1, ())
            streaming_loop_core_0()
            # after streaming ends, disable the sampling and enable the GC
            stop_adc()
            gc.enable()

        elif state & COMMAND:
            if DEBUG:
                print('Entering command mode...')
            # Receive new ADC settings, they will be applied to the ADC when we
            # resume STREAMING mode
            adc_settings = process_command()
        
        elif state & RESET:
            # The ISR has detected that the reset pin went low
            # Ensure the CS* pin on ADC is deselected
            cs_adc_pin.value(1)
            # Wait for the reset pin to return to inactive (high), then reset Pico
            while reset_me_pin.value() == 0:
                continue
            machine.reset()

    if DEBUG:
        print('Main function exited.')
    
# Run from here
if __name__ == '__main__':
    try:
        main()
    except:
        # an interrupt is received, or we set 'QUIT' mode
        if DEBUG:
            print('Interrupted.')
        # tell core 1 to stop
        state = QUIT
        # return system to idle state with GC enabled
        stop_adc()
        gc.enable()

