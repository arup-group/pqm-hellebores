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
import binascii
from micropython import const

########################################################
######### Configuration constants
########################################################
# Some constants are defined with the const() compilation hint to optimise performance.

# SPI_CLOCK_RATE is a configurable clock speed for comms on the SPI bus between
# Pico and ADC. Its setting is independent from the sampling rate, but needs to be
# fast enough to complete communications in the period between successive samples.
SPI_CLOCK_RATE = 8000000 
 
# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# This maintains code paths as much as possible, but outputs progress and diagnostic
# information. Instead of pushing sample data to stdout, it caches snips of sample
# data in a dedicated buffer and exits the program after a few cycles to then print
# it out.
DEBUG = const(False)

# These adc settings can be adjusted via comms from the Pi via command line arguments
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes is BUFFER_SIZE * 8 because we
# have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE = const(128)
BUFFER_MEMORY_SIZE = const(1024)
HALF_BUFFER_MEMORY_SIZE = const(512)

# flags: operation flags used to control program flow on both CPU cores.
STOP              = const(0b0001)          # tells both cores to exit
RESET             = const(0b0010)          # initiate a machine reset
OVERLOAD          = const(0b0100)          # perform an overload recovery on the ADC
STREAMING         = const(0b1000)          # fast ADC streaming using both cores

# cell:  sample pointer 0 to 127.
# Bit-and the cell variable with WRAP_MASK after incrementing it, to make the
# pointer circular.
WRAP_MASK         = const(0b01111111)      # pointer increment from 127 wraps round to 0

# The following three constants are used to test whether a page boundary has been
# crossed, and therefore time to output the next page of sample buffer. The cell
# variable is bit-anded with the PAGE_TEST mask and the result checked against
# WRITING_PAGE0 and WRITING_PAGE1 respectively.
PAGE_TEST         = const(0b01000000)      # test page number and streaming flag
WRITING_PAGE0     = const(0b00000000)      # bit6==0: pointer in range 0-63, ie page 0
WRITING_PAGE1     = const(0b01000000)      # bit6==1: pointer in range 64-127, ie page 1


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
        'flags_select' : Pin(26, Pin.IN)             # NOT USED
    }
    

def configure_adc_spi_interface():
    '''Sets up the Pico SPI interface using selected hardware pins. This will be
    used to communicate with the ADC.'''
    global spi_adc_interface
    # The SPI interface is set up in mode 0, with non-inverted clock polarity.
    # This means that data is input (sampled) on the first rising edge of the
    # clock pulse, and output (asserted) on the falling edge of the clock pulse.
    # The quiescent mode of the clock ('polarity') is low.
    # SPI messages begin and end when the chip select (CS*) pin is set low
    # and high. Note that the sending device does not know the clock speed and 
    # will assert the first bit immediately the CS* is activated.
    # Example: transferring the byte 201d or 11001001b in both directions.
    #
    # CS*     ----__________________________------
    # SCK     _____________-_-_-_-_-_-_-_-________
    # SDI     ____________----____--____--________
    # SDO     _____-----------____--____--________
    #                      1 1 0 0 1 0 0 1

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
    '''Write, and in DEBUG mode verify, values into selected register of the ADC.'''
    # The actual address byte leads with binary 01 and ends with the read/write
    # bit (1 or 0). The five bits in the middle are the 'register' address inside
    # the ADC.
    addr = 0x40 | (reg << 1)
    # for writing, make sure lowest bit is cleared, hence & 0b11111110
    pins['cs_adc'].low()
    if DEBUG:
        print('Writing: ' + ' '.join(hex(b) for b in bs))
    spi_adc_interface.write(bytes([addr & 0b11111110]) + bs)
    pins['cs_adc'].high()

    # for reading, make sure lowest bit is set, hence | 0b00000001
    if DEBUG:
        pins['cs_adc'].low()
        spi_adc_interface.write(bytes([addr | 0b00000001])) 
        obs = spi_adc_interface.read(len(bs))
        print('Verifying: ' + ' '.join(hex(b) for b in obs))
    pins['cs_adc'].high()
 

