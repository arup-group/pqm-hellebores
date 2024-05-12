# To run on Raspberry Pi Pico microcontroller, communicating with MCP3912
# 4-channel ADC via SPI serial interface, and host computer via USB serial
# interface. The code provides a circular buffer for precisely timed incoming
# measurements signalled by the ADC (via the data ready, DR* pin), and sends
# output from the buffer in blocks of 64x4x16 bit integer values.

import time
import machine
from machine import Pin
import gc
import _thread
import sys
from micropython import const


# some constants are defined with the const() compilation hint to optimise performance
# SPI_CLOCK_RATE is a configurable clock speed for comms on the SPI bus between
# Pico and ADC
SPI_CLOCK_RATE = 8000000 
 
# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# this reduces the sample rate and the amount of data that is output to screen, and
# it prints some diagnostic progress info as the code proceeds
DEBUG = const(False)

# These adc settings can be adjusted via comms from the Pi via command line arguments
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE = 128

# For performance optimisation, we hold synchronisation information shared between
# the two CPU cores in a single 'state' variable that is 10 bits wide
# The following mask definitions enable us to perform certain assignments and tests
# on the state variable efficiently.
STOPPED           = const(0b0000000000)      # tells both cores to exit
RESET             = const(0b0100000000)      # initiate a machine reset
STREAMING         = const(0b1000000000)      # fast ADC streaming using both cores

# LSB 0yyyyyyy:  sample pointer 0 to 127
# bit-and the state variable with SAMPLE_MASK to remove the mode bits, to access 
# just the buffer pointer
# bit-and the state variable with WRAP_MASK after incrementing it, to make the pointer circular
SAMPLE_MASK       = const(0b0001111111)      # mask to return just the cell pointer
WRAP_MASK         = const(0b1101111111)      # pointer increment from 127 wraps round to 0

# The following three constants are used to test whether a page boundary has been crossed, and therefore
# time to output the next page of sample buffer. The state variable is bit-anded with the PAGE_TEST
# mask and the result checked against STREAMING_PAGE0 and STREAMING_PAGE1 respectively. The test
# also breaks the waiting loop if a mode other than STREAMING is selected.
PAGE_TEST         = const(0b1001000000)      # test page number and streaming flag
WRITING_PAGE0     = const(0b1000000000)      # bit6==0: cell pointer is in range 0-63, ie page 0
WRITING_PAGE1     = const(0b1001000000)      # bit6==1: cell pointer is in range 64-127, ie page 1


def configure_pins():
    '''Pico pin setup, referenced by a global variable 'pins'. We initialise with the
    RESET* and CS* pins high, since they are active low and we don't want them to operate
    until needed.'''
    global pins
    pins = {
        'pico_led'    : Pin(25, Pin.OUT, value=0),  # the led on the Pico
        'buffer_led'  : Pin(15, Pin.OUT, value=0),  # the 'buffer' LED on the PCB
        'cs_adc'      : Pin(1, Pin.OUT, value=1),   # chip select pin of the ADC (active low)
        'sck_adc'     : Pin(2, Pin.OUT),            # serial clock for the SPI interface
        'sdi_adc'     : Pin(3, Pin.OUT),            # serial input to ADC from Pico
        'sdo_adc'     : Pin(0, Pin.IN),             # serial output from ADC to Pico
        'reset_adc'   : Pin(5, Pin.OUT, value=1),   # hardware reset of ADC commanded from Pico (active low)
        'dr_adc'      : Pin(4, Pin.IN),             # data ready from ADC to Pico (active low)
        'reset_me'    : Pin(14, Pin.IN),            # reset and restart Pico (active low)
        'mode_select' : Pin(26, Pin.IN)             # switch between streaming (LOW) and command mode (HIGH)
    }
    

