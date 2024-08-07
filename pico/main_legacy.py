# To run on Raspberry Pi Pico microcontroller, communicating with MCP3912
# 4-channel ADC via SPI serial interface, and host computer via USB serial
# interface. The code provides a circular buffer for precisely timed incoming
# measurements signalled by the ADC (via the data ready, DR* pin), and sends
# output from the buffer in blocks of 64x4x16 bit integer values.

import time
import machine
import gc
import hashlib
import binascii
from machine import Pin
import _thread
import sys
from micropython import const


# __file__ isn't defined in micropython, so we have to define the file name explicitly
# this is used to do the MD5 check to help with version verification at runtime
PROGRAM_FILE_NAME = 'main.py'

# some constants are defined with the const() compilation hint to optimise performance
# SPI_CLOCK_RATE is a configurable clock speed for comms on the SPI bus between
# Pico and ADC
SPI_CLOCK_RATE = 8000000 
 
# NB set the DEBUG flag to True when testing the code inside the Thonny REPL.
# this reduces the sample rate and the amount of data that is output to screen, and
# it prints some diagnostic progress info as the code proceeds
DEBUG = const(False)

# These adc settings can be adjusted via comms from the Pi when in COMMAND mode
DEFAULT_ADC_SETTINGS = { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }

# Buffer memory -- number of samples cached in Pico memory.
# Buffer size is a power of two, to allow divide by two and bit masks to work easily
# The buffer size is measured in 'samples' or number of cells.
# However note the underlying memory size in bytes
# is BUFFER_SIZE * 8 because we have 4 measurement channels and 2 bytes per channel.
BUFFER_SIZE = 128

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
# bit-and the state variable with SAMPLE_MASK to remove the mode bits, to access 
# just the buffer pointer
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


def configure_pins():
    global pins

    # Pico pin setup
    # We initialise with the RESET* and CS* pins high, since they are active low and we don't want
    # them to operate until needed
    pins = {
        'pico_led'    : machine.Pin(25, Pin.OUT),           # the led on the Pico
        'buffer_led'  : machine.Pin(15, Pin.OUT),           # the 'buffer' LED on the PCB
        'cs_adc'      : machine.Pin(1, Pin.OUT, value=1),   # chip select pin of the ADC (active low)
        'sck_adc'     : machine.Pin(2, Pin.OUT),            # serial clock for the SPI interface
        'sdi_adc'     : machine.Pin(3, Pin.OUT),            # serial input to ADC from Pico
        'sdo_adc'     : machine.Pin(0, Pin.IN),             # serial output from ADC to Pico
        'reset_adc'   : machine.Pin(5, Pin.OUT, value=1),   # hardware reset of ADC commanded from Pico (active low)
        'dr_adc'      : machine.Pin(4, Pin.IN),             # data ready from ADC to Pico (active low)
        'reset_me'    : machine.Pin(14, Pin.IN),            # reset and restart Pico (active low)
        'mode_select' : machine.Pin(26, Pin.IN)             # switch between streaming (LOW) and command mode (HIGH)
    }
    

def configure_adc_spi_interface():
    global pins, spi_adc_interface

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
    global pins, spi_adc_interface

    # The actual address byte leads with binary 01 and ends with the read/write bit (1 or 0).
    # The five bits in the middle are the 'register' address inside the ADC
    addr = 0x40 | (reg << 1)

    # Activate the CS* pin to communicate with the ADC
    pins['cs_adc'].value(0)
    # for writing, make sure lowest bit is cleared, hence & 0b11111110
    spi_adc_interface.write(bytes([addr & 0b11111110]) + bs) 
    pins['cs_adc'].value(1)
    if DEBUG:
        pins['cs_adc'].value(0)
        # for reading, make sure lowest bit is set, hence | 0b00000001
        spi_adc_interface.write(bytes([addr | 0b00000001])) 
        obs = spi_adc_interface.read(len(bs))
        pins['cs_adc'].value(1)
        print("Verify: " + " ".join(hex(b) for b in obs))
 

def reset_adc():
    global pins

    # deselect the ADC
    pins['cs_adc'].value(1)
    time.sleep(0.1)
    # cycle the reset pin
    pins['reset_adc'].value(0)
    time.sleep(0.1)
    pins['reset_adc'].value(1)
    time.sleep(0.1)


# gains are in order of hardware channel: differential current, low range current, full range current, voltage
# refer to MCP3912 datasheet for behaviour of all the settings configured here
def setup_adc(adc_settings):
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
    global pins

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

    # Bind pin transitions to interrupt handlers
    # we use hard interrupt for the DR* pin to maintain tight timing
    # and for the RESET* pin so that the reset works even within a blocking function (eg serial write)
    pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)
    pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: set_mode(RESET), hard=True)
    # for mode select, timing is less critical so we use soft interrupts
    pins['mode_select'].irq(trigger = Pin.IRQ_FALLING, handler = lambda _: set_mode(STREAMING), hard=False)
    pins['mode_select'].irq(trigger = Pin.IRQ_RISING, handler = lambda _: set_mode(COMMAND), hard=False)


