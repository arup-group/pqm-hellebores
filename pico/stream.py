# To run on Raspberry Pi Pico microcontroller, communicating with MCP3912
# 4-channel ADC via SPI serial interface, and host computer via USB serial
# interface. The code provides a circular buffer for precisely timed incoming
# measurements signalled by the ADC (via the data ready, DR* pin), and sends
# output from the buffer in blocks of 64x4x16 bit integer values.

# BE VERY CAREFUL WITH EDITING! GARBAGE COLLECTOR IS SWITCHED OFF IN INNER
# LOOPS TO MAINTAIN PERFORMANCE. MEMORYVIEW OBJECTS ARE USED TO AVOID NEW
# MEMORY ALLOCATIONS.

import time
import machine
import uctypes
from machine import Pin
import gc
import _thread
import sys
import binascii
from micropython import const

########################################################
######### Configuration constants
########################################################
# Some constants are defined with the const() compilation hint to optimise
# performance.

# SPI_CLOCK_RATE is a configurable clock speed for comms on the SPI bus between
# Pico and ADC. Its setting is independent from the sampling rate, but needs
# to be fast enough to complete communications in the period between successive
# samples.
SPI_CLOCK_RATE = 6000000

# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# This maintains code paths as much as possible, but outputs progress and
# diagnostic information. Instead of pushing sample data to stdout, it caches
# snips of sample data in a dedicated buffer and exits the program after a few
# cycles to then print it out.
DEBUG = const(False)

