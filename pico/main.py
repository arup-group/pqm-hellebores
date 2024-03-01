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
DEBUG           = const(True)
SYNC_BYTES      = const(b'\x00\x00\x00\x00\x00\x00\x00\x00')
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# Buffer memory
# Buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE       = const(128)                 # number of samples in a buffer


# For performance optimisation, we hold synchronisation information shared between
# the two CPU cores in a 'state' variable that is 12 bits wide
# The following mask definitions enable us to perform certain assignments and tests
# on the state variable efficiently.
# MSB 0000xxxx:  mode flags 0001=QUIT, 0010=RESET, 0100=COMMAND, 1000=STREAMING
QUIT              = const(0b000100000000)      # tells both cores to exit
RESET             = const(0b001000000000)      # initiate a machine reset
COMMAND           = const(0b010000000000)      # receives commands to modify settings
STREAMING         = const(0b100000000000)      # fast ADC streaming using both cores
# LSB 0yyyyyyy:  sample pointer 0 to 127
SAMPLE_MASK       = const(0b000001111111)      # mask to return just the cell reference
WRAP_MASK         = const(0b111101111111)      # cell increment from 127 wraps round to 0
# The following three constants are used to test whether a page boundary has been crossed, and therefore
# time to output the next page of sample buffer. The state variable is bit-anded with the PAGE_TEST
# mask and the result checked against STREAMING_PAGE1 and STREAMING_PAGE2 respectively. The test
# also breaks the waiting loop if a mode other than STREAMING is selected.
PAGE_TEST         = const(0b100001000000)      # test page number and streaming flag
STREAMING_PAGE1   = const(0b100000000000)      # bit6=0: cell pointer is in range 0-63, ie page 1
STREAMING_PAGE2   = const(0b100001000000)      # bit6=1: cell pointer is in range 64-127, ie page 2


# pin setup
pins = {
    'pico_led'    : machine.Pin(25, Pin.OUT),  # the led on the Pico
    'buffer_led'  : machine.Pin(15, Pin.OUT),  # the 'buffer' LED on the PCB
    'cs_adc'      : machine.Pin(1, Pin.OUT),   # chip select pin of the ADC
    'sck_adc'     : machine.Pin(2, Pin.OUT),   # serial clock for the SPI interface
    'sdi_adc'     : machine.Pin(3, Pin.OUT),   # serial input to ADC from Pico
    'ado_adc'     : machine.Pin(0, Pin.IN),    # serial output from ADC to Pico
    'reset_adc'   : machine.Pin(5, Pin.OUT),   # hardware reset of ADC commanded from Pico (active low)
    'dr_adc'      : machine.Pin(4, Pin.IN),    # data ready from ADC to Pico (active low)
    'reset_me'    : machine.Pin(14, Pin.IN),   # hardware reset of Pico (active low, implemented with interrupt handler)
    'mode_select' : machine.Pin(26, Pin.IN)    # switch between streaming (LOW) and command mode (HIGH)
}

#
#pico_led_pin     = machine.Pin(25, Pin.OUT)    # the led on the Pico
#buffer_led_pin   = machine.Pin(15, Pin.OUT)    # the 'buffer' LED on the PCB
#cs_adc_pin       = machine.Pin(1, Pin.OUT)     # chip select pin of the ADC
#sck_adc_pin      = machine.Pin(2, Pin.OUT)     # serial clock for the SPI interface
#sdi_adc_pin      = machine.Pin(3, Pin.OUT)     # serial input to ADC from Pico
#ado_adc_pin      = machine.Pin(0, Pin.IN)      # serial output from ADC to Pico
#reset_adc_pin    = machine.Pin(5, Pin.OUT)     # hardware reset of ADC commanded from Pico (active low)
#dr_adc_pin       = machine.Pin(4, Pin.IN)      # data ready from ADC to Pico (active low)
#reset_me_pin     = machine.Pin(14, Pin.IN)     # hardware reset of Pico (active low, implemented with interrupt handler)
#mode_select_pin  = machine.Pin(26, Pin.IN)     # switch between streaming (LOW) and command mode (HIGH)
#

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
    G = { '32x':0b101, '16x':0b100, '8x':0b011, '4x':0b010, '2x':0b001, '1x':0b000 }
    try:
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
    
    
 