def disable_interrupts():
    global pins

    pins['dr_adc'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    pins['reset_me'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    pins['mode_select'].irq(trigger = Pin.IRQ_FALLING, handler = None)
    pins['mode_select'].irq(trigger = Pin.IRQ_RISING, handler = None)


def configure_buffer_memory():
    global mv_acq

    # 2 bytes per channel, 4 channels
    # we use a memoryview to allow this to be sub-divided into cells and
    # pages in the streaming loops
    mv_acq = memoryview(bytearray(BUFFER_SIZE * 8))


def start_adc():
    global pins, spi_adc_interface

    if DEBUG:
        print('Starting the ADC...')
    # Command ADC to repeatedly refresh ADC registers, by holding CS* low
    # Pico will successively read the SPI bus each time the DR* pin is activated
    pins['cs_adc'].value(0)
    spi_adc_interface.write(bytes([0b01000001]))


def stop_adc():
    global pins

    # Tell the ADC to stop sampling
    # Note that the DR* pin continues to cycle, so it's necessary to also stop
    # interrupts if we want to stop processing completely
    if DEBUG:
        print('Stopping the ADC...')
    pins['cs_adc'].value(1)


########################################################
######### STREAMING LOOP FOR CORE 1 STARTS HERE
########################################################
def streaming_loop_core_1():
    global state, spi_adc_interface, mv_acq

    # Create a memoryview reference into each sample or slice of the buffer.
    # The SPI read instruction will write into these memory slices directly.
    mv_cells = []
    for i in range(0, BUFFER_SIZE):
        mv_cells.append(memoryview(mv_acq[i*8 : i*8+8]))

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
def streaming_loop_core_0(): 
    global pins, state, mv_acq

    # Create memoryviews of each half of the circular buffer (ie two pages)
    half_mem = BUFFER_SIZE * 8 // 2
    mv_p1 = memoryview(mv_acq[:half_mem])
    mv_p2 = memoryview(mv_acq[half_mem:])

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
    global pins

    # The ISR has detected that the reset pin went low
    # Ensure the reset process is not interrupted
    disable_interrupts()
    stop_adc()
    # Wait for the reset pin to return to inactive (high)
    while pins['reset_me'].value() == 0:
        continue
    time.sleep(0.1)
    # now reset Pico
    machine.reset()


def get_sha256(filename):
    with open(filename, 'rb') as f:
        sha = hashlib.sha256(f.read())
    bs = sha.digest()
    # return as a string containing the hex respresentation
    return binascii.hexlify(bs).decode('utf-8')


def process_command(adc_settings):
    global state, pins

    # adc_settings are assembled into the dictionary structure as below
    #  { 'gains': ['1x', '1x', '1x', '1x'], 'sample_rate': '7.812k' }
    # Pico LED lights while waiting for commands
    pins['pico_led'].on()

    while state & COMMAND:
        command_string = sys.stdin.readline()
        # remove newline and CR and make an array of words
        words = command_string.strip('\n\r').split(' ')
        # remove any empty words (eg caused by duplicate spaces)
        words = [ w for w in words if w != '' ]
        command_status = 'OK'
        if len(words) == 0:
            continue    # do nothing for blank lines, don't handle as an error
        elif len(words) == 1:
            token = words[0]
            if token == 'RESET':
                state = RESET
            elif token == 'MD5':
                print(get_sha256(PROGRAM_FILE_NAME))
            elif token == 'STREAM':
                # change to ADC streaming mode
                # do not output anything -- at this point the receiving process will
                # be expecting to read bytes from the ADC
                state = STREAMING
            else:
                command_status = f'Error: bad token {token}'
        elif len(words) == 2:
            token, value = words
            if token == 'SAMPLERATE':
                adc_settings['sample_rate'] = value
            else:
                command_status = f'Error: bad token {token}'
        elif len(words) == 5:
            token, g3, g2, g1, g0 = words
            if token == 'GAINS':
                adc_settings['gains'] = [g3, g2, g1, g0] 
            else:
                command_status = f'Error: bad token {token}'
        else:
            command_status = f'Error: bad structure {words}'
        print(command_status)

    pins['pico_led'].off()
    return adc_settings


def main():
    global pins, state

    # adc_settings can be changed in COMMAND mode
    adc_settings = DEFAULT_ADC_SETTINGS
    
    # Pause briefly at startup, to ensure IO hardware is initialised
    time.sleep(1)
    if DEBUG:
        print('PICO starting up.')

    if DEBUG:
        print('Configuring pins and SPI interface to ADC.')
    configure_pins()
    configure_adc_spi_interface()

    if DEBUG:
        print('Configuring buffer memory.')
    # buffer memory is set up in a memoryview called mv_acq
    # this has to be a global variable so it can be accessed in both cores
    configure_buffer_memory()

    if DEBUG:
        print('Set command mode and configure interrupts.')
    state = COMMAND
    configure_interrupts()

    if DEBUG:
        print('Entering outer processing loop.')

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
            # start the streaming loops on the two CPU cores, both accessing
            # the same buffer memory
            # core 1 captures samples from the ADC, triggered by the DR* pin
            # core 0 prints blocks of samples from the capture buffer in two pages
            _thread.start_new_thread(streaming_loop_core_1, ())
            streaming_loop_core_0()
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
        gc.enable()
        disable_interrupts()


