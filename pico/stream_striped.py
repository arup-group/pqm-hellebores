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
HALF_BUFFER_MEMORY_SIZE = const(1024)

# Penultimate and final cell locations are used to test whether the SPI
# interface has lost synchronisation with the ADC. The output shift register
# will latch into a fixed state if this is the case.
P0_CELL_A: int   = const(126)
P0_CELL_B: int   = const(127)
P1_CELL_A: int   = const(254)
P1_CELL_B: int   = const(255)

# flags: operation flags used to control program flow on both CPU cores.
STOP: int        = const(0b0001)       # tells both cores to exit
RESET: int       = const(0b0010)       # initiate a machine reset
RESYNC: int      = const(0b0100)       # perform a soft reset on the ADC
STREAMING: int   = const(0b1000)       # fast ADC streaming using both cores

# cell:  sample pointer 0 to 255.
# Bit-and the cell variable with WRAP_MASK after incrementing it, to make the
# pointer circular. Increment from 255 & WRAP_MASK wraps round to 0.
WRAP_MASK: int   = const(0b11111111)

# The following three constants are used to test whether a page boundary has
# been crossed, and therefore time to output the next page of sample buffer.
# The cell variable is bit-anded with the PAGE_BIT mask and the result
# checked against PAGE0 and PAGE1 respectively.
PAGE_BIT: int    = const(0b10000000)   # test page number and streaming flag
PAGE0: int       = const(0b00000000)   # bit7==0: in range 0-127, ie page 0
PAGE1: int       = const(0b10000000)   # bit7==1: in range 128-255, ie page 1

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
pins: dict               # pin configuration for the Pico
spi_adc_interface: SPI   # object holding SPI interface configuration
flags: int               # bit field with flags to control operation
cell: int                # pointer to current cell in the buffer
p0_mv: memoryview        # page 0 of the storage buffer
p1_mv: memoryview        # page 1 of the storage buffer
cells_mv: memoryview     # array of all the cells of the storage buffer


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


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by various memoryview objects that point
    to different portions of it.'''
    global p0_mv, p1_mv, cells_mv

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
    # Create a memoryview reference into each sample or slice of the buffer.
    # 8 bytes each cell, stepping 8 bytes.
    # This is used in the Core 1 loop to step through the memory sample by
    # sample, without needing to make an intermediate copy.
    cells_mv = [ memoryview(acq_mv[m:m+8])
                     for m in range(0, BUFFER_MEMORY_SIZE, 8) ]



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

    # performance: make a copy of the memoryview object references in a
    # local tuple, which has slightly faster lookup times
    cells_mv_tuple = tuple(cells_mv)
    adc_value = bytearray(8)

    # The resync flag may be raised by Core 0 at any time, so we have to
    # allow for it in the outer loop test here by using a bitmask filter
    start_adc()
    while flags & STREAMING:
        # cell_p is a local cache of the cell variable, so that the inner loop
        # can synchronise to the moment when cell changes value
        cell_p: int = cell

        # Inner loop -- speed critical -- we do sampling here, nothing else.
        while flags == STREAMING:
            # Read out from the ADC *immediately* if the cell variable has
            # changed. We read into a local variable first so that if there is
            # contention in the memory shared with core 0, it doesn't disrupt
            # the SPI bus read. (There can be occasional errors if the DMA
            # scheduler has to to resolve shared memory access during an SPI
            # transmission.)
            cell == cell_p \
                or (spi_adc_interface.readinto(adc_value) \
                    and cells_mv_tuple[(cell_p := cell)][:] = adc_value)

        # If Core 0 has raised RESYNC flag, we deal with it here.
        if flags & RESYNC:
            # Tell the ADC to stop and resychronise to the Pico.
            stop_adc()
            soft_reset_adc()
            start_adc()
            # Clear RESYNC flag
            flags = flags & ~RESYNC

    if DEBUG:
        print('Streaming_loop_core_1() exited')


########################################################
######### STREAMING LOOP FOR CORE 0 STARTS HERE
########################################################
# Debug cache for memorising a few sampling loops
debug_cache = Debug_cache()
@micropython.viper
def streaming_loop_core_0():
    '''Prints data from memory to stdout in 'half-buffer' chunks.'''
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

    def sync_test(cell1: int, cell2: int):
        global flags
        # If synchronisation fails, the ADC outputs will latch to the same
        # values on successive samples. We compare them to check:
        if cells_mv[cell1] == cells_mv[cell2]:
            # Raise RESYNC flag.
            flags = flags | RESYNC

    # Now loop...
    while flags & STREAMING:
        # Wait while Core 1 is filling up page 0.
        while (cell & PAGE_BIT) == PAGE0:
            continue
        transfer_buffer(p0_mv)
        sync_test(P0_CELL_A, P0_CELL_B)
        # Wait while Core 1 is filling up page 1.
        while (cell & PAGE_BIT) == PAGE1:
            continue
        transfer_buffer(p1_mv)
        sync_test(P1_CELL_A, P1_CELL_B)

    if DEBUG:
        print('Streaming_loop_core_0() exited.')
        print('Here are the contents of debug buffer memory:')
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