def configure_adc_spi_interface():
    '''Sets up the Pico SPI interface using selected hardware pins. This will be
    used to communicate with the ADC.'''
    global spi_adc_interface

    spi_adc_interface = machine.SPI(0,
                                    baudrate   = SPI_CLOCK_RATE,
                                    polarity   = 0,
                                    phase      = 0,
                                    bits       = 8,
                                    firstbit   = machine.SPI.MSB,
                                    sck        = pins['sck_adc'],
                                    mosi       = pins['sdi_adc'],
                                    miso       = pins['sdo_adc'])


def set_adc_register(reg, bs):
    '''Write, and in DEBUG mode verify, a value into selected register of the
    ADC.'''
    # The actual address byte leads with binary 01 and ends with the read/write
    # bit (1 or 0). The five bits in the middle are the 'register' address inside
    # the ADC.
    addr = 0x40 | (reg << 1)

    # Activate the CS* pin to communicate with the ADC
    pins['cs_adc'].low()
    # for writing, make sure lowest bit is cleared, hence & 0b11111110
    spi_adc_interface.write(bytes([addr & 0b11111110]) + bs) 
    pins['cs_adc'].high()
    if DEBUG:
        pins['cs_adc'].low()
        # for reading, make sure lowest bit is set, hence | 0b00000001
        spi_adc_interface.write(bytes([addr | 0b00000001])) 
        obs = spi_adc_interface.read(len(bs))
        pins['cs_adc'].high()
        print("Verify: " + " ".join(hex(b) for b in obs))
 

def reset_adc():
    '''Cycles the hardware reset pin of the ADC.'''
    # deselect the ADC
    pins['cs_adc'].high()
    # cycle the reset pin
    pins['reset_adc'].low()
    pins['reset_adc'].high()
    time.sleep(0.5)