def configure_interrupts(dr_adc_pin, reset_me_pin, mode_select_pin):
    # Interrupt handler for data ready pin (this pin is commanded from the ADC)
    def adc_read_handler(_):
        global state
        # 'anding' the pointer with a bit mask that has binary '0' in the bit above the
        # largest buffer pointer makes the buffer pointer circulate to zero without needing
        # an 'if' conditional: this means the instruction executes in constant time
        state = (state + 1) & WRAP_MASK

    # we need this helper function, because we can't easily assign to global variable
    # within a lambda expression
    def set_mode(required_mode):
        global state
        state = required_mode

    # Bind the ADC sampler handler to a falling edge transition on the DR pin
    # we use hard interrupt for the DR* pin to maintain tight timing
    dr_adc_pin.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)
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


def start_adc(cs_adc_pin):
    global spi_adc_interface
    if DEBUG:
        print('Starting the ADC...')
    # Command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    cs_adc_pin.value(0)
    spi_adc_interface.write(bytes([0b01000001]))

def stop_adc(cs_adc_pin):
    # Tell the ADC to stop sampling
    if DEBUG:
        print('Stopping the ADC...')
    cs_adc_pin.value(1)


########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
def streaming_loop_core_1():
    global state, spi_adc_interface, mv_cells

    # make a local variable to track the previous value of state
    p_state = state
    while state & STREAMING:
        # check to see if state has changed
        if state != p_state:
            # read out from the ADC immediately
            # SAMPLE_MASK eliminates the mode bits, just leaving the cell reference
            spi_adc_interface.readinto(mv_cells[state & SAMPLE_MASK])
            # save the new state
            p_state = state
    if DEBUG:
        print('streaming_loop_core_1() exited')

#########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
def streaming_loop_core_0(buffer_led_pin):    
    global state, mv_acq

    def print_buffer(bs):
        buffer_led_pin.on()
        if DEBUG:
            # when debugging, just print out a few of the samples as a byte string
            print(bs[:24])
            gc.collect()
        else:
            # write out the selected portion of buffer as bytes
            sys.stdout.buffer.write(bs)
            # the synchronisation string could be used if the Pi is having trouble
            # with byte alignment, otherwise, omit it
            #sys.stdout.buffer.write(SYNC_BYTES)
        buffer_led_pin.off()

    # divide the circular buffer into two pages
    half_mem = BUFFER_SIZE * 8 // 2
    mv_p1 = memoryview(mv_acq[:half_mem])
    mv_p2 = memoryview(mv_acq[half_mem:])
 
    while state & STREAMING:
        # wait while Core 1 is writing to page 1
        while (state & PAGE_TEST) == STREAMING_PAGE1:
            continue
        print_buffer(mv_p1)
        # wait while Core 1 is writing to page 2
        while (state & PAGE_TEST) == STREAMING_PAGE2:
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
    #configure_adc_spi_interface(sck_adc_pin, sdi_adc_pin, ado_adc_pin)
    configure_adc_spi_interface(pins['sck_adc'], pins['sdi_adc'], pins['ado_adc'])

    if DEBUG:
        print('Configuring buffer memory.')
    configure_buffer_memory()

    if DEBUG:
        print('Configuring interrupts.')
    configure_interrupts(pins['dr_adc'], pins['reset_me'], pins['mode_select'])

    # start with streaming mode and buffer pointer zero
    state = STREAMING
 
    if DEBUG:
        print('Entering mode switch loop.')

    # test all of the mode flags in turn
    while not (state & QUIT):
        if state & STREAMING:
            if DEBUG:
                print('Entering streaming mode...')
            setup_adc(pins['cs_adc'], pins['reset_adc'], adc_settings)
            # we don't want GC pauses while streaming
            gc.disable()
            # start the ADC hardware interrupt (data ready pin DR*)
            start_adc(pins['cs_adc'])
            # start the steaming loops on the two CPU cores
            _thread.start_new_thread(streaming_loop_core_1, ())
            streaming_loop_core_0(pins['buffer_led'])
            # after streaming ends, disable the sampling and enable the GC
            stop_adc(pins['cs_adc'])
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
            pins['cs_adc'].value(1)
            # Wait for the reset pin to return to inactive (high), then reset Pico
            while pins['reset_me'].value() == 0:
                continue
            machine.reset()

    if DEBUG:
        print('Main function exited.')
    
# Run from here
if __name__ == '__main__':
    main()
    if DEBUG:
        print('Interrupted.')
    # stop core 1 if it's still running
    state = QUIT
    stop_adc(pins['cs_adc'])
    gc.enable()
