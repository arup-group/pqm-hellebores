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
    print("Setting status and communication register 0x0c to 0xa9, 0x00, 0x0f.")
    set_and_verify_adc_register(spi, cs, 0x0c, bytes([0xa9,0x00,0x0f]))
    time.sleep(1)

    # Set the configuration register CONFIG0 at 0x0d
    print("Setting configuration register CONFIG0 at 0x0d to 0x24, 0x60, 0x50.")
    # 1st byte sets various ADC modes
    # 2nd byte sets OSR, for sampling speed
    # 3rd byte sets temperature coefficient (leave as default 0x50)
    set_and_verify_adc_register(spi, cs, 0x0d, bytes([0x24,0xc0,0x50]))
    time.sleep(1)

    # Set the configuration register CONFIG1 at 0x0e
    print("Setting configuration register CONFIG1 at 0x0e to 0x00, 0x00, 0x00.")
    set_and_verify_adc_register(spi, cs, 0x0e, bytes([0x00,0x00,0x00]))
    time.sleep(1)
    
    
def read_all_adcs(spi, cs, dr):
    cs.value(0)
    spi.write(bytes([0b01000001]))
    acq = spi.read(12)   # bring back all readings (12 bytes)
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
        ch = acq[i*3:i*3+3]
        raw[i] = int.from_bytes(ch, 'big')
        # lowest 4 bits of raw values are zero padded, remove them for decimal presentation
        signed_int[i] = binary_to_signed_int(ch) >> 4
    return (raw, signed_int)           


acq = False
reads = 0
read_enable = False

# interrupt handler for data ready pin
def dr_handler(dr_adc):
    global acq, reads, read_enable
    if read_enable == True:
        acq = read_all_adcs(spi_adc, cs_adc, dr_adc)
    reads = reads + 1
    

def main():
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
    acq = read_all_adcs(spi_adc, cs_adc, dr_adc)

    while True:
        # indicate and print every 100 readings
        # otherwise do nothing
        if reads % 100 == 0:
            # tell the interrupt handler not to continue to read ADCs
            # while processing here, esp. garbage collector which takes a
            # long time
            read_enable = False
            # convert to signed integers
            boardled.toggle()
            r, s = convert_to_channels(acq)
            #print(f"Readings HEX:   {r[0]:06x}   {r[1]:06x}   {r[2]:06x}   {r[3]:06x}")
            #for j in range(0,4):
            #    print(f'CH{j} ' + value_gauge(s[j], -524288, 524287) + f' {s[j]:8d}')
            # print state of selected channel to console
            ch = 3
            print(f'CH{ch} ' + value_gauge(s[3], -524288, 524287) + f' {r[3]:06x} {s[3]:8d}', end='\r')
            gc.collect()  # manual collection
            read_enable = True
            
# run from here
if __name__ == '__main__':
    main()


