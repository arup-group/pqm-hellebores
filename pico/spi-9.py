import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys

DEBUG_MODE = False

# Buffer memory
# Advantage if this is a power of two, so that the buffer pointer can 'flip' its MSB
# to indicate to the print function which 'half' of the buffer is safe to print
BUFFER_SIZE = 256                            # number of samples in a buffer
BUFFER_BIT_MASK = BUFFER_SIZE * 8 - 1        # bit mask to circulate the buffer pointer
END_POINTER     = BUFFER_SIZE * 8
HALFWAY_POINTER = END_POINTER // 2           # beginning of 2nd half


# pin and SPI setup
pico_led     = machine.Pin(25, Pin.OUT)    # this is the led on the Pico
board_led    = machine.Pin(15, Pin.OUT)    # this is the 'buffer' LED on the PCB
cs_adc       = machine.Pin(1, Pin.OUT)
sck_adc      = machine.Pin(2, Pin.OUT)
sdi_adc      = machine.Pin(3, Pin.OUT)
sdo_adc      = machine.Pin(0, Pin.IN)
reset_adc    = machine.Pin(5, Pin.OUT)
dr_adc       = machine.Pin(4, Pin.IN)
reset_me     = machine.Pin(14, Pin.IN)


spi_adc = machine.SPI(0,
                  baudrate = 6000000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = sck_adc,
                  mosi = sdi_adc,
                  miso = sdo_adc)


def write_bytes(spi, cs, addr, bs):
    cs.value(0)
    spi.write(bytes([addr & 0b11111110]) + bs) # for writing, make sure lowest bit is cleared
    cs.value(1)
        
def read_bytes(spi, cs, addr, n):
    cs.value(0)
    spi.write(bytes([addr | 0b00000001])) # for reading, make sure lowest bit is set
    obs = spi.read(n)
    cs.value(1)
    return obs


def set_and_verify_adc_register(spi, cs, reg, bs):
    # The actual address byte leads with binary 01 and ends with the read/write bit (1 or 0).
    # The five bits in the middle are the 'register' address
    addr = 0x40 | (reg << 1)
    write_bytes(spi, cs, addr, bs)
    obs = read_bytes(spi, cs, addr, len(bs))
    print("Verify: " + " ".join(hex(b) for b in obs))
    

