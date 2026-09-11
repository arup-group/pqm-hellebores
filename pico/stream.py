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
import array
from machine import Pin
import gc
import _thread
import sys
import binascii
from micropython import const

########################################################
######### Configuration constants
########################################################


# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# This maintains code paths as much as possible, but outputs progress and
# diagnostic information. Instead of pushing sample data to stdout, it caches
# snips of sample data in a dedicated buffer and exits the program after a few
# cycles to then print it out.
DEBUG = const(True)


# These settings can be adjusted via comms from the Pi via command line
# arguments.
# Try sample rates of 7.812k, 15.625k, 31.250k
# SPI frequency may operate up to 12MHz
# CPU frequency may operate up to 200MHz

# EXAMPLE COMMAND LINE
# When overriding these on the command line, write them in this exact order
# without option tags, eg
# stream.py 1x 1x 1x 1x 15.625k viper 6000000 160000000
# will increase the sample rate to 15.625k, switch to the viper optimiser
# and increase the cpu clock speed from 125MHz to 160Mhz.
DEFAULT_CAPTURE_SETTINGS = { 'gains':       ['1x', '1x', '1x', '1x'],
                             'sample_rate': '7.812k',
                             'optimisation': 'asm_thumb',
                             'spi_frequency': 6000000,
                             'pico_cpu_frequency': 125000000 }


# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work
# easily. The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes is BUFFER_SIZE * 8 because
# we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE             = const(1024)
PENULTIMATE_CELL        = const(BUFFER_SIZE - 2)
FINAL_CELL              = const(BUFFER_SIZE - 1)
# Bit-and the cell variable with WRAP_MASK after incrementing it, to make the
# pointer circular.
WRAP_MASK               = const(BUFFER_SIZE - 1)
# PAGE_BOUNDARY is used for testing transition between first and second pages
# of buffer memory. The buffer is divided into two to prevent clashes between
# memory reading and memory writing.
PAGE_BOUNDARY           = const(BUFFER_SIZE // 2)


# flags: operation flags used to control program flow on both CPU cores.
STOP        = const(0b0001)       # tells both cores to exit
RESET       = const(0b0010)       # initiate a machine reset
RESYNC      = const(0b0100)       # perform a soft reset on the ADC
STREAMING   = const(0b1000)       # fast ADC streaming using both cores

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

# RP2040 hardware related constants
SPI0_BASE   = const(0x4003c000)
# Constants required to set up and detect edge transitions on the data request
# (DR*) pin
# Refer to Section 2.19.6.1 in RP2040 datasheet
# IO_BANK0 Registers (Base: 0x40014000)
IO_BANK0_BASE      = const(0x40014000)
# Core 0 Interrupt Enable (GPIO 0-7)
PROC0_INTE0        = const(IO_BANK0_BASE + 0x100)
# Core 1 Interrupt Enable (GPIO 0-7)
PROC1_INTE0        = const(IO_BANK0_BASE + 0x130)
# Pin and Interrupt Status (GPIO 0-7)
INTR0              = const(IO_BANK0_BASE + 0x0F0)
# GPIO 4 falling edge: (4 * 4) + 2 = bit 18
FALL_EDGE_GPIO4    = const(0x40000)   # 1 << 18


# Arrangement of bytes in the state bytearray
# They are word aligned so that they can be accessed
# and set atomically from both CPU cores
STATE_LAYOUT = {
    'cell': 0 | uctypes.UINT32,
    'flags': 4 | uctypes.UINT32,
}

########################################################
######### Global variables
########################################################
pins: dict                   # pin configuration for the Pico
spi_adc_interface: object    # object holding SPI interface configuration
state: object                # uctypes.struct shared state ('cell' and 'flags')
                             # which is instantiated inside the state_buf bytearray
state_buf: bytearray         # backing store for the state variable
state_addr: int              # 32 bit memory address of state_buf
acq: bytearray               # backing store for the storage buffer
p0_mv: memoryview            # page 0 of the storage buffer
p1_mv: memoryview            # page 1 of the storage buffer
cells_mv: tuple              # tuple containing memoryviews of the individual
                             # cells of the buffer (one memoryview per cell)


########################################################
######### Hardware control functions
########################################################
def set_cpu_core_voltage(value):
    '''Set cpu core voltage, required for enhancing CPU speed.'''
    # NB, machine default is 1.10V
    VREG_CTRL = 0x40064000
    VOLTAGE_LOOKUP = { '1.05': 0x0a, '1.10': 0x0b, '1.15': 0x0c, '1.20': 0x0d }

    # Clear VSEL bits and apply new setting
    vsel_val = VOLTAGE_LOOKUP[f'{value:.2f}']
    reg = machine.mem32[VREG_CTRL]
    reg = (reg & ~0xf0) | ((vsel_val & 0x0f) << 4)
    machine.mem32[VREG_CTRL] = reg

    # Wait for voltage to stabilise before returning
    time.sleep(0.01)


def configure_cpu_frequency():
    '''This function needs to be called early to allow SPI clock rates to
    be correctly computed.'''
    MAX_CPU_FREQUENCY = const(200000000)
    try:
        required_cpu_frequency = int(capture_settings['pico_cpu_frequency'])
        # For faster speeds, we need to increase cpu core voltage.
        if required_cpu_frequency > 133000000:
            set_cpu_core_voltage(1.15)
        machine.freq(min(required_cpu_frequency, MAX_CPU_FREQUENCY))

    except:
        if DEBUG:
            print(f'There was an exception setting the CPU frequency to '
                  f'{capture_settings['pico_cpu_frequency']}.')
            print(f'Defaulting to standard system frequency of 125MHz')
        machine.freq(125000000)


def configure_dr_pin_edge_detection():
    '''This enables an edge latching feature on GPIO4 specifically (DR*). It means
    that we will definitely catch the data ready pulse, even if it is short in
    length. However, after we pick it up we have to clear the latch each time.'''
    # Enable hardware edge detection on GPIO 4
    machine.mem32[PROC1_INTE0] |= FALL_EDGE_GPIO4

    # Clear any stale latched edge (W1C)
    machine.mem32[INTR0] = FALL_EDGE_GPIO4


def configure_pins():
    '''Pico pin setup, referenced by a global variable 'pins'. Pins labelled *
    are active low. We initialise with the RESET* and CS* pins high, since we
    don't want them to operate until needed.'''
    global pins
    pins = {
        'pico_led'    : Pin(25, Pin.OUT, value=0),      # led on the Pico
        'buffer_led'  : Pin(15, Pin.OUT, value=0),      # 'buffer' LED on PCB
        'cs_adc'      : Pin(1, Pin.OUT, value=1),       # chip select* pin ADC
        'sck_adc'     : Pin(2, Pin.OUT, value=0),       # SPI interface clock
        'sdi_adc'     : Pin(3, Pin.OUT, value=0),       # input to ADC (from Pico)
        'sdo_adc'     : Pin(0, Pin.IN, Pin.PULL_DOWN),  # output from ADC (to Pico)
        'reset_adc'   : Pin(5, Pin.OUT, value=1),       # reset* ADC
        'dr_adc'      : Pin(4, Pin.IN, Pin.PULL_UP),    # data ready* from ADC
        'reset_me'    : Pin(14, Pin.IN, Pin.PULL_DOWN), # reset Pico (from Pi)
        'flags_select': Pin(26, Pin.IN, Pin.PULL_DOWN)  # NOT USED
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
    # spi_frequency is a configurable clock speed for comms on the SPI bus between
    # Pico and ADC. Its setting is independent from the sampling rate, but needs
    # to be fast enough to complete communication of 8 bytes in the period between
    # successive samples.

    spi_adc_interface = machine.SPI(0,
                                    baudrate   = capture_settings['spi_frequency'],
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


def setup_adc():
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
        g3, g2, g1, g0 = [ G[k] for k in capture_settings['gains'] ]
    except KeyError:
        g3, g2, g1, g0 = [ G[k] for k in ['1x', '1x', '1x', '1x'] ]
    gain_bits = (g3 << 9) + (g2 << 6) + (g1 << 3) + g0
    bs = bytes([0x00, gain_bits >> 8, gain_bits & 0b11111111])
    if DEBUG:
        print('GAIN register.')
    set_adc_register(GAIN, bs)

    # Set the status and communication register 0x0c
    # required bytes are:
    # CONSIDER MAKING THIS 0b10011000 = 0x98 TO MAKE DR NON-FLOATING
    # 0x98 = 0b10011000: 10 READ address increments on TYPES, 0 WRITE address
    # does not increment, 1 DR_HIZ* DR is active high/low, 1 DR_LINK
    # only 1 DR pulse is generated, 0 WIDTH_CRC is 16 bit, 00 WIDTH_DATA is 16
    # bits.
    # 0x00 = 0b00000000: 0 EN_CRCCOM CRC, 0 EN_INT CRC interrupt both disabled
    # 0x0f = 0b00001111: 1111 DRSTATUS data ready status bits for channels
    if DEBUG:
        print('STATUSCOM register.')
    set_adc_register(STATUSCOM, bytes([0x98, 0x00, 0x0f]))

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
        bs = bytes([0x24, osr_table[capture_settings['sample_rate']], 0x50])
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
######### Hardware interrupt configuration
########################################################
def configure_hardware_interrupt(command: str ='enable'):
    # we need this auxiliary function, because we can't easily assign to
    # a global variable within a lambda expression
    def reset():
        global state
        state.flags = RESET

    if command == 'enable':
        # Bind pin transition to interrupt handler.
        # We use hard interrupt for the RESET pin so that the reset works even
        # within a blocking function (eg serial write). We defer the actual
        # hardware reset until cleanup has happened, including core 1 exiting.
        pins['reset_me'].irq(trigger = Pin.IRQ_RISING,
                           handler = reset, hard=True)

    elif command == 'disable':
        pins['reset_me'].irq(handler = None)



########################################################
######### Debug memory configuration
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


########################################################
######### Buffer and state memory configuration
########################################################
def get_unstriped_bank_starts(buf: bytearray) -> tuple[int, int, int, int]:
    '''Maps default striped memory buffer as provided by micropython
    allocator across to 4x unstriped memory buffers (base addresses provided).'''
    # NOTE: This simple implementation assumes that the base address of the input
    # bytearray is 4-word (16 byte) aligned. This has been the case for all
    # tested firmware, but is not guaranteed. Hence trap is provided. If
    # implementation needs to handle 1-word (4 byte) alignment then we could
    # allocate a slightly larger buffer and offset 4 bytes into each stripe.
    addr = uctypes.addressof(buf)
    assert addr & 0xf == 0, 'Buffer bytearray is not aligned on SRAM0.'

    striped_offset = addr - 0x20000000
    # unstriped offset stride is 'divide by 4' compared to the striped offset
    unstriped_offset = striped_offset >> 2

    return (
        0x21000000 + unstriped_offset,
        0x21010000 + unstriped_offset,
        0x21020000 + unstriped_offset,
        0x21030000 + unstriped_offset
    )


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by various memoryview objects that point
    to different portions of it. By default, buffer memory allocated from global
    heap is striped across 4 x 64kB memory regions, with striping at 32 bit
    word boundaries. When we are accessing memory from 2 CPU cores, we want to
    avoid accessing the same memory region from both cores simultaneously (one
    access will be delayed by the DMA scheduler).
    Consequently, we re-map the allocated bytearray into memoryview objects that
    are in contigous memory regions, using the unstriped memory mapping of the
    underlying bytearray.
    This memory layout means that at a hardware level, reading and writing from
    different pages can occur in the same clock cycle.
    EXAMPLE:
    Default striped mapping of a bytearray:
    W0 W1 W2 W3 (16 bytes)
    W0 W1 W2 W3 (16 bytes)
    W0 W1 W2 W3 (16 bytes)
    W0 W1 W2 W3 (16 bytes)
    ...
    Map this to:
    W0 W0 W0 W0 ... (page 0 contiguous unstriped memory)
    W1 W1 W1 W1 ... (page 1 contiguous unstriped memory)
    W2 W2 W2 W2 ... (we don't use page 2)
    W3 W3 W3 W3 ... (we don't use page 3)
    '''
    global acq
    global p0_mv, p1_mv, cells_mv

    # 2 bytes per channel, 4 channels
    # We allocate 16 bytes per sample, and use only slices of it that
    # align with specific physical memory banks in the Pico.
    # Subsequently, we use only stripes 0 and 1 and 'waste' the memory
    # that lands in stripes 2 and 3.

    # The required page size for 2 pages is BUFFER_SIZE * 8 bytes / 2
    page_memory_size = BUFFER_SIZE * 8 // 2
    # We have to allocate total memory across four stripes even though
    # our intention is to use only memory from two stripes.
    buffer_memory_size = page_memory_size * 4
    acq = bytearray(buffer_memory_size)

    # Create memoryviews for two unstriped regions of the buffer.
    (p0_address, p1_address, _, _) = get_unstriped_bank_starts(acq)
    p0_acq = uctypes.bytearray_at(p0_address, page_memory_size)
    p1_acq = uctypes.bytearray_at(p1_address, page_memory_size)
    p0_mv = memoryview(p0_acq)
    p1_mv = memoryview(p1_acq)

    # Create an array of memoryviews that are slices of the buffer memoryview.
    # These point to each individual storage cell of the buffer.
    cells_list =      [ memoryview(p0_mv[i:i+8]) for i in range(0, len(p0_mv), 8) ]
    cells_list.extend([ memoryview(p1_mv[i:i+8]) for i in range(0, len(p1_mv), 8) ])

    # Convert to a tuple for a slight performance gain
    cells_mv = tuple(cells_list)


def configure_state_memory():
    '''State memory contains the cell and flags state variables. We set these up
    to occupy memory stripes 3 and 4. This avoids them clashing with memory used
    for sample buffer and reduces the likelihood of bus contention between cores
    0 and 1 for memory access.'''
    global state, state_addr, state_buf

    # Instantiate the state variables in memory
    # A bytearray is used for the backing store so that we can discover its
    # address and read/write to memory directly from assembler and viper, as
    # well as via native micropython access via the 'state' object
    state_buf = bytearray(16)

    # We have a cunning plan. We want to deliberately insert 'cell' in SRAM2
    # and 'flags' in SRAM3. This ensures that there is no memory bus contention
    # between state memory access and buffer memory access, which uses unstriped
    # memory in SRAM0 and SRAM1.
    # Check we are 4-word (16 byte aligned)
    state_addr = uctypes.addressof(state_buf)
    assert state_addr & 0xf == 0, 'State bytearray is not aligned on SRAM0.'

    # Offset starting address that we use in the bytearray to SRAM2.
    # This is the mechanism we use to ensure memory read/writes to the two state
    # variables do not interface or block read/writes to the sample buffer.
    state_addr = state_addr + 8
    state = uctypes.struct(state_addr, STATE_LAYOUT, uctypes.LITTLE_ENDIAN)


########################################################
######### READING LOOP (CORE 1) STARTS HERE
########################################################
# 1. Assembly function, with fixed input parameters which will be set in a wrapper
# function
@micropython.asm_thumb
def _asm_streaming_loop_inner_core(r0, r1, r2):
    # r0 = state_addr  (0=cell, 4=flags)
    # r1 = p0_addr     (base address of Page 0)
    # r2 = CONSTANTS   (INTR0, FALL_EDGE_GPIO4, SPI0_BASE, BUFFER_SIZE)
    # r3 = reserved    (used for cell index)

    # Allocate r3 to hold the cell index, for the life of the function
    ldr(r3, [r0, 0])

    # In use: r0, r1, r2, r3 and we do not clobber them at any point

    # Off we go
    label(MAIN_LOOP_START)

    # 0. Set up constants
    # get INTR0 address into r4, and FALL_EDGE_GPIO4 into r5
    ldr(r4, [r2, 0])       # INTR0
    ldr(r5, [r2, 4])       # FALL_EDGE_GPIO4
    mov(r6, STREAMING)     # we can directly load this constant, because STREAMING <= 255

    # 1. Begin spin loop, waiting for a new sample to be ready
    label(SPIN_LOOP_START)

    # 1a. Check if state.flags == STREAMING...
    ldr(r7, [r0, 4])
    tst(r6, r7)            # if zero, we're not STREAMING, we quit
    beq(MAIN_LOOP_EXIT)

    # 1b. ...then check for DR falling edge
    ldr(r7, [r4, 0])       # Read from INTR0
    tst(r7, r5)            # Test if bit 18 is set
    beq(SPIN_LOOP_START)   # if zero, DR* hasn't fired yet, loop back

    # 2. OK, we're clear to read from SPI. Clear the DR latch event (write-1-to-clear)
    str(r5, [r4, 0])       # Write back to INTR0, to clear the latch

    # 3. Target Address Calculation (Dynamic from r2)
    # 3a. PAGE_BOUNDARY: r7 = BUFFER_SIZE // 2
    ldr(r7, [r2, 12])      # r7 = BUFFER_SIZE
    lsr(r7, r7, 1)         # r7 = r7 >> 1 (samples per page)

    # 3b. Sample offset within page: (cell & mask) * 8 bytes, into r5
    sub(r4, r7, 1)         # r4 = mask (e.g. 0x3F, 0x7F, 0xFF)
    mov(r5, r3)            # r5 = cell index
    and_(r5, r4)           # r5 = sample_in_page = cell & mask
    lsl(r5, r5, 3)         # r5 = byte_offset_in_page (we stride at 8 bytes per sample)

    # 3c. Page offset in unstriped memory map, into r6:
    mov(r6, 0)             # Default to Page 0
    tst(r3, r7)            # Tests if MSB is set in the cell index
    beq(ON_PAGE_0)         # Jump if result is zero, r6 = 0x0
    mov(r6, 1)             # Ok, we're on Page 1
    lsl(r6, r6, 16)        # r6 = 0x10000
    label(ON_PAGE_0)

    # 3d. Total target RAM address = p0_addr + page_offset + byte_offset_in_page
    add(r4, r5, r6)        # r4 = r5 + r6
    add(r4, r1, r4)        # r4 = r1 + r5 + r6 (target_addr)

    # In use: r0-r3, r4=target RAM address for the current cell

    # 4. Drive the SPI bus
    # Burst write 8 x dummy bytes (trigger 64 SCK cycles)
    ldr(r5, [r2, 8])       # SPI0_BASE
    mov(r6, 0)
    str(r6, [r5, 8])       # Byte 0
    str(r6, [r5, 8])       # Byte 1
    str(r6, [r5, 8])       # Byte 2
    str(r6, [r5, 8])       # Byte 3
    str(r6, [r5, 8])       # Byte 4
    str(r6, [r5, 8])       # Byte 5
    str(r6, [r5, 8])       # Byte 6
    str(r6, [r5, 8])       # Byte 7

    # 5. Wait for SPI to complete the current transmission
    mov(r7, 0x10)          # RFF bit mask (0b010000)
    label(WAIT_RX_FULL)
    ldr(r6, [r5, 12])      # Load SSPSR
    tst(r6, r7)            # RFF is set only when all 8 transfers are complete
    bne(WAIT_RX_FULL)      # Loop back until this is true

    # In use: r0-r3, r4=target address, r5=SPI0_BASE

    # 6. Read 8 bytes and store to memory
    ldr(r6, [r5, 8])       # Ch 0, MSB
    strb(r6, [r4, 0])
    ldr(r6, [r5, 8])       # Ch 0, LSB
    strb(r6, [r4, 1])
    ldr(r6, [r5, 8])       # Ch 1, MSB
    strb(r6, [r4, 2])
    ldr(r6, [r5, 8])       # Ch 1, LSB
    strb(r6, [r4, 3])
    ldr(r6, [r5, 8])       # Ch 2, MSB
    strb(r6, [r4, 4])
    ldr(r6, [r5, 8])       # Ch 2, LSB
    strb(r6, [r4, 5])
    ldr(r6, [r5, 8])       # Ch 3, MSB
    strb(r6, [r4, 6])
    ldr(r6, [r5, 8])       # Ch 3, LSB
    strb(r6, [r4, 7])

    # In use: r0-r3 only

    # 7. Increment and wrap the cell pointer
    ldr(r4, [r2, 12])      # BUFFER_SIZE into r4
    sub(r4, r4, 1)         # make a wrap mask
    add(r3, r3, 1)         # increment the cell index
    and_(r3, r4)           # 'and' with the wrap mask to circulate the index
    str(r3, [r0, 0])       # save cell index to state.cell

    b(MAIN_LOOP_START)

    # 8. Jump to here for exit
    label(MAIN_LOOP_EXIT)


# 2. Create a wrapper function that binds in the state_addr
# value determined at run time
def _asm_streaming_loop_inner():
    '''Adds some code to flip the SPI interface into and out of 16 bit operation,
    around the assembly routine.'''
    CONSTANTS = array.array('I', [
        INTR0,            # Offset 0 (0 bytes)
        FALL_EDGE_GPIO4,  # Offset 1 (4 bytes)
        SPI0_BASE,        # Offset 2 (8 bytes)
        BUFFER_SIZE       # Offset 3 (12 bytes)
    ])
    # Inner sampling loop -- high-performance inline assembly
    p0_addr = uctypes.addressof(p0_mv)
    _asm_streaming_loop_inner_core(state_addr, p0_addr, CONSTANTS)


def wait_for_falling_edge_hw():
    # Spin tightly until the hardware latches the edge
    while not (machine.mem32[INTR0] & FALL_EDGE_GPIO4):
        pass
    # Acknowledge / clear the event
    machine.mem32[INTR0] = FALL_EDGE_GPIO4


# NOT USED YET
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


# NOT USED YET
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
    if capture_settings['optimisation'] == 'asm_thumb':
        streaming_loop_inner = _asm_streaming_loop_inner
    else:
        pass
        # streaming_loop_inner = _viper_streaming_loop_inner

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
    # Note that in DEBUG mode, transfer_buffer can pull us out of STREAMING,
    # so we check the flag after writing the buffer.
    while True:
        # Wait while we fill page 0, then transfer it
        while state.cell < PAGE_BOUNDARY:
            continue
        buffer_led_pin_on()
        transfer_buffer(p0_mv)
        buffer_led_pin_off()
        if not state.flags & STREAMING:
            break
        # Wait while we fill page 1, then transfer it
        while state.cell >= PAGE_BOUNDARY:
            continue
        buffer_led_pin_on()
        transfer_buffer(p1_mv)
        buffer_led_pin_off()
        if not state.flags & STREAMING:
            break
        # Check to see if ADC readouts have latched to a constant value.
        # This function will raise a flag if necessary and the other CPU
        # core will reset ADC comms.
        latch_test(state_addr, cells_mv[FINAL_CELL], cells_mv[PENULTIMATE_CELL])

    if DEBUG:
        print('Streaming_loop_core_0() exited.')
        print('Here are the contents of debug buffer memory:')
        print(debug_cache.as_text())
    gc.collect()


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


def prepare_to_stream():
    '''Configures all the pre-requisities: pins, SPI interface, ADC settings,
    interrupts and garbage collection.'''

    if DEBUG:
        print('Configuring SPI interface.')
    # SPI library setup
    configure_adc_spi_interface()

    if DEBUG:
        print('Configuring ADC.')
    # Push required settings into the ADC.
    hard_reset_adc()
    setup_adc()

    if DEBUG:
        print('Configuring DR* edge detection.')
    configure_dr_pin_edge_detection()

    if DEBUG:
        print('Disabling garbage collection.')
    # We don't want garbage collection pauses while streaming, so we clean up
    # now and then disable the automatic GC.
    gc.collect()
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
    #     debug_cache:        cache fills up in DEBUG mode.



def cleanup():
    '''For debugging, it's useful for the Pico to be returned to a quiescent
    mode.'''
    stop_adc()
    gc.enable()
    configure_hardware_interrupt('disable')


def try_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return val


def read_arguments():
    # We can pass configuration variables into the program from main.py
    # via the sys.argv variable.
    # sys.argv = [ 'stream.py', '1x', '1x', '1x', '1x', '7.812k', 'asm_thumb', '6000000', '125000000' ]
    # The variables are loaded into the capture_settings dictionary.
    # capture_settings = { 'gains':       ['1x', '1x', '1x', '1x'],
    #                      'sample_rate': '7.812k',
    #                      'optimisation': 'asm_thumb',
    #                      'spi_frequency': 6000000,
    #                      'cpu_frequency': 125000000 }
    argv = sys.argv
    capture_settings = DEFAULT_CAPTURE_SETTINGS
    capture_settings_keys = [ 'gains', 'sample_rate', 'optimisation', 'spi_frequency', 'pico_cpu_frequency' ]
    # brutal parser requires optional arguments to be provided in specific order
    try:
        if len(argv) >= 1:
            # dispose of first entry (program name)
            argv.pop(0)
        # read the gains and any other arguments provided
        if len(argv) >= 4:
            capture_settings[capture_settings_keys.pop(0)] = argv[:4]
            argv = argv[4:]
            # deal with remaining arguments one by one
            # if an argument can be expressed as an integer, it should be stored as one
            while len(argv) >= 1:
                capture_settings[capture_settings_keys.pop(0)] = try_int(argv.pop(0))
    except:
        if DEBUG:
            print(f'There was an exception reading arguments {sys.argv}')
    if DEBUG:
        print(f'stream.py started with parameters {capture_settings}.')
    return capture_settings


def main():
    global state, capture_settings
    try:
        # Adjust settings for command line arguments
        capture_settings = read_arguments()

        # Setup microcontroller hardware
        configure_cpu_frequency()
        configure_pins()
        configure_hardware_interrupt('enable')

        # Buffer memory is set up in various memoryview structures that point to
        # an underlying bytearray that holds a buffer of ADC samples. These
        # objects are declared global so that the memory can be reached by both
        # CPU cores.
        configure_buffer_memory()

        # Instantiate the state variables in memory
        # A bytearray is used for the backing store so that we can discover its
        # address and read/write to memory directly from assembler and viper, as
        # well as via native micropython access via the 'state' object
        configure_state_memory()

        # Now initialise the state elements (cell and flags)
        state.cell = 0            # always lands in SRAM2
        state.flags = STREAMING   # always lands in SRAM3

        # Loop while flags indicate that we are in STREAMING mode
        while state.flags == STREAMING:
            prepare_to_stream()
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
        else:
            # If we're not debugging, soft reboot the machine
            state.flags = RESET

    except Exception as e:
        # Catch other exceptions.
        if DEBUG:
           err_type = type(e)
           print(f'There was an exception of type {err_type}.')
           state.flags = STOP
        else:
           state.flags = RESET

    finally:
        # If we reach here, STOP or RESET flags are raised.
        cleanup()
        if DEBUG:
            print(f'Stopping with state.flags = {state.flags}, '
                  f'state.cell = {state.cell}.')
        if state.flags & RESET:
            if DEBUG:
                print('The RESET flag was raised: resetting Pico shortly.')
            # allow time for the hardware reset pin to clear to normal
            time.sleep(1)
            pins['pico_led'].low()
            machine.reset()


# Run from here
if __name__ == '__main__':
    main()
