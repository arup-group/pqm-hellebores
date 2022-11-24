import math
import time
import machine
import utime
import ustruct
import sys
import gc
from machine import Pin


# pin and SPI setup
led = machine.Pin(25, Pin.OUT)
boardled = machine.Pin(15, Pin.OUT)
cs_adc = machine.Pin(1, Pin.OUT)
#sck_adc = machine.Pin(2, Pin.OUT)
#sdo_adc = machine.Pin(0, Pin.IN)
#sdi_adc = machine.Pin(3, Pin.OUT)
reset_adc = machine.Pin(5, Pin.OUT)
dr_adc = machine.Pin(4, Pin.IN)


spi_adc = machine.SPI(0,
                  baudrate = 4000000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = machine.Pin(2),
                  mosi = machine.Pin(3),
                  miso = machine.Pin(0))


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



# convert two's complement 24 bit binary to signed integer
def binary_to_signed_int(bs):
    v = int.from_bytes(bs, 'big')
    if bs[0] & (1<<7):    # negative number if most significant bit is set
        # adjust for negative number
        v = v - (1 << len(bs)*8)
    return v

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
    print("Setting gain register 0x0b to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0b, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    # Set the status and communication register 0x0c
    print("Setting status and communication register STATUSCOM at 0x0c to 0x88, 0x00, 0x0f.")
    set_and_verify_adc_register(spi, cs, 0x0c, bytes([0x88,0x00,0x0f]))
    time.sleep(1)

    # Set the configuration register CONFIG0 at 0x0d
    print("Setting configuration register CONFIG0 at 0x0d to 0x24, 0x40, 0x50.")
    # 1st byte sets various ADC modes
    # 2nd byte sets OSR, for sampling speed: 0x20 = 15.625kSa/s, 0x40 = 7.8125kSa/s, 0x60 = 3.90625kSa/s
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    set_and_verify_adc_register(spi, cs, 0x0d, bytes([0x24,0x40,0x50]))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    print("Setting configuration register CONFIG1 at 0x0e to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0e, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    
def read_all_adcs(spi, cs, dr):
    cs.value(0)
    spi.write(bytes([0b01000001]))
    acq = spi.read(8)   # bring back all readings (8 bytes)
    cs.value(1)
    return acq


def value_gauge(v, low, high):
    # scale readings over 50 characters
    out = '|'
    v_pos = round((v - low)/(high - low) * 50)
    for i in range(0, v_pos):
        out = out + '-'
    out = out + '>'
    for i in range(v_pos+1, 51):
        out = out + ' '
    out = out + '|'
    return out

def convert_to_channels(acq):
    raw = [0,0,0,0]
    signed_int = [0,0,0,0]
    # split up and process the readings
    for i in range(0,4):
        ch = acq[i*2 : i*2+2]
        raw[i] = int.from_bytes(ch, 'big')
        signed_int[i] = binary_to_signed_int(ch)
    return (raw, signed_int)           


acq = False
reads = 0
read_enable = False

# interrupt handler for data ready pin
def dr_handler(dr_adc):
    global acq, reads
    acq = spi_adc.read(8)
    reads = reads + 1
    

def main():
    # waiting in case of lock up, opportunity to cancel
    print('PICO starting up.')
    time.sleep(1)
    print('Waiting for 10 seconds...')
    time.sleep(10)
    print('Now continuing with setup.')
    
    # configure the ADC
    setup_adc(spi_adc, cs_adc, reset_adc)

    #  disable automatic garbage collection to improve performance
    gc.disable()
    
    # bind the handler to a falling edge transition on the DR pin
    dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = dr_handler)

    # initialise global vars
    global acq, reads, read_enable
    reads = 0
    read_enable = True
    
    # command ADC to repeatedly read ADC registers, by holding CS* low
    # subsequent spi read commands will read the same registers again
    cs_adc.value(0)
    spi_adc.write(bytes([0b01000001]))
    acq = spi_adc.read(8)   # first reading

    while True:
        # indicate and print every 4096 readings
        # otherwise do nothing
        if reads % 4096 == 0:
            # disable interrupts
            # while processing here, esp. garbage collector which takes a
            # long time
            dr_adc.irq(handler = None)

            read_enable = False
            # convert to signed integers
            boardled.toggle()
            r, s = convert_to_channels(acq)
            # print state of selected channel to console
            ch = 3
            print(f'CH{ch} ' + value_gauge(s[ch], -32768, 32767) + f' {r[ch]:04x} {s[ch]:5d}', end='\r')
            gc.collect()  # manual collection
            # re-enable interrupts
            dr_adc.irq(trigger = Pin.IRQ_FALLING, handler = dr_handler)

# run from here
if __name__ == '__main__':
    main()