# These adc settings can be adjusted via comms from the Pi via command line
# arguments
DEFAULT_ADC_SETTINGS = { 'gains':       ['1x', '1x', '1x', '1x'],
                         'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work
# easily. The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes is BUFFER_SIZE * 8 because
# we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE = const(256)
BUFFER_MEMORY_SIZE = const(2048)

# flags: operation flags used to control program flow on both CPU cores.
STOP: int        = const(0b0001)       # tells both cores to exit
RESET: int       = const(0b0010)       # initiate a machine reset
RESYNC: int      = const(0b0100)       # perform a soft reset on the ADC
STREAMING: int   = const(0b1000)       # fast ADC streaming using both cores

# cell:  sample pointer 0 to 255.
# Bit-and the cell variable with WRAP_MASK after incrementing it, to make the
# pointer circular. Increment from 255 & WRAP_MASK wraps round to 0.
WRAP_MASK: int   = const(0b11111111)

# The following constants are used to test whether a page boundary has
# been crossed, and therefore time to output the next page of sample buffer.
# The cell variable is bit-anded with the PAGE_BITS bit mask and the result
# checked against PAGEn constants.
PAGE_BITS: int   = const(0b11000000)   # test page number
PAGE0: int       = const(0b00000000)   # bit76==00: in range 0-63, ie page 0
PAGE1: int       = const(0b01000000)   # bit76==01: in range 64-127, ie page 1
PAGE2: int       = const(0b10000000)   # bit76==10: in range 128-191, ie page 2
PAGE3: int       = const(0b11000000)   # bit76==11: in range 192-255, ie page 3

# ADC register addresses
PHASE = 0x0a
GAIN = 0x0b
STATUSCOM = 0x0c
CONFIG0 = 0x0d
CONFIG1 = 0x0e
LOCK_CRC = 0x1f
# ADC commands
ADC_WRITE = 0x40
ADC_READ = 0x41


########################################################
######### Global variables
########################################################
# Define the global variables with type hints to assist the optimiser
pins: dict                   # pin configuration for the Pico
spi_adc_interface: object    # object holding SPI interface configuration
flags: int                   # bit field with flags to control operation
cell: int                    # pointer to current cell in the buffer
acq: bytearray               # underlying storage for the sample buffer
p0: bytearray                # page 0 of the storage buffer
p1: bytearray                # page 1 of the storage buffer
p2: bytearray                # page 2 of the storage buffer
p3: bytearray                # page 3 of the storage buffer
cells_mv: tuple              # index to the individual cells of the buffer


########################################################
######### Hardware control functions
########################################################
def configure_pins():
    '''Pico pin setup, referenced by a global variable 'pins'. Pins labelled *
    are active low. We initialise with the RESET* and CS* pins high, since we
    don't want them to operate until needed.'''
    global pins
    pins = {
        'pico_led'    : Pin(25, Pin.OUT, value=0),  # led on the Pico
        'buffer_led'  : Pin(15, Pin.OUT, value=0),  # 'buffer' LED on PCB
        'cs_adc'      : Pin(1, Pin.OUT, value=1),   # chip select* pin ADC
        'sck_adc'     : Pin(2, Pin.OUT),            # SPI interface clock
        'sdi_adc'     : Pin(3, Pin.OUT),            # input to ADC (from Pico)
        'sdo_adc'     : Pin(0, Pin.IN),             # output from ADC (to Pico)
        'reset_adc'   : Pin(5, Pin.OUT, value=1),   # reset* ADC
        'dr_adc'      : Pin(4, Pin.IN),             # data ready* from ADC
        'reset_me'    : Pin(14, Pin.IN),            # reset Pico (from Pi)
        'flags_select': Pin(26, Pin.IN)             # NOT USED
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


def set_adc_register(reg: int, bs: bytes):
    '''Write, and in DEBUG mode verify, values into selected register of the
    ADC.'''
    if DEBUG:
        print('Writing: ' + ' '.join(hex(b) for b in bs))
    # The register address is inserted into bits 5..1 of the command byte.
    addr = ADC_WRITE | (reg << 1)
    pins['cs_adc'].low()
    spi_adc_interface.write(bytes([addr]) + bs)
    pins['cs_adc'].high()
    # Verify in debug mode
    if DEBUG:
        obs = get_adc_register(reg, len(bs))
        print('Verifying: ' + ' '.join(hex(b) for b in obs))


def get_adc_register(reg: int, n: int) -> bytes:
    '''Read n bytes from register of ADC.'''
    addr = ADC_READ | (reg << 1)
    pins['cs_adc'].low()
    spi_adc_interface.write(bytes([addr]))
    obs = spi_adc_interface.read(n)
    pins['cs_adc'].high()
    return obs


def lock_adc_registers():
    '''Lock all writable register values apart from LOCK_CRC, to increase
    resilence to electrical noise.'''
    if DEBUG:
        print('Locking registers.')
    set_adc_register(LOCK_CRC, bytes([0x00]))

def unlock_adc_registers():
    '''Unlock registers for writing.'''
    if DEBUG:
        print('Unlocking registers.')
    set_adc_register(LOCK_CRC, bytes([0x0a]))


def hard_reset_adc():
    '''Cycles the hardware reset pin of the ADC.'''
    pins['reset_adc'].low()
    pins['reset_adc'].high()


def soft_reset_adc():
    '''ADC codes can latch in the ADC output if spurious clock pulses are
    received and new values can't be loaded. Assigning to the PHASE
    register resets the ADCs to allow them to resume operation
    (datasheet section 5.5).'''
    unlock_adc_registers()
    set_adc_register(PHASE, bytes([0x00, 0x00, 0x00]))
    lock_adc_registers()


def setup_adc(adc_settings: dict):
    '''Setup the MCP3912 ADC. Refer to MCP3912 datasheet for detailed
    description of behaviour of all the settings configured here.'''
    # Unlock registers, so that we can write to them
    unlock_adc_registers()

    # Set the phase configuration register which soft resets all ADCs
    if DEBUG:
        print('PHASE register.')
    set_adc_register(PHASE, bytes([0x00, 0x00, 0x00]))

    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    # gains are in order of hardware channel:
    # differential current, low range current, full range current, voltage
    G = { '32x':0b101, '16x':0b100, '8x':0b011,
          '4x':0b010, '2x':0b001, '1x':0b000 }
    try:
        g3, g2, g1, g0 = [ G[k] for k in adc_settings['gains'] ]
    except KeyError:
        g3, g2, g1, g0 = [ G[k] for k in ['1x', '1x', '1x', '1x'] ]
    gain_bits = (g3 << 9) + (g2 << 6) + (g1 << 3) + g0
    bs = bytes([0x00, gain_bits >> 8, gain_bits & 0b11111111])
    if DEBUG:
        print('GAIN register.')
    set_adc_register(GAIN, bs)

    # Set the status and communication register 0x0c
    # required bytes are:
    # 0x88 = 0b10001000: 10 READ address increments on TYPES, 0 WRITE address
    # does not increment, 0 DR_HIZ* DR is high impedance when idle, 1 DR_LINK
    # only 1 DR pulse is generated, 0 WIDTH_CRC is 16 bit, 00 WIDTH_DATA is 16
    # bits.
    # 0x00 = 0b00000000: 0 EN_CRCCOM CRC, 0 EN_INT CRC interrupt both disabled
    # 0x0f = 0b00001111: 1111 DRSTATUS data ready status bits for channels
    if DEBUG:
        print('STATUSCOM register.')
    set_adc_register(STATUSCOM, bytes([0x88, 0x00, 0x0f]))

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets sampling rate via over-sampling ratio (OSR), possible OSR
    # settings are as per the table:
    # 0x00 = 32:  31.25    kSa/s
    # 0x20 = 64:  15.625   kSa/s
    # 0x40 = 128:  7.8125  kSa/s
    # 0x60 = 256:  3.90625 kSa/s
    # 0x80 = 512:  1.953   kSa/s
    # 0xa0 = 1024:   976   Sa/s
    # 0xc0 = 2048:   488   Sa/s
    # 0xe0 = 4096:   244   Sa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    osr_table = { '244':0xe0, '488':0xc0, '976':0xa0, '1.953k':0x80,
                  '3.906k':0x60, '7.812k':0x40, '15.625k':0x20, '31.250k':0x00 }
    try:
        bs = bytes([0x24, osr_table[adc_settings['sample_rate']], 0x50])
    except KeyError:
        bs = bytes([0x24, osr_table['7.812k'], 0x50])
    if DEBUG:
        print('CONFIG0 register.')
    set_adc_register(CONFIG0, bs)

    # Set the configuration register CONFIG1 at 0x0e
    if DEBUG:
        print('CONFIG1 register.')
    set_adc_register(CONFIG1, bytes([0x00, 0x00, 0x00]))

    # Lock the registers against further write access.
    lock_adc_registers()



def configure_interrupts(command: str ='enable'):
    '''Two interrupt handlers are set up, one for the DR* pin, for notifying
    Pico that new data is ready for reading from the ADC, and a reset command
    from the Pi, to help with run-time error recovery.'''

    # Interrupt handler for data ready pin (this pin is commanded from the ADC)
    # Use viper native optimiser to minimise response time.
    @micropython.viper
    def adc_read_handler(_):
        global cell
        # 'anding' the pointer with a bit mask that has binary '0' in the bit
        # above the largest buffer pointer makes the buffer pointer circulate
        # to zero without needing an 'if' conditional: this means the
        # instruction executes in constant time
        cell = (int(cell) + 1) & int(WRAP_MASK)

    # we need this helper function, because we can't easily assign to global
    # variable within a lambda expression
    def set_flags(required_flags: int):
        global flags
        flags = required_flags

    if command == 'enable':
        # Bind pin transitions to interrupt handlers.
        # We use hard interrupt for the DR* pin to maintain tight timing,
        # and for the RESET pin so that the reset works even within a blocking
        # function (eg serial write). We defer the actual hardware reset until
        # cleanup has happened, including core 1 exiting
        pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING,
                           handler = adc_read_handler, hard=True)
        pins['reset_me'].irq(trigger = Pin.IRQ_RISING,
                           handler = lambda _: set_flags(RESET), hard=True)

    elif command == 'disable':
        pins['dr_adc'].irq(handler = None)
        pins['reset_me'].irq(handler = None)