def reset_adc():
    '''Cycles the hardware reset pin of the ADC.'''
    pins['reset_adc'].low()
    pins['reset_adc'].high()


def clear_adc_overload():
    '''ADC codes at out-of-range values latch in the ADC output. Assigning to the
    PHASE register resets the ADCs to allow them to resume operation (datasheet
    section 5.5).'''
    bs = bytes([0x00, 0x00, 0x00])
    if DEBUG:
        print('PHASE register.')
    set_adc_register(0x0a, bs) 


def setup_adc(adc_settings):
    '''Setup the MCP3912 ADC. Refer to MCP3912 datasheet for detailed description of
    behaviour of all the settings configured here.'''
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
    bs = bytes([0x00, gain_bits >> 8, gain_bits & 0b11111111])
    if DEBUG:
        print('GAIN register.')
    set_adc_register(0x0b, bs) 

    # Set the status and communication register 0x0c
    # required bytes are:
    # 0x88 = 0b10001000: 10 READ address increments on TYPES, 0 WRITE address does not
    # increment, 0 DR_HIZ* DR is high impedance when idle, 1 DR_LINK only 1 DR pulse is
    # generated, 0 WIDTH_CRC is 16 bit, 00 WIDTH_DATA is 16 bits.
    # 0x00 = 0b00000000: 0 EN_CRCCOM CRC is disabled, 0 EN_INT CRC interrupt is disabled
    # 0x0f = 0b00001111: 1111 DRSTATUS data ready status bits for individual channels  
    bs = bytes([0x88, 0x00, 0x0f])
    if DEBUG:
        print('STATUSCOM register.')
    set_adc_register(0x0c, bs) 

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets sampling rate via over-sampling ratio (OSR), possible OSR settings
    # are as per the table:
    # 0x00 = 32:  31.25 kSa/s
    # 0x20 = 64:  15.625 kSa/s
    # 0x40 = 128:  7.8125 kSa/s
    # 0x60 = 256:  3.90625 kSa/s
    # 0x80 = 512:  1.953 kSa/s
    # 0xa0 = 1024:   976 Sa/s
    # 0xc0 = 2048:   488 Sa/s
    # 0xe0 = 4096:   244 Sa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    osr_table = { '244':0xe0, '488':0xc0, '976':0xa0, '1.953k':0x80,
                  '3.906k':0x60, '7.812k':0x40, '15.625k':0x20, '31.250k':0x00 }
    try:
        bs = bytes([0x24, osr_table[adc_settings['sample_rate']], 0x50])
    except KeyError:
        bs = bytes([0x24, osr_table['7.812k'], 0x50])
    if DEBUG:
        print('CONFIG0 register.')
    set_adc_register(0x0d, bs) 

    # Set the configuration register CONFIG1 at 0x0e
    bs = bytes([0x00, 0x00, 0x00])
    if DEBUG:
        print('CONFIG1 register.')
    set_adc_register(0x0e, bs)

 

def configure_interrupts(command='enable'):
    '''Two interrupt handlers are set up, one for the DR* pin, for notifying Pico
    that new data is ready for reading from the ADC, and a reset command from the
    Pi, to help with run-time error recovery.'''

    # Interrupt handler for data ready pin (this pin is commanded from the ADC)
    def adc_read_handler(_):
        global cell
        # 'anding' the pointer with a bit mask that has binary '0' in the bit above the
        # largest buffer pointer makes the buffer pointer circulate to zero without needing
        # an 'if' conditional: this means the instruction executes in constant time
        cell = (cell + 1) & WRAP_MASK

    # we need this helper function, because we can't easily assign to global variable
    # within a lambda expression
    def set_flags(required_flags):
        global flags
        flags = required_flags

    if command == 'enable':
        # Bind pin transitions to interrupt handlers.
        # We use hard interrupt for the DR* pin to maintain tight timing,
        # and for the RESET* pin so that the reset works even within a blocking
        # function (eg serial write). We defer the actual hardware reset until
        # cleanup has happened, including core 1 exiting
        pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING,
                           handler = adc_read_handler, hard=True)
        pins['reset_me'].irq(trigger = Pin.IRQ_FALLING,
                           handler = lambda _: set_flags(RESET), hard=True)

    elif command == 'disable':
        pins['dr_adc'].irq(handler = None)
        pins['reset_me'].irq(handler = None)


