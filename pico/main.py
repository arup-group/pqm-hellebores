import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys
from micropython import const


# constants are defined with the const() compilation hint to optimise performance
# This is a configurable clock speed for comms on the SPI bus between Pico and ADC
SPI_CLOCK_RATE  = const(8000000) 
 
# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# this reduces the sample rate and the amount of data that is output to screen, and
# it prints some diagnostic progress info as the code proceeds
DEBUG           = const(False)

# A synchronisation string that can be transmitted at the beginning or end of each
# page of buffer data.
SYNC_BYTES      = const(b'\x00\x00\x00\x00\x00\x00\x00\x00')

# These adc settings can be adjusted via comms from the Pi when in COMMAND mode
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE       = const(128)


# For performance optimisation, we hold synchronisation information shared between
# the two CPU cores in a single 'state' variable that is 12 bits wide
# The following mask definitions enable us to perform certain assignments and tests
# on the state variable efficiently.
# MSB 0000xxxx:  mode flags 0001=QUIT, 0010=RESET, 0100=COMMAND, 1000=STREAMING
QUIT              = const(0b000100000000)      # tells both cores to exit
RESET             = const(0b001000000000)      # initiate a machine reset
COMMAND           = const(0b010000000000)      # receive commands to modify settings
STREAMING         = const(0b100000000000)      # fast ADC streaming using both cores
# LSB 0yyyyyyy:  sample pointer 0 to 127
# bit-and the state variable with SAMPLE_MASK to remove the mode bits
# bit-and the state variable with WRAP_MASK after incrementing it, to make the pointer circular
SAMPLE_MASK       = const(0b000001111111)      # mask to return just the cell pointer
WRAP_MASK         = const(0b111101111111)      # pointer increment from 127 wraps round to 0
# The following three constants are used to test whether a page boundary has been crossed, and therefore
# time to output the next page of sample buffer. The state variable is bit-anded with the PAGE_TEST
# mask and the result checked against STREAMING_PAGE1 and STREAMING_PAGE2 respectively. The test
# also breaks the waiting loop if a mode other than STREAMING is selected.
PAGE_TEST         = const(0b100001000000)      # test page number and streaming flag
STREAMING_PAGE1   = const(0b100000000000)      # bit6==0: cell pointer is in range 0-63, ie page 1
STREAMING_PAGE2   = const(0b100001000000)      # bit6==1: cell pointer is in range 64-127, ie page 2


# Pico pin setup
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


def configure_adc_spi_interface():
    global spi_adc_interface
    spi_adc_interface = machine.SPI(0,
                                    baudrate   = SPI_CLOCK_RATE,
                                    polarity   = 0,
                                    phase      = 0,
                                    bits       = 8,
                                    firstbit   = machine.SPI.MSB,
                                    sck        = pins['sck_adc'],
                                    mosi       = pins['sdi_adc'],
                                    miso       = pins['ado_adc'])


def set_adc_register(reg, bs):
    global spi_adc_interface
    # The actual address byte leads with binary 01 and ends with the read/write bit (1 or 0).
    # The five bits in the middle are the 'register' address inside the ADC
    addr = 0x40 | (reg << 1)

    # Activate the CS* pin to communicate with the ADC
    pins['cs_adc'].value(0)
    # for writing, make sure lowest bit is cleared, hence & 0b11111110
    spi_adc_interface.write(bytes([addr & 0b11111110]) + bs) 
    if DEBUG:
        # for reading, make sure lowest bit is set, hence | 0b00000001
        spi_adc_interface.write(bytes([addr | 0b00000001])) 
        obs = spi_adc_interface.read(len(bs))
        print("Verify: " + " ".join(hex(b) for b in obs))
    pins['cs_adc'].value(1)


def reset_adc():
    # deselect the ADC
    pins['cs_adc'].value(1)
    time.sleep(0.1)
    # cycle the reset pin
    pins['reset_adc'].value(0)
    time.sleep(0.1)
    pins['reset_adc'].value(1)


# gains are in order of hardware channel: differential current, low range current, full range current, voltage
# refer to MCP3912 datasheet for behaviour of all the settings configured here
def setup_adc(adc_settings):
    global spi_adc_interface
    # Setup the MCP3912 ADC
    reset_adc()
    
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    G = { '32x':0b101, '16x':0b100, '8x':0b011, '4x':0b010, '2x':0b001, '1x':0b000 }
    try:
        g3, g2, g1, g0 = [ G[k] for k in adc_settings['gains'] ]
    except KeyError:
        g3, g2, g1, g0 = [ G[k] for k in ['1x', '1x', '1x', '1x'] ]
    gain_bits = (g3 << 9) + (g2 << 6) + (g1 << 3) + g0
    bs = [0x00, gain_bits >> 8, gain_bits & 0b11111111]
    if DEBUG:
        print('Setting gain register at 0b to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_adc_register(0x0b, bytes(bs))
    
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
    set_adc_register(0x0c, bytes(bs))

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
    set_adc_register(0x0d, bytes(bs))

    # Set the configuration register CONFIG1 at 0x0e
    bs = [0x00, 0x00, 0x00]
    if DEBUG:
        print('Setting configuration register CONFIG1 at 0e to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
        time.sleep(1)
    set_adc_register(0x0e, bytes(bs))
    
    
 
def configure_interrupts():
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
    pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)
    # for these other interrupts, timing is less critical so we use soft interrupts
    pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: set_mode(RESET), hard=False)
    pins['mode_select'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: set_mode(STREAMING), hard=False)
    pins['mode_select'].irq(trigger = Pin.IRQ_RISING, handler = lambda _: set_mode(COMMAND), hard=False)