def start_adc():
    '''Tell the ADC to read out the ADC registers in multiple-read mode. It's
    necessary for the CS pin to be held low from this point, for the duration
    of sampling.'''
    if DEBUG:
        print('Starting the ADC...')
    pins['cs_adc'].low()
    # Start reading from address 0x00. As the SPI clock pumps out data, the
    # ADC will loop around the four ADC channel registers.
    spi_adc_interface.write(bytes([0x41]))


def stop_adc():
    '''Tell the ADC to stop sampling.'''
    # Note that the DR* pin continues to cycle, so it's necessary to also stop
    # interrupts if we want to stop processing completely
    if DEBUG:
        print('Stopping the ADC...')
    pins['cs_adc'].high()



########################################################
######### Buffer and debug memory
########################################################
class Debug_cache:

    def __init__(self):
        self.cache_pointer = 0
        self.cache = [ bytearray(32) for i in range(16) ]

    def reset(self):
        self.cache_pointer = 0

    def save_snip(self, bs: bytearray) -> bool:
        if self.cache_pointer <= 15:
            self.cache[self.cache_pointer][:] = bs[:32]
            self.cache_pointer += 1
            return True
        else:
            return False

    def as_text(self) -> str:
        text_out = ''
        for bs in self.cache:
            # NB 32 bytes become 64 characters.
            hs = binascii.hexlify(bs).decode('utf-8')
            text_out += f'{hs[0:16]} {hs[16:32]} {hs[32:48]} {hs[48:64]}\n'
        return text_out


