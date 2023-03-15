import time
import machine
import gc
import binascii
from machine import Pin
import _thread
import sys

DEBUG_MODE = False

# Buffer memory
# Advantage if this is a power of two, to allow divide by two and bit masks to work easily
BUFFER_SIZE = 256                          # number of samples in a buffer
BUFFER_BIT_MASK = BUFFER_SIZE * 8 - 1      # bit mask to circulate the buffer pointer
END_POINTER     = BUFFER_SIZE * 8          # pointer value to end of buffer
HALFWAY_POINTER = END_POINTER // 2         # beginning of 2nd half


# pin setup
pico_led     = machine.Pin(25, Pin.OUT)    # the led on the Pico
board_led    = machine.Pin(15, Pin.OUT)    # the 'buffer' LED on the PCB
cs_adc       = machine.Pin(1, Pin.OUT)     # chip select pin of the ADC
sck_adc      = machine.Pin(2, Pin.OUT)     # serial clock for the SPI interface
sdi_adc      = machine.Pin(3, Pin.OUT)     # serial input to ADC from Pico
sdo_adc      = machine.Pin(0, Pin.IN)      # serial output from ADC to Pico
reset_adc    = machine.Pin(5, Pin.OUT)     # hardware reset of ADC commanded from Pico (active low)
dr_adc       = machine.Pin(4, Pin.IN)      # data ready from ADC to Pico (active low)
reset_me     = machine.Pin(14, Pin.IN)     # hardware reset of Pico (active low, implemented with interrupt handler)

# SPI setup
spi_adc = machine.SPI(0,
                  baudrate   = 6000000,
                  polarity   = 0,
                  phase      = 0,
                  bits       = 8,
                  firstbit   = machine.SPI.MSB,
                  sck        = sck_adc,
                  mosi       = sdi_adc,
                  miso       = sdo_adc)


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
    cs.value(1)
    
    # reset the adc
    reset.value(0)
    time.sleep(0.1)
    reset.value(1)
    time.sleep(0.1)
    # Set the gain configuration register 0x0b
    # 3 bits per channel (12 LSB in all)
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
    SSP = { '244':0xe0, '488':0xc0, '976':0xa0, '1.953k':0x80, '3.906k':0x60, '7.812k':0x40, '15.625k':0x20, '31.250k':0x00 }
    bs = [0x24, SSP['7.812k'], 0x50]
    if DEBUG_MODE == True:
        bs[1] = SSP['976']    # slow down sampling for debug mode
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
def pico_restart_handler(reset_me):
    machine.reset()
    

# NB print_responder() runs on Core 1
def print_responder():
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
    
    ########################################################
    ######### MAIN LOOP FOR CORE 1 STARTS HERE
    ########################################################
    while running == True:
        while (running == True) and (print_request != 1):
            continue
        # we received a request to print 'page 1'
        p_buf[:] = acquire_buffer[0:HALFWAY_POINTER]
        print_it()
        while (running == True) and (print_request != 2):
            continue
        # we received a request to print 'page 2'
        p_buf[:] = acquire_buffer[HALFWAY_POINTER:END_POINTER]
        print_it()
                
    print('print_responder() exited on Core 1')


def main():
    global acquire_buffer, running, print_request, in_ptr

    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    print('Initialising ADC...')
    setup_adc(spi_adc, cs_adc, reset_adc)
    time.sleep(1)

    print('Setting up RESET interrupt...')
    # configure the interrupt handlers
    # bind the reset handler to a falling edge transition on the RESET ME pin
    reset_me.irq(trigger = Pin.IRQ_FALLING, handler = pico_restart_handler, hard=True)
    time.sleep(1)
    
    # initial values for global variables shared with second core
    # and interrupt service routine
    running = True              # flag for running each core
    acquire_buffer = bytearray(BUFFER_SIZE * 8)   # 2 bytes per channel, 4 channels
    in_ptr = 0                  # buffer cell pointer (for DR* interrupt service routine)
    print_request = 0           # flag to indicate that printing is required

    # the print process runs on Core 1
    print('Starting the print_responder() process on Core 1...')
    _thread.start_new_thread(print_responder, ())
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

 
    ########################################################
    ######### MAIN LOOP FOR CORE 0 STARTS HERE
    ########################################################
    print('Entering main loop...')
    gc.collect()
    ptr = 0
    spi_buffer = bytearray(8)   # temporary buffer for reading one sample via SPI
    while running == True:
        # this loop waits for the ISR to change the pointer value
        while in_ptr == ptr:
            continue

        # now immediately read the new data from ADC
        spi_adc.readinto(spi_buffer)
        # the pointer is volatile, so capture its value
        ptr = in_ptr

        # store the new data in the buffer
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
        running = False
        cs_adc.value(1)
        gc.enable()



