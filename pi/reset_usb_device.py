#!/usr/bin/env python2
##--------------------
##--- Author: Pradeep Singh
##--- Blog: https://iotbytes.wordpress.com/
##--- Date: 1st Dec 2017
##--- Version: 1.0
##--- Python Ver: 2.7
##--- Description: This python code will reset a USB port connected to Raspberry Pi
##--------------------


import subprocess
import os
import fcntl


# Define "USB_DEV_NAME" variable based on the Device/Manufacturer name as shown
# in the output of the "lsusb" command on the linux shell
#
# For Example - 
#
# I am using U.S. Robotics Analog USB Modem and want to reset it
# as shown in the following output my Modem is listed as "U.S. Robotics"
# hence I will use "U.S. Robotics" in the USB_DEV_NAME variable -
#
# pi@RaPi3:~ $ lsusb
# Bus 001 Device 004: ID 0baf:0303 U.S. Robotics  <<<<<=========
# Bus 001 Device 003: ID 0424:ec00 Standard Microsystems Corp. SMSC9512/9514 Fast Ethernet Adapter
# Bus 001 Device 002: ID 0424:9514 Standard Microsystems Corp. 
# Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
# pi@RaPi3:~ $ 

# Pico board identifies with this string when using lsusb
USB_DEV_NAME = 'MicroPython Board'

#=================================================================
# Reset Modem
#=================================================================
def reset_USB_Device():

	# Same as _IO('U', 20) constant in the linux kernel.
	CONST_USB_DEV_FS_RESET_CODE = ord('U') << (4*2) | 20
	usb_dev_path = ""

	# Based on 'lsusb' command, get the usb device path in the following format - 
	# /dev/bus/usb/<busnum>/<devnum>
	proc = subprocess.Popen(['lsusb'], stdout=subprocess.PIPE)
	cmd_output = proc.communicate()[0]
	usb_device_list = cmd_output.split('\n')
	for device in usb_device_list:
		if USB_DEV_NAME in device:
			print device
			usb_dev_details = device.split()
			usb_bus = usb_dev_details[1]
			usb_dev = usb_dev_details[3][:3]
			usb_dev_path = '/dev/bus/usb/%s/%s' % (usb_bus, usb_dev)

	try:
		if usb_dev_path != "":
			print "Trying to reset USB Device: " + usb_dev_path
			device_file = os.open(usb_dev_path, os.O_WRONLY)
			fcntl.ioctl(device_file, CONST_USB_DEV_FS_RESET_CODE, 0)
			print "USB Device reset successful."
		else:
			print "Device not found."
	except:
		print "Failed to reset the USB Device."
	finally:
		try:
			os.close(device_file)
		except:
			pass

#=================================================================


reset_USB_Device()