def disable_interrupts():
    pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    # leave the reset interrupt running
    # pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    pins['mode_select'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    pins['mode_select'].irq(trigger = Pin.IRQ_RISING, handler = None)


def configure_buffer_memory():
    # Make an array of memoryview objects that point into an acquire_buffer.
    # this makes it possible to access slices of the buffer without creating new objects
    # or allocating new memory when the main loop is running. In turn this allows us 
    # to switch off the garbage collector, allowing the program to continuously
    # sample without interruptions.
    # 2 bytes per channel, 4 channels
    mv_acq = memoryview(bytearray(BUFFER_SIZE * 8))

    # Create a memoryview reference into each sample or slice of the buffer.
    # Later, the SPI read instruction will write into these memory slices directly.
    mv_cells = []
    for i in range(0, BUFFER_SIZE):
        mv_cells.append(memoryview(mv_acq[i*8 : i*8+8]))

    # Also create memoryviews of each half of the circular buffer (ie two pages)
    half_mem = BUFFER_SIZE * 8 // 2
    mv_p1 = memoryview(mv_acq[:half_mem])
    mv_p2 = memoryview(mv_acq[half_mem:])
    return (mv_cells, mv_p1, mv_p2) 

def start_adc():
    global spi_adc_interface
    if DEBUG:
        print('Starting the ADC...')
    # Command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    pins['cs_adc'].value(0)
    spi_adc_interface.write(bytes([0b01000001]))

def stop_adc():
    # Tell the ADC to stop sampling
    if DEBUG:
        print('Stopping the ADC...')
    pins['cs_adc'].value(1)


########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
def streaming_loop_core_1(mv_cells):
    global state, spi_adc_interface

    # make a local variable to track the previous value of state
    p_state = state
    while state & STREAMING:
        # check to see if state has changed
        if state != p_state:
            # read out from the ADC immediately
            # SAMPLE_MASK masks the mode bits, just leaving the array index
            spi_adc_interface.readinto(mv_cells[state & SAMPLE_MASK])
            # save the new state
            p_state = state
    if DEBUG:
        print('streaming_loop_core_1() exited')

#########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
def streaming_loop_core_0(mv_p1, mv_p2): 
    global state

    def print_buffer(bs):
        pins['buffer_led'].on()
        if DEBUG:
            # when debugging, just print out a few of the samples as a byte string
            print(bytes(bs[:24]))
            gc.collect()
        else:
            # write out the selected portion of buffer as raw bytes
            sys.stdout.buffer.write(bs)
            # the synchronisation string could be used if the Pi is having trouble
            # with byte alignment, otherwise, omit it
            #sys.stdout.buffer.write(SYNC_BYTES)
        pins['buffer_led'].off()

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

def reset_microcontroller():
    # The ISR has detected that the reset pin went low
    # Ensure the CS* pin on ADC is deselected
    pins['cs_adc'].value(1)
    # Wait for the reset pin to return to inactive (high), then reset Pico
    while pins['reset_me'].value() == 0:
        continue
    machine.reset()


def process_command(adc_settings):
    global state
    # adc_settings are assembled into the dictionary structure as below
    #  { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }
    while state & COMMAND:
        command_string = sys.stdin.readline()
        words = command_string.split(' ')
        if len(words) == 0:
            continue
        elif len(words) == 1:
            token = words[0]
            if token == 'RESET':
                print('OK')
                reset_microcontroller()
            continue
        elif len(words) == 2:
            token, value = words
            if token == 'SAMPLERATE':
                print('OK')
                adc_settings['sample_rate'] = value
            continue
        elif len(words) == 5:
            token, g3, g2, g1, g0 = words
            if token == 'GAINS':
                print('OK')
                adc_settings['gains'] = [g3, g2, g1, g0] 
            continue
        else:
            print('Error')
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
    pins['pico_led'].on()
    time.sleep(30)
    pins['pico_led'].off()

    if DEBUG:
        print('Configuring SPI interface to ADC.')
    configure_adc_spi_interface()

    if DEBUG:
        print('Configuring buffer memory.')
    # mv_cells contains an array of memoryviews to individual samples in the buffer
    # mv_p1 and mv_p2 contain memoryviews to half of the buffer each
    mv_cells, mv_p1, mv_p2 = configure_buffer_memory()

    if DEBUG:
        print('Configuring interrupts.')
    configure_interrupts()

    # start with streaming mode and buffer pointer zero
    state = STREAMING
 
    if DEBUG:
        print('Entering mode switch loop.')

    # test all of the mode flags in turn
    while not (state & QUIT):
        if state & STREAMING:
            if DEBUG:
                print('Entering streaming mode...')
            setup_adc(adc_settings)
            # we don't want GC pauses while streaming
            gc.disable()
            # start the ADC continuous capture mode
            start_adc()
            # start the streaming loops on the two CPU cores
            # core 1 captures samples from the ADC, triggered by the DR* pin
            # core 0 prints blocks of samples from the capture buffer in two pages
            _thread.start_new_thread(streaming_loop_core_1, (mv_cells))
            streaming_loop_core_0(mv_p1, mv_p2)
            # after streaming ends, stop the ADC capture and enable the GC
            stop_adc()
            gc.enable()

        elif state & COMMAND:
            if DEBUG:
                print('Entering command mode...')
            # Receive new ADC settings, they will be transferred to the ADC when we
            # resume STREAMING mode
            adc_settings = process_command(adc_settings)
        
        elif state & RESET:
            reset_microcontroller()

    if DEBUG:
        print('Main function exited.')
    
# Run from here
if __name__ == '__main__':
    try:
        main()
    except KeyError:
        if DEBUG:
            print('Interrupted.')
    finally:
        # stop core 1 if it's still running
        state = QUIT
        stop_adc()
        disable_interrupts()
        gc.enable()