def setup_adc(adc_settings):
    '''Setup the MCP3912 ADC. Refer to MCP3912 datasheet for detailed description of
    behaviour of all the settings configured here.'''
    reset_adc()
    
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    # gains are in order of hardware channel:
    # differential current, low range current, full range current, voltage
    G = { '32x':0b101, '16x':0b100, '8x':0b011, '4x':0b010, '2x':0b001, '1x':0b000 }
    try:
        g3, g2, g1, g0 = [ G[k] for k in adc_settings['gains'] ]
    except KeyError:
        g3, g2, g1, g0 = [ G[k] for k in ['1x', '1x', '1x', '1x'] ]
    gain_bits = (g3 << 9) + (g2 << 6) + (g1 << 3) + g0
    bs = [0x00, gain_bits >> 8, gain_bits & 0b11111111]
    if DEBUG:
        print('Setting gain register at 0b to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_adc_register(0x0b, bytes(bs))
    time.sleep(0.1)

    # Set the status and communication register 0x0c
    # required bytes are:
    # 0x88 = 0b10001000: 10 READ address increments on TYPES, 0 WRITE address does not
    # increment, 0 DR_HIZ* DR is high impedance when idle, 1 DR_LINK only 1 DR pulse is
    # generated, 0 WIDTH_CRC is 16 bit, 00 WIDTH_DATA is 16 bits.
    # 0x00 = 0b00000000: 0 EN_CRCCOM CRC is disabled, 0 EN_INT CRC interrupt is disabled
    # 0x0f = 0b00001111: 1111 DRSTATUS data ready status bits for individual channels  
    bs = [0x88, 0x00, 0x0f]
    if DEBUG:
        print('Setting status and communication register STATUSCOM at 0c to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_adc_register(0x0c, bytes(bs))
    time.sleep(0.1)

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets sampling rate via over-sampling ratio (OSR), possible OSR settings
    # are as follows:
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
        print('Setting configuration register CONFIG0 at 0d to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_adc_register(0x0d, bytes(bs))
    time.sleep(0.1)

    # Set the configuration register CONFIG1 at 0x0e
    bs = [0x00, 0x00, 0x00]
    if DEBUG:
        print('Setting configuration register CONFIG1 at 0e to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_adc_register(0x0e, bytes(bs))
    time.sleep(0.1)
    
    
 
def configure_interrupts(mode='enable'):
    '''Two interrupt handlers are set up, one for the DR* pin, for notifying Pico
    that new data is ready for reading from the ADC, and a reset command from the
    Pi, to help with run-time error recovery.'''

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

    if mode == 'enable':
        # Bind pin transitions to interrupt handlers.
        # We use hard interrupt for the DR* pin to maintain tight timing,
        # and for the RESET* pin so that the reset works even within a blocking
        # function (eg serial write). We defer the actual hardware reset until
        # cleanup has happened, including core 1 exiting
        pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)
        pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: set_mode(RESET), hard=True)

    elif mode == 'disable':
        pins['dr_adc'].irq(handler = None)
        pins['reset_me'].irq(handler = None)


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by a global variable acq_mv.'''
    global acq_mv

    # 2 bytes per channel, 4 channels
    # we use a memoryview to allow this to be sub-divided into cells and
    # pages in the streaming loops
    acq_mv = memoryview(bytearray(BUFFER_SIZE * 8))


def start_adc():
    '''Tell the ADC to start sampling in multiple-read mode. It's necessary for
    the CS pin to be held low from this point.'''
    if DEBUG:
        print('Starting the ADC...')
    # Command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    pins['cs_adc'].low()
    spi_adc_interface.write(bytes([0b01000001]))


def stop_adc():
    '''Tell the ADC to stop sampling.'''
    # Note that the DR* pin continues to cycle, so it's necessary to also stop
    # interrupts if we want to stop processing completely
    if DEBUG:
        print('Stopping the ADC...')
    pins['cs_adc'].high()


########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
def streaming_loop_core_1():
    '''Watches for change in state variable (caused the by interrupt handler)
    and reads new data from the ADC into memory.'''
    # Create a memoryview reference into each sample or slice of the buffer.
    # The SPI read instruction will write into these memory slices directly.
    cells_mv = []
    # 8 bytes each cell, stepping 8 bytes
    for m in range(0, BUFFER_SIZE*8, 8):
        cells_mv.append(memoryview(acq_mv[m:m+8]))

    # It's really important that SPI reads are timed correctly and don't
    # happen while the ADC is trying to latch in new data -- it will stop
    # working. At this point, we could be anywhere in the sampling cycle.
    # To help synchronise, we wait until 'state' changes once before
    # slipping into the data acquisition loop. 'p_state' is a variable that
    # helps us to detect when state changes value.
    p_state = state
    while state == p_state:
        continue
    # ok, a DR* pulse just happened, we're now ready to enter the loop. 
    p_state = state
    
    while state & STREAMING:
        # check to see if state has changed
        if state != p_state:
            # read out from the ADC *immediately*
            # SAMPLE_MASK masks the mode bits, just leaving the array index
            spi_adc_interface.readinto(cells_mv[state & SAMPLE_MASK])
            # save the new state
            p_state = state
    if DEBUG:
        print('streaming_loop_core_1() exited')


########################################################
def streaming_loop_core_0(): 
    '''Prints data from memory to stdout in 'half-buffer' chunks.'''
    # Create memoryviews of each half of the circular buffer (ie two pages)
    half_mem = BUFFER_SIZE // 2 * 8
    p0_mv = memoryview(acq_mv[:half_mem])
    p1_mv = memoryview(acq_mv[half_mem:])

    # This memory is only actually used in debug mode
    debug_blocks = 32
    debug_bs = [ bytearray(32) for i in range(debug_blocks) ]
    debug_block_counter = 0

    def _write_buffer_normal(bs):
        pins['buffer_led'].on()
            # write out the selected portion of buffer as raw bytes
            sys.stdout.buffer.write(bs)
        pins['buffer_led'].off()

    def _write_buffer_debug(bs):
        pins['buffer_led'].on()
            # We capture the first four samples of each buffer
            # Printing is slow, so we'll output them when finished.
            debug_mv[debug_sample_counter][:] = bs[:32]  
            debug_block_counter += 1
            if debug_block_counter == debug_blocks:
                state = STOPPED
        pins['buffer_led'].off()

    # select the writing function once at runtime
    if DEBUG:
        write_buffer = _write_buffer_debug
    else:
        write_buffer = _write_buffer_normal

    # Now loop...
    while state & STREAMING:
        # wait while Core 1 is writing to page 0
        while (state & PAGE_TEST) == WRITING_PAGE0:
            continue
        write_buffer(p0_mv)
        # wait while Core 1 is writing to page 1
        while (state & PAGE_TEST) == WRITING_PAGE1:
            continue
        write_buffer(p1_mv)

    if DEBUG:
        print('streaming_loop_core_0() exited.')
        print('Here are the contents of debug buffer memory:')
        for bs in debug_bs:
            h = binascii.hexlify(bs).decode('utf-8'))
            print(f'{h[0:8] h[8:16] h[16.24] h[24:32]')


def prepare_to_stream(adc_settings):
    '''Configures all the pre-requisities: pins, SPI interface, ADC settings
    circular buffer memory, interrupts and garbage collection.'''
    global state

    if DEBUG:
        print('Configuring pins, SPI interface to ADC, and buffer memory.')
    # This state variable is used everywhere to control program flow and the
    # location of the current 'cell' in the buffer memory.
    state = STREAMING

    # Hardware pins that will communicate with the ADC and the Raspberry Pi.
    configure_pins()

    # Interface to the ADC uses SPI protocol
    configure_adc_spi_interface()

    # Buffer memory is set up in a memoryview called acq_mv. Memoryview objects
    # allow read/write access to a block of memory. acq_mv is declared a
    # global variable so it can be reached by both CPU cores.
    configure_buffer_memory()

    if DEBUG:
        print('Configuring interrupts and starting ADC.')
    # ADC is responsible for sample timing. Every sample, it toggles the DR* pin.
    # An interrupt handler on Pico receives this pulse, so that the data can
    # be processed.
    configure_interrupts()

    # With everything on the Pico setup, we push some settings into the ADC...
    setup_adc(adc_settings)
    # ...and now tell it to start.
    start_adc()

    # We don't want garbage collection pauses while streaming, so we disable the
    # automatic GC.
    gc.disable()


def stream():
    '''Start the streaming loops on the two CPU cores, both accessing
    the same buffer memory. Core 1 captures samples from the ADC, triggered
    by the DR* pin. Core 0 prints blocks of samples from the capture buffer
    in two pages.'''
    if DEBUG:
        print('Starting streaming loops on both cores.')
    _thread.start_new_thread(streaming_loop_core_1, ())
    streaming_loop_core_0()
    # runs forever, unless reset pin is activated

    
def cleanup():
    '''For debugging, it's useful for the Pico to be returned to a quiescent
    state. This function stops core 1 that can interfere with proper operation
    of the Thonny IDE. It also disables the ADC prior to a machine reset.'''
    global state

    # stop core 1 if it's still running
    if state & STREAMING:
        state = STOPPED

    stop_adc()
    gc.enable()
    configure_interrupts('disable')

    if state & RESET:
        if DEBUG:
            print('Reset signal received.')
            time.sleep(1)
        machine.reset()


# Run from here
if __name__ == '__main__':
    try:
        # We can pass configuration variables into the program from main.py
        # via the sys.argv variable.
        # sys.argv = [ 'stream.py', '1x', '1x', '1x', '1x', '7.812k' ]
        # The variables are set into the adc_settings dictionary.
        # adc_settings = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }
        if len(sys.argv) == 6:
            _, g0, g1, g2, g3, sample_rate = sys.argv
            adc_settings = { 'gains': [g0, g1, g2, g3], 'sample_rate': sample_rate }
        else:
            adc_settings = DEFAULT_ADC_SETTINGS
        if DEBUG:
            print('stream.py started.')
        prepare_to_stream(adc_settings)
        stream()
    except KeyError:
        if DEBUG:
            print('Interrupted.')
    finally:
        cleanup()

