# To run on Raspberry Pi Pico microcontroller, communicating with MCP3912
# 4-channel ADC via SPI serial interface, and host computer via USB serial
# interface. The code provides a circular buffer for precisely timed incoming
# measurements signalled by the ADC (via the data ready, DR* pin), and sends
# output from the buffer in blocks of 64x4x16 bit integer values.

# BE VERY CAREFUL WITH EDITING! GARBAGE COLLECTOR IS SWITCHED OFF IN INNER
# LOOPS TO MAINTAIN PERFORMANCE. MEMORYVIEW OBJECTS ARE USED TO AVOID NEW
# MEMORY ALLOCATIONS.

# DOUBLE CHECK ANY OUTPUT ASSERTIONS. HARDWARE DAMAGE IS POSSIBLE IF PINS ARE
# ASSERTED INCORRECTLY IE ASSERTING OUTPUT STATE TO A PIN THAT IS WIRED TO
# THE OUTPUT OF ANOTHER DEVICE.

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

# SPI_CLOCK_RATE is a configurable clock speed for comms on the SPI bus between
# Pico and ADC. Its setting is independent from the sampling rate, but needs
# to be fast enough to complete communications in the period between successive
# samples.
SPI_CLOCK_RATE = const(6000000)

# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# This maintains code paths as much as possible, but outputs progress and
# diagnostic information. Instead of pushing sample data to stdout, it caches
# snips of sample data in a dedicated buffer and exits the program after a few
# cycles to then print it out.
DEBUG = const(False)

# Flag to activate the asm.thumb code paths. Switching to 'False' allows
# original micropython implementation to run. NB: micropython maxes out
# at a sample rate of 15.625k, while assembler can run to 31.250k samples/sec.
ASM_THUMB = const(True)