def setup_adc(spi, cs, reset):
    # Setup the MC3912 ADC
    # deselect the ADC
    cs_adc.value(1)
    
    # reset the adc
    reset_adc.value(0)
    time.sleep(0.1)
    reset_adc.value(1)
    time.sleep(0.1)
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
    # binary codes:
    # 101=32x
    # 100=16x
    # 011=8x
    # 010=4x
    # 001=2x
    # 000=1x
    # XXXXXXXX XXXX---- --------
    # channel ->   3332 22111000
    G = { '32x':0b101, '16x':0b100, '8x':0b011, '4x':0b010, '2x':0b001, '1x':0b000 } 
    g0 = G['32x']    # differential current
    g1 = G['2x']     # current 1
    g2 = G['2x']     # current 2
    g3 = G['1x']     # voltage
    gains = (g0 << 9) + (g1 << 6) + (g2 << 3) + g3 
    bs = [0x00, gains >> 8, gains & 0b11111111]
    print('Setting gain register at 0b to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0b, bytes(bs))
    time.sleep(1)
    
    # Set the status and communication register 0x0c
    bs = [0x88, 0x00, 0x0f]
    print('Setting status and communication register STATUSCOM at 0c to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0c, bytes(bs))
    time.sleep(1)

    # Set the configuration register CONFIG0 at 0x0d
    # 1st byte sets various ADC modes
    # 2nd byte sets OSR, for sampling speed, OSR speeds as follows:
    # 0x00 = 32:  31.25 kSa/s
    # 0x20 = 64:  15.625 kSa/s
    # 0x40 = 128:  7.8125 kSa/s
    # 0x60 = 256:  3.90625 kSa/s
    # 0x80 = 512:  1.953 kSa/s
    # 0xa0 = 1024:   976 Sa/s
    # 0xc0 = 2048:   488 Sa/s
    # 0xe0 = 4096:   244 Sa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    bs = [0x24, 0x40, 0x50]
    if DEBUG_MODE == True:
        bs[1] = 0xa0    # slow down sampling for debug mode
    print('Setting configuration register CONFIG0 at 0d to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0d, bytes(bs))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    bs = [0x00, 0x00, 0x00]
    print('Setting configuration register CONFIG1 at 0e to 0x{:02x} 0x{:02x} 0x{:02x}'.format(*bs))
    set_and_verify_adc_register(spi, cs, 0x0e, bytes(bs))
    time.sleep(1)
    
    
# interrupt handler for data ready pin
def adc_read_handler(dr_adc):
    global in_ptr
    # 'anding' the pointer with a bit mask that has binary '1' in the LSBs
    # makes the buffer pointer return to zero without needing an 'if' conditional
    # this means it executes in constant time
    in_ptr = (in_ptr + 8) & BUFFER_BIT_MASK    # BUFFER_BIT_MASK = BUFFER_SIZE * 8 - 1
 
        
# interrupt handler for reset pin (this pin is commanded from Pi GPIO)    
def pico_restart(reset_me):
    machine.reset()
    
    
def initialise():
    # configure the ADC
    setup_adc(spi_adc, cs_adc, reset_adc)


# print is an I/O operation and unfortunately can block (terminal not ready etc)
# therefore we ensure that *ALL* shared memory access takes place inside the lock
# and Core 0 is not allowed to use it until we're finished.

# Runs on Core 1
def print_responder():
    # print('Core 1 print_responder() starting, hello...')
    p_buf = bytearray(BUFFER_SIZE * 8 // 2)
    
    def print_it():
        board_led.on()
        if DEBUG_MODE == True:
            # write out the selected portion of buffer as hexadecimal text
            sys.stdout.write(binascii.hexlify(p_buf)[:32])
            sys.stdout.write('\n')
        else:
            # write out the selected portion of buffer as bytes
            sys.stdout.buffer.write(p_buf)
        board_led.off()
     
    while running1 == True:
        while (running1 == True) and (print_request != 1):
            continue
        p_buf[:] = acquire_buffer[0:HALFWAY_POINTER]
        print_it()
        while (running1 == True) and (print_request != 2):
            continue
        p_buf[:] = acquire_buffer[HALFWAY_POINTER:END_POINTER]
        print_it()
                
    print('print_responder() exited on Core 1')


def main():
    global acquire_buffer, running0, running1, print_request, in_ptr

    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    print('Initialising ADC...')
    initialise()
    time.sleep(1)

    print('Setting up RESET interrupt...')
    # configure the interrupt handlers
    # bind the reset handler to a falling edge transition on the RESET ME pin
    reset_me.irq(trigger = Pin.IRQ_FALLING, handler = pico_restart, hard=True)
    time.sleep(1)
    
    running0 = True             # flags for running each core
    running1 = True
    spi_buffer = bytearray(8)   # temporary buffer for reading one sample via SPI
    acquire_buffer = bytearray(BUFFER_SIZE * 8)   # 2 bytes per channel, 4 channels
    in_ptr = 0                  # buffer cell pointer (for DR* interrupt service routine)
    ptr = 0
    print_request = 0           # flag to indicate that printing is required

    # create a lock around access to the 'print_request' variable
    #lk = _thread.allocate_lock()
    # the print process runs on Core 1
    print('Starting the print process on Core 1...')
    _thread.start_new_thread(print_responder, ())  # Start Core 1 (printing)
    time.sleep(1)        # give it some time to initialise
    
    # disable garbage collector
    # heap memory can't be recovered below here
    # so we must avoid functions that repeatedly allocate memory
    # eg we use hexlify in DEBUG_MODE.
    #if DEBUG_MODE == False:
    #    gc.disable()

    print('Setting up the ADC (DR*) interrupt...')
    # bind the sampler handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = adc_read_handler, hard=True)

    # now command ADC to repeatedly refresh ADC registers, by holding CS* low
    # pico will successively read these registers
    # each time the DR* pin is activated
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))

    print('Entering main loop...')
    gc.collect()
    while running0 == True:
        # this loop waits for the ISR to change the pointer value
        while in_ptr == ptr:
            continue
        # now immediately read the new data from ADC
        spi_adc.readinto(spi_buffer)
        # the pointer is volatile, so capture its value
        ptr = in_ptr
        # store the data in the buffer
        acquire_buffer[ptr : ptr+8] = spi_buffer
        # see if we have reached a 'page boundary' in the buffer
        # if so, instruct Core 1 CPU to print it
        if ptr == HALFWAY_POINTER:
            print_request = 1
        elif ptr == 0:
            print_request = 2
            #gc.collect()
            
    # finish sampling
    cs_adc.value(1)
    print('Core 0 exited.')
    
# run from here
if __name__ == '__main__':
    try:
        main()
    except:
        print('Interrupted -- re-enabling auto garbage collector.')
        running0 = False
        running1 = False
        cs_adc.value(1)
        gc.enable()


#
# To prevent deadlock, if Core 0 has instructed a print
# it *must* release and not re-acquire a lock until the print is cleared
# Similarly if Core 1 has cleared a print, it *must* release and not
# re-acquire a lock until a new print is instructed.
# Additional timing safeguards:
# The I/O print operation in Core 1 doesn't have a guaranteed completion time,
# it can block and so the data must be copied out of the main buffer first
# to prevent a memory fault.
# Timing chart
# Core 0                  Core 1
# filling z1              -
# ACQUIRE                 -
# print req clear?        -
# zone transit?           -
# -> req print z1         -                               (print_request = 1)
# RELEASE                 -
# filling z2              ACQUIRE
# -                       req print?
# -                       -> copy z1 to local
# -                       <- clear print req              (print_request = -1)
# -                       print local
# -                       RELEASE
# ACQUIRE                 -
# print req clear?        -
# zone transit?           -
# -> req print z2         -                               (print_request = 2)
# RELEASE                 -
# filling z1              ACQUIRE
# -                       req print?
# -                       -> copy z2 to local
# -                       <- clear print req              (print_request = -2)              
# -                       print local
# -                       RELEASE
# ACQUIRE                 -
# print req clear?        -
# zone transit?           -
# -> req print z1         -
# RELEASE                 -
# filling z2              ACQUIRE
# -                       req print?
# -                       -> copy z1 to local
# -                       <- clear print req
# -                       print local
# -                       RELEASE
# ...
