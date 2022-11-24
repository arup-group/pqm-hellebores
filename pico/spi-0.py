import math
import time
import machine
import utime
import ustruct
import sys
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


spi = machine.SPI(0,
                  baudrate = 100000,
                  polarity = 0,
                  phase = 0,
                  bits = 8,
                  firstbit = machine.SPI.MSB,
                  sck = machine.Pin(2),
                  mosi = machine.Pin(3),
                  miso = machine.Pin(0))

def write_text(spi, cs, text):
    message = bytearray()
    for c in text:
        message.append(ord(c))
    # send the message on the bus    
    cs.value(0)
    spi.write(message)
    cs.value(1)
    
def write_bytes(spi, cs, data):
    # send the message on the bus    
    cs.value(0)
    spi.write(data)
    cs.value(1)
        
def write_and_read_bytes(spi, cs, data, nbytes):
    cs.value(0)
    spi.write(data)
    result = spi.read(nbytes)
    cs.value(1)
    return result

def read_adc(cs, ch):
    cs.value(0)
    if ch == 0:
        spi.write(bytes([0b01000001]))
    elif ch == 1:
        spi.write(bytes([0b01000011]))
    elif ch == 2:
        spi.write(bytes([0b01000101]))
    elif ch == 3:
        spi.write(bytes([0b01000111]))

    result = spi.read(3)
    cs.value(1)
    return result


# deselect the adc
cs_adc.value(1)

# reset the adc
reset_adc.value(0)
time.sleep(0.1)
reset_adc.value(1)
time.sleep(0.1)


# Setup the MC3912 ADC
# Set the gain configuration register 0x0b
print("Setting gain register 0x0b to 0x00.")
write_bytes(spi, cs_adc, bytes([0b01010110,0b0]))
bs = write_and_read_bytes(spi, cs_adc, bytes([0b01010111]), 3)
print("Verify: " + " ".join(hex(b) for b in bs))
time.sleep(2)
                        
# Set the status and communication register 0x0c
print("Setting status and communication register 0x0c to 0x89, 0x00, 0x0f.")
write_bytes(spi, cs_adc, bytes([0b01011000,0b10001001,0b00000000,0b00001111]))
bs = write_and_read_bytes(spi, cs_adc, bytes([0b01011001]), 3)
print("Verify: " + " ".join(hex(b) for b in bs))
time.sleep(2)

# Set the configuration register CONFIG0 at 0x0d
print("Setting configuration register CONFIG0 at 0x0d to 0x5a, 0x38, 0x50.")
write_bytes(spi, cs_adc, bytes([0b01011010,0b00111000,0b00100000,0x50]))
bs = write_and_read_bytes(spi, cs_adc, bytes([0b01011011]), 3)
print("Verify: " + " ".join(hex(b) for b in bs))
time.sleep(2)

# Set the configuration register CONFIG1 at 0x0e
print("Setting configuration register CONFIG0 at 0x0e to 0x00, 0x00, 0x00.")
write_bytes(spi, cs_adc, bytes([0b01011100,0b00000000,0b00000000,0b00000000]))
bs = write_and_read_bytes(spi, cs_adc, bytes([0b01011101]), 3)
print("Verify: " + " ".join(hex(b) for b in bs))
time.sleep(2)



# Attempt to read from ADCs
i = 0
while True:
    boardled.toggle()
    ch0 = read_adc(cs_adc, 0)
    ch1 = read_adc(cs_adc, 1)
    ch2 = read_adc(cs_adc, 2)
    ch3 = read_adc(cs_adc, 3)
    print("Readings: " + str(ch0) + "  " + str(ch1) + "  " + str(ch2) + "  " + str(ch3))
#    print(f"Readings: {ch0:6} {ch1:6} {ch2:6} {ch3:6}")
    time.sleep(0.05)
    i = i+1
    