# These adc settings can be adjusted via comms from the Pi via command line
# arguments. try 7.812k, 15.625k, 31.250k
DEFAULT_ADC_SETTINGS = { 'gains':       ['1x', '1x', '1x', '1x'],
                         'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work
# easily. The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes is BUFFER_SIZE * 8 because
# we have 4 measurement channels and 2 bytes per channel.
# NOTE: Hard coded optimisation is included in acquistion inner loop that reflects
# an exact buffer size of 256 samples, and the unstriped memory layout. Verify
# the effect om that code if changes are to be made to the buffer size here.
BUFFER_SIZE             = const(256)
BUFFER_MEMORY_SIZE      = const(2048)
PENULTIMATE_CELL        = const(BUFFER_SIZE - 2)
FINAL_CELL              = const(BUFFER_SIZE - 1)

# flags: operation flags used to control program flow on both CPU cores.
STOP        = const(0b0001)       # tells both cores to exit
RESET       = const(0b0010)       # initiate a machine reset
RESYNC      = const(0b0100)       # perform a soft reset on the ADC
STREAMING   = const(0b1000)       # fast ADC streaming using both cores

# cell:  sample pointer 0 to 255.
# Bit-and the cell variable with WRAP_MASK after incrementing it, to make the
# pointer circular. Increment from 255 & WRAP_MASK wraps round to 0.
# WARNING: WRAP_MASK must be an integer between 0 and 255 (8-bit immediate).
# Values > 255 will cause a compilation error in the ARM Cortex-M0+ 'mov' instruction.
WRAP_MASK   = const(0b11111111)

# The following constants are used to test whether a page boundary has
# been crossed, and therefore time to output the next page of sample buffer.
# The cell variable is bit-anded with the PAGE_BITS bit mask and the result
# checked against PAGEn constants.
PAGE_BITS   = const(0b11000000)   # test page number
PAGE0       = const(0b00000000)   # bit76==00: in range 0-63, ie page 0
PAGE1       = const(0b01000000)   # bit76==01: in range 64-127, ie page 1
PAGE2       = const(0b10000000)   # bit76==10: in range 128-191, ie page 2
PAGE3       = const(0b11000000)   # bit76==11: in range 192-255, ie page 3

# ADC register addresses
PHASE       = const(0x0a)
GAIN        = const(0x0b)
STATUSCOM   = const(0x0c)
CONFIG0     = const(0x0d)
CONFIG1     = const(0x0e)
LOCK_CRC    = const(0x1f)

# ADC commands
ADC_WRITE   = const(0x40)
ADC_READ    = const(0x41)

# RP2040 SPI0 base address
SPI0_BASE   = const(0x4003c000)


########################################################
######### Global variables
########################################################
pins: dict                   # pin configuration for the Pico
spi_adc_interface: object    # object holding SPI interface configuration
state: object                # uctypes.struct shared state ('cell' and 'flags')
state_addr: int              # 32 bit memory address of the state variable
p0_mv: bytearray             # page 0 of the storage buffer (64 cells)
p1_mv: bytearray             # page 1 of the storage buffer (64 cells)
p2_mv: bytearray             # page 2 of the storage buffer (64 cells)
p3_mv: bytearray             # page 3 of the storage buffer (64 cells)
cells_mv: tuple              # tuple containing memoryviews of the individual
                             # cells of the buffer (one memoryview per cell)


########################################################
######### Hardware control functions
########################################################
def configure_cpu_speed(adc_settings: dict):
    '''This function needs to be called early to allow SPI clock rates to
    be correctly computed.'''
    if adc_settings['sample_rate'] == '31.250k':
        # Some CPU overclocking is required at highest sample rate to
        # achieve USB serial transfer speed needed.
        # Increase CPU speed from default of 133 MHz to 200 MHz
        machine.freq(200000000)
    else:
        # For all other sample rates, we leave the CPU at default speed.
        pass


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


def start_adc():
    '''Tell the ADC to read out the ADC registers in multiple-read mode. It's
    necessary for the CS pin to be held low from this point, for the duration
    of sampling.'''
    if DEBUG:
        print('Starting the ADC...')
    pins['cs_adc'].low()
    # Start reading from address 0x00 using 8-bit command byte
    spi_adc_interface.write(bytes([0x41]))


def stop_adc():
    '''Tell the ADC to stop sampling.'''
    # Note that the DR* pin continues to cycle, so it's necessary to also stop
    # interrupts if we want to stop processing completely
    if DEBUG:
        print('Stopping the ADC...')
    pins['cs_adc'].high()


########################################################
######### Interrupt configuration and handling functions
########################################################
# ARM thumb assembly implementation of _adc_read_handler() python function
# (see below).
# 1. This is the raw assembly function. It expects the address of the state
# object memory location in r1.
@micropython.asm_thumb
def _asm_adc_read_handler_core(r0, r1):
    # r0 = pin object (passed by IRQ, unused)
    # r1 = state_addr (explicitly passed by our wrapper)

    # Load current index from state_addr pointer (state.cell)
    ldr(r2, [r1, 0])

    # Increment the index
    add(r2, r2, 1)

    # Apply 8-bit WRAP_MASK (e.g., 255)
    mov(r3, WRAP_MASK)
    and_(r2, r3)

    # Store the wrapped index back into memory
    str(r2, [r1, 0])


# 2. This factory creates the clean IRQ binding callback
def create_asm_adc_read_handler() -> object:
    '''Creates a compilable wrapper function for the Pico IRQ dispatcher.'''
    # We return a lambda/function that locks 'state_addr' into the core
    # assembly routine via a closure
    def _asm_adc_read_handler(_):
        _asm_adc_read_handler_core(_, state_addr)

    return _asm_adc_read_handler


@micropython.viper
def _viper_adc_read_handler_core(_, state_addr: int):
    '''Micropython implementation of IRQ callback function'''
    # we use the ptr32 pointer to allow viper optimisation by direct
    # access to the memory holding the cell index.
    # 'anding' the value with a bit mask that has binary '0' in the bit
    # above the largest buffer pointer makes the buffer pointer circulate
    # to zero without needing an 'if' conditional: this means the
    # instruction executes in constant time
    p_state: ptr32 = ptr32(state_addr)
    p_state[0] = (p_state[0] + 1) & WRAP_MASK


def create_viper_adc_read_handler() -> object:
    '''We make a python closure around the state_addr variable'''
    def _viper_adc_read_handler(_):
        _viper_adc_read_handler_core(_, state_addr)

    return _viper_adc_read_handler


def configure_interrupts(command: str ='enable'):
    '''Two interrupt handlers are set up, one for the DR* pin, for notifying
    Pico that new data is ready for reading from the ADC, and a reset command
    from the Pi, to help with run-time error recovery.'''

    # Use the accelerated assembler interrupt handler if ASM_THUMB is True.
    if ASM_THUMB:
        # Create inline Thumb assembly interrupt handler targeting RAM address
        # of state_buf directly
        adc_read_handler = create_asm_adc_read_handler()
    else:
        # otherwise use the viper handler
        adc_read_handler = create_viper_adc_read_handler()


    # we need this helper function, because we can't easily assign to global
    # variable within a lambda expression
    @micropython.viper
    def set_flags(state_addr: int, required_flags: int):
        p_state: ptr32 = ptr32(state_addr)
        p_state[1] = required_flags

    if command == 'enable':
        # Bind pin transitions to interrupt handlers.
        # We use hard interrupt for the DR* pin to maintain tight timing,
        # and for the RESET pin so that the reset works even within a blocking
        # function (eg serial write). We defer the actual hardware reset until
        # cleanup has happened, including core 1 exiting
        pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING,
                           handler = adc_read_handler, hard=True)
        pins['reset_me'].irq(trigger = Pin.IRQ_RISING,
                           handler = lambda _: set_flags(state_addr, RESET), hard=True)

    elif command == 'disable':
        pins['dr_adc'].irq(handler = None)
        pins['reset_me'].irq(handler = None)