def get_unstriped_regions(bs: bytearray):
    '''From a given bytearray or memoryview, finds the starting address and
    places some test data in the bytearray. Then searches for the unstriped
    form of the data across the unstriped memory space. Then computes
    starting addresses for each unstriped region and returns them as
    bytearray objects.
    '''
    length = len(bs)
    qlen = length // 4
    # write some test data into the bytearray
    test_data = b'abcdefghijklmnopqrstuvwxyz'
    if len(test_data) > length:
        print('ERROR: stream.py, get_unstriped_regions() was called with a '
              'bytearray that was too short.')
        sys.exit(1)
    bs[:len(test_data)] = test_data
    # with the test_data written into memory, adjacent words of the unstriped
    # memory region will have the following contents. We search in two steps
    # to prevent the search matching on python source or bytecode that might
    # also be in memory.
    search_data1 = b'abcd'
    search_data2 = b'qrst'
    # figure out base address offset into unstriped memory, searching the
    # first 64kB of unstriped address space
    offset = None
    for i in range(0, 65536):
        if ((uctypes.bytearray_at(0x21000000 + i, 4) == search_data1)
            and (uctypes.bytearray_at(0x21000000 + i + 4, 4) == search_data2)):
            offset = i
            break
    # quit if we can't find the test data
    if offset == None:
        print('ERROR: stream.py, get_unstriped_regions() could not locate '
              'unstriped memory regions.')
        sys.exit(1)
    # make bytearray objects that correspond to each page
    p0 = uctypes.bytearray_at(0x21000000 + offset, qlen)
    p1 = uctypes.bytearray_at(0x21010000 + offset, qlen)
    p2 = uctypes.bytearray_at(0x21020000 + offset, qlen)
    p3 = uctypes.bytearray_at(0x21030000 + offset, qlen)
    return (p0, p1, p2, p3)


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by various memoryview objects that point
    to different portions of it. By default, buffer memory allocated from global
    heap is striped across 4 x 64kB memory regions, with striping at 32 bit
    word boundaries. When we are accessing memory from 2 CPU cores, we want to
    avoid accessing the same memory region from both cores simultaneously (one
    access will be delayed by the DMA scheduler).
    Consequently, we re-map the allocated bytearray into bytearray objects that
    are in contigous memory regions, using the unstriped memory mapping.
    This memory layout means that at a hardware level, reading and writing from
    different pages can occur in the same clock cycle.
    '''
    global acq
    global p0, p1, p2, p3
    global cells_mv

    # 2 bytes per channel, 4 channels
    # acq is a global variable to prevent it being garbage collected
    acq = bytearray(BUFFER_MEMORY_SIZE)
    # Create bytearrays for each unstriped region of the buffer (ie four pages).
    # This is used in the Core 0 loop to output one region of the memory while new
    # samples are read into a different region.
    p0, p1, p2, p3 = get_unstriped_regions(acq)
    # Create a memoryview reference into each sample or slice of the buffer.
    # 8 bytes each cell, stepping 8 bytes.
    # This is used in the Core 1 loop to step through the memory regions sample by
    # sample, without needing to store an intermediate copy or calculate byte
    # offsets on the fly.
    qlen = len(acq) // 4
    cells_mv_list =      [ memoryview(p0[m:m+8]) for m in range(0, qlen, 8) ]
    cells_mv_list.extend([ memoryview(p1[m:m+8]) for m in range(0, qlen, 8) ])
    cells_mv_list.extend([ memoryview(p2[m:m+8]) for m in range(0, qlen, 8) ])
    cells_mv_list.extend([ memoryview(p3[m:m+8]) for m in range(0, qlen, 8) ])
    # Convert list into a tuple object for slight performance gain
    cells_mv = tuple(cells_mv_list)


########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
# performance: optimise this function to native code rather than bytecode
@micropython.viper
def streaming_loop_core_1():
    '''Watches for change in cell variable (incremented by the interrupt
    handler) and reads new data from the ADC into memory. Also watches for
    change in flags variable to enable clean exit or recovery from RESYNC
    condition.'''
    global flags, cell

    # The resync flag may be raised by Core 0 at any time, so we have to
    # allow for it in the outer loop test here by using a bitmask filter
    start_adc()
    while flags & STREAMING:
        # cell_p is a local cache of the cell variable, so that the inner loop
        # can synchronise to the moment when cell changes value
        cell_p: int = cell

        # Inner loop -- speed critical -- we do sampling here, nothing else.
        while flags == STREAMING:
            # Read out from the ADC *immediately* if the cell variable changes
            # value, then repeat.
            cell == cell_p \
                or spi_adc_interface.readinto(cells_mv[(cell_p := cell)])

        # If Core 0 has raised RESYNC flag, we miss a few samples and deal
        # with it here.
        if flags & RESYNC:
            # Tell the ADC to stop and resychronise to the Pico.
            stop_adc()
            soft_reset_adc()
            start_adc()
            # Clear RESYNC flag
            flags = flags & ~RESYNC
            # Clear garbage
            gc.collect()

    if DEBUG:
        print('Streaming_loop_core_1() exited')


########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
# Debug cache for memorising a few sampling loops
debug_cache = Debug_cache()
def streaming_loop_core_0():
    '''Prints data from memory to stdout in chunks.'''
    global debug_cache

    def _transfer_buffer_normal(bs):
        pins['buffer_led'].on()
        # write out the selected portion of buffer as raw bytes
        sys.stdout.buffer.write(bs)
        pins['buffer_led'].off()

    def _transfer_buffer_debug(bs):
        global flags
        pins['buffer_led'].on()
        # saves snips until the debug cache is full
        if not bool(debug_cache.save_snip(bs)):
            flags = STOP
        pins['buffer_led'].off()

    # select the transfer function we are going to use from now on
    if DEBUG:
        transfer_buffer = _transfer_buffer_debug
    else:
        transfer_buffer = _transfer_buffer_normal

    def sync_test():
        global flags
        # If SPI clock synchronisation fails, the ADC outputs will latch to the same
        # values on successive samples. So we compare the readings from two successive
        # samples to check:
        c1 = const(BUFFER_SIZE - 2)
        c2 = const(BUFFER_SIZE - 1)
        if (cells_mv[c1][0:4] == cells_mv[c1][4:8]
            and cells_mv[c1][4:8] == cells_mv[c2][0:4]
            and cells_mv[c2][0:4] == cells_mv[c2][4:8]):
           # Raise RESYNC flag.
           flags = flags | RESYNC

    # Wait for receiving programs to be ready to receive data
    time.sleep(5)

    # Now transfer buffers in turn and loop...
    while flags & STREAMING:
        # Wait while we fill page 0, then transfer it
        while (cell & PAGE_BITS) == PAGE0:
            continue
        transfer_buffer(p0)
        # Wait while we fill page 1, then transfer it
        while (cell & PAGE_BITS) == PAGE1:
            continue
        transfer_buffer(p1)
        # Wait while we fill page 2, then transfer it
        while (cell & PAGE_BITS) == PAGE2:
            continue
        transfer_buffer(p2)
        # Wait while we fill page 3. then transfer it
        while (cell & PAGE_BITS) == PAGE3:
            continue
        transfer_buffer(p3)
        # Check to see if SPI clock is still sync'ed with ADC readouts
        sync_test()

    if DEBUG:
        print('Streaming_loop_core_0() exited.')
        print('Here are the contents of debug buffer memory:')
        gc.collect()
        print(debug_cache.as_text())



########################################################
######### High level functions to support main()
########################################################
def reset_pin_held_high() -> bool:
    '''This function supports recovery from some transient disturbances that
    can cause the inner sampling loops to exit. The function confirms that the
    reset_me pin of the Pico is sustained in a high state for a long enough
    period that we can rely on it being a genuine reset command.'''
    # We check to see if the reset pin is sustained in high state
    reset_status = True
    for i in range(3):
        if pins['reset_me'].value() == 0:
            reset_status = False
        time.sleep(0.01)
    return reset_status


def prepare_to_stream(adc_settings: dict):
    '''Configures all the pre-requisities: pins, SPI interface, ADC settings
    circular buffer memory, interrupts and garbage collection.'''

    # SPI library setup
    configure_adc_spi_interface()

    # Buffer memory is set up in various memoryview structures that point to
    # an underlying bytearray that holds a buffer of ADC samples. These
    # objects are declared global so that the memory can be reached by both
    # CPU cores.
    configure_buffer_memory()

    if DEBUG:
        print('Configuring ADC and interrupts.')
    # Push required settings into the ADC.
    hard_reset_adc()
    setup_adc(adc_settings)

    # ADC is responsible for sample timing. Every sample, it toggles the DR*
    # pin. An interrupt handler on Pico receives this pulse, calling
    # adc_read_handler(), so that the data can be retrieved.
    # DR*     ----_------------_------------_-----
    #             irq          irq          irq
    configure_interrupts()

    # We don't want garbage collection pauses while streaming, so we disable
    # the automatic GC.
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

    # We can pass configuration variables into the program from main.py
    # via the sys.argv variable.
    # sys.argv = [ 'stream.py', '1x', '1x', '1x', '1x', '7.812k' ]
    # The variables are loaded into the adc_settings dictionary.
    # adc_settings = { 'gains':       ['1x', '1x', '1x', '1x'],
    #                  'sample_rate': '7.812k' }
    if len(sys.argv) == 6:
        _, g0, g1, g2, g3, sample_rate = sys.argv
        adc_settings = { 'gains': [g0, g1, g2, g3],
                         'sample_rate': sample_rate }
    else:
        adc_settings = DEFAULT_ADC_SETTINGS
    if DEBUG:
        print(f'stream.py started with parameters {adc_settings}.')
    try:
        configure_pins()
        flags = STREAMING
        cell = 0
        while flags == STREAMING:
            prepare_to_stream(adc_settings)
            stream()
            # Inner sampling loops will exit if a rising edge pulse is detected
            # on the 'reset_me' pin. This is to make it possible to restart the
            # Pico via software, toggling this pin. However, this outer loop
            # allows for automatic recovery if a reset edge was caused by an
            # electrical disturbance (eg inrush). If the reset state is not
            # sustained for a long enough period, we consider it spurious and
            # we will restart the ADCs and continue streaming, instead of
            # proceeding to reset the machine.
            if flags & RESET and not reset_pin_held_high():
                flags = STREAMING

    except KeyboardInterrupt:
        # Catch CTRL-C here.
        if DEBUG:
            print('Interrupted.')
        # Stop Core 1.
        flags = STOP

    except:
        # Catch other exceptions.
        if DEBUG:
           print('There was an exception.')
        flags = RESET

    finally:
        # If we reach here, STOP or RESET flags are raised.
        cleanup()
        if flags & RESET:
            if DEBUG:
                print('Reset flag raised: resetting shortly.')
            # allow the reset pin to clear to normal
            time.sleep(1)
            machine.reset()


# Run from here
if __name__ == '__main__':
    main()