class Debug_cache:

    def __init__(self):
        self.cache_pointer = 0
        self.cache = [ bytearray(32) for i in range(32) ]
 
    def reset(self):
        self.cache_pointer = 0

    def save_snip(self, bs):
        if self.cache_pointer <= 31:
            self.cache[self.cache_pointer][:] = bs[:32]
            self.cache_pointer += 1
            return True
        else:
            return False   
   
    def as_text(self):
        text_out = ''
        for bs in self.cache:
            # NB 32 bytes become 64 characters.
            hs = binascii.hexlify(bs).decode('utf-8')
            text_out += f'{hs[0:16]} {hs[16:32]} {hs[32:48]} {hs[48:64]}\n'
        return text_out


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by various memoryview objects that point to
    different portions of it.'''
    global p0_mv, p1_mv, p0_last_cell_mv, p1_last_cell_mv, cells_mv

    # 2 bytes per channel, 4 channels
    acq = bytearray(BUFFER_MEMORY_SIZE)
    # we make a memoryview to allow this to be sub-divided into pages and
    # cells
    acq_mv = memoryview(acq)
    # Create memoryviews of each half of the buffer (ie two pages).
    # This is used in the Core 0 loop to output one half of the memory while new
    # samples are read into the other half.
    p0_mv = memoryview(acq_mv[:HALF_BUFFER_MEMORY_SIZE])
    p1_mv = memoryview(acq_mv[HALF_BUFFER_MEMORY_SIZE:])
    # For testing ADC overload, make a reference to the last cell of each page.
    p0_last_cell_mv = memoryview(p0_mv[-2:])
    p1_last_cell_mv = memoryview(p1_mv[-2:])
    # Create a memoryview reference into each sample or slice of the buffer.
    # 8 bytes each cell, stepping 8 bytes.
    # This is used in the Core 1 loop to step through the memory sample by sample,
    # without needing to make an intermediate copy.
    cells_mv = [ memoryview(acq_mv[m:m+8]) for m in range(0, BUFFER_MEMORY_SIZE, 8) ]
 

def start_adc():
    '''Tell the ADC to read out the ADC registers in multiple-read mode. It's
    necessary for the CS pin to be held low from this point, for the duration
    of sampling.'''
    if DEBUG:
        print('Starting the ADC...')
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
    '''Watches for change in cell variable (incremented by the interrupt handler)
    and reads new data from the ADC into memory. Also watches for change in flags
    variable to enable clean exit or recovery from OVERLOAD condition.'''
    global flags

    start_adc()
    # The overload state may start at any time, so we have to include it in the
    # loop test here.
    while flags & STREAMING:
        # p_cell is a local cache of the cell variable, so that we can
        # detect when it changes value
        p_cell = cell
        # Inner loop -- speed critical -- we do sampling here, nothing else.
        while flags & STREAMING:
            # Check to see if cell has changed
            if cell != p_cell:
                # read out from the ADC *immediately*
                spi_adc_interface.readinto(cells_mv[cell])
                # save the new cell pointer value
                p_cell = cell
        # If Core 0 has raised OVERLOAD flag, we deal with it here.
        if flags & OVERLOAD:
            # Tell the ADC to clear overload.
            # Note that while we skip data acquisition while we work through
            # these steps, the cell index counter continues to increment.
            stop_adc()
            clear_adc_overload()
            start_adc()
            # Clear OVERLOAD flag 
            flags = STREAMING

    if DEBUG:
        print('Streaming_loop_core_1() exited')


########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
def streaming_loop_core_0(): 
    '''Prints data from memory to stdout in 'half-buffer' chunks.'''

    # Create local debug cache for memorising a few sampling loops
    debug_cache = Debug_cache()

    def _transfer_buffer_normal(bs):
        pins['buffer_led'].on()
        # write out the selected portion of buffer as raw bytes
        sys.stdout.buffer.write(bs)
        pins['buffer_led'].off()

    def _transfer_buffer_debug(bs):
        global flags
        pins['buffer_led'].on()
        # saves snips until the debug cache is full
        if debug_cache.save_snip(bs) == False:
            flags = STOP
        pins['buffer_led'].off()

    # select the transfer function we are going to use from now on
    if DEBUG:
        transfer_buffer = _transfer_buffer_debug
    else:
        transfer_buffer = _transfer_buffer_normal
    
    def overload_test(mv):
        global flags
        # If overloaded the ADC will latch on all channels to one of
        # these overload codes.
        if (mv == b'\x80\x00') or (mv == b'\x7f\xff'):
            # Raise OVERLOAD flag.
            flags = flags | OVERLOAD

    # Now loop...
    while flags & STREAMING:
        # Wait while Core 1 is filling up page 0.
        while (cell & PAGE_TEST) == WRITING_PAGE0:
            continue
        transfer_buffer(p0_mv)
        overload_test(p0_last_cell_mv)
        # Wait while Core 1 is filling up page 1.
        while (cell & PAGE_TEST) == WRITING_PAGE1:
            continue
        transfer_buffer(p1_mv)
        overload_test(p1_last_cell_mv)

    if DEBUG:
        print('Streaming_loop_core_0() exited.')
        print('Here are the contents of debug buffer memory:')
        print(debug_cache.as_text())


def prepare_to_stream(adc_settings):
    '''Configures all the pre-requisities: pins, SPI interface, ADC settings
    circular buffer memory, interrupts and garbage collection.'''

    # Pin and SPI library setup
    configure_pins()
    configure_adc_spi_interface()

    # Buffer memory is set up in various memoryview structures that point to
    # an underlying bytearray that holds a buffer of ADC samples. These
    # objects are declared global so that the memory can be reached by both
    # CPU cores.
    configure_buffer_memory()

    if DEBUG:
        print('Configuring ADC and interrupts.')
    # Push required settings into the ADC.
    reset_adc()
    clear_adc_overload()    # NB The reset process can cause the ADCs to latch
    setup_adc(adc_settings)

    # ADC is responsible for sample timing. Every sample, it toggles the DR* pin.
    # An interrupt handler on Pico receives this pulse, calling adc_read_handler(),
    # so that the data can be retrieved.
    # DR*     ----_------------_------------_-----
    #             irq          irq          irq
    configure_interrupts()

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
    # These loops will both stay running while the STREAMING flag is raised.
    _thread.start_new_thread(streaming_loop_core_1, ())
    streaming_loop_core_0()
    # runs forever, unless:
    #     CTRL-C:             STOP flag raised.
    #     reset_me pin:       RESET flag raised.
    

def cleanup():
    '''For debugging, it's useful for the Pico to be returned to a quiescent
    mode.'''
    stop_adc()
    gc.enable()
    configure_interrupts('disable')


def main():
    global flags, cell
    
    try:
        # We can pass configuration variables into the program from main.py
        # via the sys.argv variable.
        # sys.argv = [ 'stream.py', '1x', '1x', '1x', '1x', '7.812k' ]
        # The variables are loaded into the adc_settings dictionary.
        # adc_settings = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }
        if len(sys.argv) == 6:
            _, g0, g1, g2, g3, sample_rate = sys.argv
            adc_settings = { 'gains': [g0, g1, g2, g3], 'sample_rate': sample_rate }
        else:
            adc_settings = DEFAULT_ADC_SETTINGS
        if DEBUG:
            print('stream.py started.')
        flags = STREAMING
        cell = 0
        prepare_to_stream(adc_settings)
        stream()

    except KeyboardInterrupt:
        # Catch CTRL-C here.
        if DEBUG:
            print('Interrupted.')
        # Stop Core 1 if it's still running 
        flags = STOP

    finally:
        # If we reach here, STOP or RESET flags are raised.
        cleanup()
        if flags & RESET:
            if DEBUG:
                print('Reset flag raised; waiting 10 seconds before proceeding.')
                time.sleep(10)
            machine.reset()
    

# Run from here
if __name__ == '__main__':
    main()