########################################################
######### Buffer and debug memory configuration
########################################################
class Debug_cache:

    def __init__(self: object):
        self.cache_pointer = 0
        self.cache = [ bytearray(32) for i in range(16) ]

    def reset(self: object):
        self.cache_pointer = 0

    def save_snip(self: object, bs: bytearray) -> bool:
        if self.cache_pointer <= 15:
            self.cache[self.cache_pointer][:] = bs[:32]
            self.cache_pointer += 1
            return True
        else:
            return False

    def as_text(self: object) -> str:
        text_out = ''
        for bs in self.cache:
            # NB 32 bytes become 64 characters.
            hs = binascii.hexlify(bs).decode('utf-8')
            text_out += f'{hs[0:16]} {hs[16:32]} {hs[32:48]} {hs[48:64]}\n'
        return text_out


def get_unstriped_regions(bs: bytearray) -> tuple:
    '''From a given bytearray or memoryview, finds the starting address and
    places some test data in the memory. Then searches for the unstriped
    form of the data across the unstriped memory space. Then computes
    starting addresses for each unstriped region and returns them as
    memoryview objects.
    '''
    length = len(bs)
    # write some test data into the bytearray
    test_data = b'abcdefghijklmnopqrstuvwxyz'
    clear_data = b'\x00' * len(test_data)
    if len(test_data) > length:
        print('ERROR: stream.py, get_unstriped_regions() was called with a '
              'bytearray that was too short.')
        sys.exit(1)
    bs[:len(test_data)] = test_data
    # with the test_data written into memory, adjacent words of the unstriped
    # memory region will have the following contents.
    search_data = test_data[0:4] + test_data[16:20]
    # Figure out base address offset into unstriped memory, searching the
    # first 64kB of unstriped address space. We want to find the last match of
    # search data: this avoids a false match on data in the run-time environment.
    offset = None
    # Memory allocations are word-aligned (32 bits) so we can step through in
    # 4 byte increments
    for i in range(0, 65536-length, 4):
        if uctypes.bytearray_at(0x21000000 + i, 8) == search_data:
            offset = i
    # Quit if we can't find the test data
    if offset == None:
        print('ERROR: stream.py, get_unstriped_regions() could not locate '
              'unstriped memory regions.')
        sys.exit(1)
    # clear the test data
    bs[:len(clear_data)] = clear_data
    # make bytearray objects that correspond to each page of unstriped memory
    p0_mv = memoryview(uctypes.bytearray_at(0x21000000 + offset, length // 4))
    p1_mv = memoryview(uctypes.bytearray_at(0x21010000 + offset, length // 4))
    p2_mv = memoryview(uctypes.bytearray_at(0x21020000 + offset, length // 4))
    p3_mv = memoryview(uctypes.bytearray_at(0x21030000 + offset, length // 4))
    return (p0_mv, p1_mv, p2_mv, p3_mv)


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
    global p0_mv, p1_mv, p2_mv, p3_mv
    global cells_mv

    # 2 bytes per channel, 4 channels
    acq = bytearray(BUFFER_MEMORY_SIZE)
    # Create memoryviews for each unstriped region of the buffer (ie four pages).
    p0_mv, p1_mv, p2_mv, p3_mv = get_unstriped_regions(acq)
    # Create an array of memoryviews for each storage cell of the buffer.
    cells_list =      [ memoryview(p0_mv[i:i+8]) for i in range(0, len(p0_mv), 8) ]
    cells_list.extend([ memoryview(p1_mv[i:i+8]) for i in range(0, len(p1_mv), 8) ])
    cells_list.extend([ memoryview(p2_mv[i:i+8]) for i in range(0, len(p2_mv), 8) ])
    cells_list.extend([ memoryview(p3_mv[i:i+8]) for i in range(0, len(p3_mv), 8) ])
    # Convert to a tuple for a slight performance gain
    cells_mv = tuple(cells_list)


########################################################
######### READING LOOP (CORE 1) STARTS HERE
########################################################
# 1. Raw assembly function, with base address of state variable and base address of
# page 0 in as parameters
@micropython.asm_thumb
def _asm_streaming_loop_inner_core(r0, r1, r2):
    # r0 = state_addr (points to state_buf in RAM: offset 0=cell, offset 4=flags)
    # r1 = p0_addr (base address of Page 0 in unstriped RAM)
    # r2 = spi_base (0x4003c000 for SPI0)

    # Load initial cell index into r3
    ldr(r3, [r0, 0])

    label(LOOP_START)

    # 1. Check if state.flags == STREAMING (flags at offset 4)
    ldr(r4, [r0, 4])
    mov(r5, STREAMING)
    cmp(r4, r5)
    bne(LOOP_EXIT)

    # 2. Read current state.cell (at offset 0)
    ldr(r4, [r0, 0])

    # 3. Check if cell index changed
    cmp(r4, r3)
    beq(LOOP_START)

    # Cell changed! Update cached cell index: r3 = r4
    mov(r3, r4)

    # 4. Calculate target RAM address for cell r4:
    # The fancy bit shifts are to reflect the page starting addresses, which
    # shift every 64 samples (512 bytes) and the jump per sample (8 bytes)
    # target_addr = p0_addr + ((cell & 0xC0) << 10) + ((cell & 0x3F) << 3)
    mov(r5, 0xc0)
    and_(r5, r4)       # r5 = cell & 0xC0
    lsl(r5, r5, 10)    # r5 = page_offset = (cell & 0xC0) * 1024

    mov(r6, 0x3f)
    and_(r6, r4)       # r6 = cell_in_page = cell & 0x3F
    lsl(r6, r6, 3)     # r6 = cell_offset = cell_in_page * 8

    add(r5, r5, r6)    # r5 = page_offset + cell_offset
    add(r5, r1, r5)    # r5 = target_addr = p0_addr + page_offset + cell_offset

    # 5. Read 64 bits (4 x 16-bit frames) from ADC via SPI0 hardware registers into target_addr [r5]
    # SPI0 SSPDR is at offset 8 ([r2, 8])
    # SPI0 SSPSR is at offset 12 ([r2, 12])

    # Burst write 4 x 16-bit dummy words (0x0000) to trigger 64 SCK pulses continuously
    mov(r7, 0)
    str(r7, [r2, 8])   # 16 SCK pulses (Channel 0)
    str(r7, [r2, 8])   # 16 SCK pulses (Channel 1)
    str(r7, [r2, 8])   # 16 SCK pulses (Channel 2)
    str(r7, [r2, 8])   # 16 SCK pulses (Channel 3)

    # Wait until Receive FIFO is not empty (SSPSR bit 2 RNE == 1)
    label(WAIT_RX)
    ldr(r7, [r2, 12])  # Load SSPSR
    mov(r4, 4)         # RNE bit mask (0b0100)
    and_(r7, r4)
    beq(WAIT_RX)

    # Read Channel 0 & Channel 1 (16 bits each) and pack into 32-bit Word 0
    ldr(r6, [r2, 8])   # Channel 0 (16 bits)
    ldr(r7, [r2, 8])   # Channel 1 (16 bits)
    lsl(r7, r7, 16)
    orr(r7, r6)        # r7 = (Ch 1 << 16) | Ch 0
    str(r7, [r5, 0])   # Store 32-bit Word 0 to target_addr + 0

    # Read Channel 2 & Channel 3 (16 bits each) and pack into 32-bit Word 1
    ldr(r6, [r2, 8])   # Channel 2 (16 bits)
    ldr(r7, [r2, 8])   # Channel 3 (16 bits)
    lsl(r7, r7, 16)
    orr(r7, r6)        # r7 = (Ch 3 << 16) | Ch 2
    str(r7, [r5, 4])   # Store 32-bit Word 1 to target_addr + 4

    # Loop back to wait for next sample
    b(LOOP_START)

    label(LOOP_EXIT)


# 2. Create a wrapper function that binds in the state_addr
# value determined at run time
def create_asm_streaming_loop_inner() -> object:
    '''Make a python closure around the global state_addr value, and add code
    to flip the SPI interface into and out of 16 bit operation.'''
    def _asm_streaming_loop_inner():
        # Inner sampling loop -- high-performance inline assembly
        # Dynamically switch RP2040 SPI0 hardware (SSPCR0 bits 3:0)
        # to 16-bit mode (DSS = 15) and back to 8-bit mode (DSS = 7) afterwards
        machine.mem32[SPI0_BASE] = (machine.mem32[SPI0_BASE] & ~0x0f) | 0x0f
        p0_addr = uctypes.addressof(p0_mv)
        _asm_streaming_loop_inner_core(state_addr, p0_addr, SPI0_BASE)
        machine.mem32[SPI0_BASE] = (machine.mem32[SPI0_BASE] & ~0x0f) | 0x07

    return _asm_streaming_loop_inner


@micropython.viper
def _viper_streaming_loop_inner_core(state_addr: int):
    '''This is a pure micropython SPI read loop optimised as much as we can
    without driving the SPI bus directly.'''
    p_state: ptr32 = ptr32(state_addr)
    # cell_p is a local cache of the cell variable, so that the inner loop
    # can synchronise to the moment when cell changes value
    cell_p: int = p_state[0]

    # Inner loop -- speed critical -- we do sampling here, nothing else.
    while p_state[1] == STREAMING:
        # Read out from the ADC *immediately* if the cell parameter changes
        # value, then repeat. Unfortunately we can't further optimise
        # the lookup cost of cells_mv, because 'readinto' requires a
        # micropython object and not a plain starting address
        p_state[0] == cell_p \
            or spi_adc_interface.readinto(cells_mv[(cell_p := p_state[0])])


def create_viper_streaming_loop_inner() -> object:
    '''Make a python closure around the global state_addr value.'''
    def _viper_streaming_loop_inner():
        _viper_streaming_loop_inner_core(state_addr)

    return _viper_streaming_loop_inner


def streaming_loop_core_1():
    '''Watches for change in state.cell (incremented by the inline assembly interrupt
    handler) and reads new data from the ADC into memory. Also watches for
    change in state.flags variable to enable clean exit or recovery from RESYNC
    condition.'''
    global state

    # Choose between assembler and viper optimisations
    if ASM_THUMB:
        streaming_loop_inner = create_asm_streaming_loop_inner()
    else:
        streaming_loop_inner = create_viper_streaming_loop_inner()

    # The RESYNC flag may be raised by Core 0 at any time, so we have to
    # allow for it in the outer loop test here by using a bitmask filter
    start_adc()
    while state.flags & STREAMING:
        streaming_loop_inner()
        # If Core 0 has raised RESYNC flag, we miss a few samples and deal
        # with it here.
        if state.flags & RESYNC:
            # Tell the ADC to stop and resychronise to the Pico.
            stop_adc()
            soft_reset_adc()
            start_adc()
            # Clear RESYNC flag
            state.flags = state.flags & ~RESYNC
            gc.collect()

    if DEBUG:
        print('Streaming_loop_core_1() exited')


########################################################
######### WRITING LOOP (CORE 0) STARTS HERE
########################################################
@micropython.viper
def latch_test(state_addr: int, cell1: ptr32, cell2: ptr32):
    # SPI clock synchronisation can fail during a large power disturbance.
    # If this happens, the ADC outputs will latch to the same values
    # on successive SPI reads. So we compare all the readings from two
    # samples to check, and set a RESYNC flag if necessary:
    # use native viper variables for the cell locations
    # two words (64 bits) contain a sample for all 4 channels
    p_state: ptr32 = ptr32(state_addr)
    #p1: ptr32 = ptr32(cell1)
    #p2: ptr32 = ptr32(cell2)
    # check if two successive cells are identical on all channels
    if cell1[0] == cell2[0] and cell1[1] == cell2[1]:
        # make successive cells different, in case we happen to check
        # them again before the RESYNC is completed.
        cell1[0] = uint(0xffffffff)
        cell2[0] = uint(0x00000000)
        # raise RESYNC flag
        p_state[1] = p_state[1] | RESYNC


def streaming_loop_core_0():
    '''Prints data from memory to stdout in chunks.'''

    # cache pin function lookups
    buffer_led_pin_on = pins['buffer_led'].on
    buffer_led_pin_off = pins['buffer_led'].off

    if DEBUG:
        # Create a cache for memorising output from a few sampling loops
        debug_cache = Debug_cache()

    def _transfer_buffer_debug(bs):
        global state
        # saves snips until the debug cache is full
        if not bool(debug_cache.save_snip(bs)):
            state.flags = STOP

    # select the transfer function we are going to use from now on
    if DEBUG:
        transfer_buffer = _transfer_buffer_debug
    else:
        transfer_buffer = sys.stdout.buffer.write

    # Now transfer buffers in turn and loop...
    while state.flags & STREAMING:
        # Wait while we fill pages 0 and 1, then transfer them both
        while state.cell < PAGE2:
            continue
        buffer_led_pin_on()
        transfer_buffer(p0_mv)
        transfer_buffer(p1_mv)
        buffer_led_pin_off()
        # Wait while we fill pages 2 and 3, then transfer them both
        while state.cell >= PAGE2:
            continue
        buffer_led_pin_on()
        transfer_buffer(p2_mv)
        transfer_buffer(p3_mv)
        buffer_led_pin_off()
        # Check to see if ADC readouts have latched to a constant value.
        # This function will raise a flag if necessary and the other CPU
        # core will reset ADC comms.
        latch_test(state_addr, cells_mv[FINAL_CELL], cells_mv[PENULTIMATE_CELL])

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
    global state, state_addr
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
        # Setup microcontroller hardware
        configure_cpu_speed(adc_settings)
        configure_pins()
        # Instantiate the state variables in memory
        # A bytearray is used for the backing store so that we can discover its
        # address and read/write to memory directly from assembler, as well as
        # via native micropython access via the 'state' object
        STATE_LAYOUT = {
            'cell': 0 | uctypes.UINT32,
            'flags': 4 | uctypes.UINT32,
        }
        state_buf = bytearray(8)
        state_addr = uctypes.addressof(state_buf)
        state = uctypes.struct(state_addr, STATE_LAYOUT, uctypes.LITTLE_ENDIAN)
        # Initialise the state elements (cell and flags)
        state.cell = 0
        state.flags = STREAMING
        while state.flags == STREAMING:
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
            if state.flags & RESET:
                # Show the world that we have a RESET situation...
                pins['pico_led'].high()
                # If the pin is not held high, we will return to streaming
                if not reset_pin_held_high():
                    state.flags = STREAMING
                    pins['pico_led'].low()

    except KeyboardInterrupt:
        # Catch CTRL-C here.
        if DEBUG:
            print('Interrupted.')
        # Stop Core 1.
        state.flags = STOP

    except Exception as e:
        # Catch other exceptions.
        if DEBUG:
           err_type = type(e)
           print(f'There was an exception of type {err_type}.')
        state.flags = RESET

    finally:
        # If we reach here, STOP or RESET flags are raised.
        cleanup()
        if state.flags & RESET:
            if DEBUG:
                print('Reset flag raised: resetting Pico shortly.')
            # allow the reset pin to clear to normal
            time.sleep(1)
            pins['pico_led'].low()
            machine.reset()


# Run from here
if __name__ == '__main__':
    main()
