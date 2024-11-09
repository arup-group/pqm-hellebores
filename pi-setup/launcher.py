#!/usr/bin/env python3

import sys
import os
import subprocess
import tkinter as tk


if not os.geteuid() == 0:
    sys.exit("\nOnly root can run this script.\n")

### wifi connection functions

# onboard -l Small -t Droid
# matchbox-keyboard lq1

# connect to wifi using wpa_cli
# wpa_cli add_network
# 0
# wpa_cli set_network 0 ssid "peppa"
# OK
# wpa_cli set_network 0 psk "asdfasdfasdf"
# OK
# wpa_cli enable_network 0
# OK
# wpa_cli reconnect
# OK


def what_wifi():
    process = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'], stdout=subprocess.PIPE)
    if process.returncode == 0:
        return process.stdout.decode('utf-8').strip().split(':')[1]
    else:
        return ''

def is_connected_to(ssid: str):
    return what_wifi() == ssid

def scan_wifi():
    process = subprocess.run(['nmcli', '-t', '-f', 'SSID,SECURITY,SIGNAL', 'dev', 'wifi'], stdout=subprocess.PIPE)
    if process.returncode == 0:
        return process.stdout.decode('utf-8').strip().split('\n')
    else:
        return []
        
def is_wifi_available(ssid: str):
    return ssid in [x.split(':')[0] for x in scan_wifi()]

def connect_to(ssid: str, password: str):
    if not is_wifi_available(ssid):
        return False
    subprocess.call(['nmcli', 'd', 'wifi', 'connect', ssid, 'password', password])
    return is_connected_to(ssid)

def connect_to_saved(ssid: str):
    if not is_wifi_available(ssid):
        return False
    subprocess.call(['nmcli', 'c', 'up', ssid])
    return is_connected_to(ssid)


### User interface

root = tk.Tk()
root.title('Power quality monitor launcher')

ssid_available = tk.StringVar()
ssid_available.set('Available SSID: waiting for scan')
string_entered = tk.StringVar()

def print_result(string_variable):
    print(string_variable.get())

# frame for the buttons
button_frame = tk.Frame(root, width=400, height=100)
button_frame.grid(row=3, column=0)

# text field to display available wifi SSID
ssid_scan = tk.Label(root, width=50, textvariable=ssid_available, font=('System', 12))
ssid_scan.grid(row=1, column=0)

# password field is an editable Text object
password_field = tk.Entry(root, width=50, textvariable=string_entered, font=('System', 14))
password_field.grid(row=2, column=0)


# make a grid of buttons
button_characters = [ "()[]{}<>",
                      "0123456789",
                      "@&¬`'\"%^~!$£#",
                      "*/+-=_.,\\|?:;",
                      "abcdefghijklm",
                      "nopqrstuvwxyz",
                      "ABCDEFGHIJKLM",
                      "NOPQRSTUVWXYZ" ]

# create the 'keyboard'
r = 2
for line in button_characters:
    c = 0
    for character in line:
        b = tk.Button(button_frame, width=2, font=('System',14), text=character, \
                 command=lambda character=character: password_field.insert(tk.END, character))
        b.grid(row=r, column=c)
        c += 1
    r += 1

# special buttons
delete_button = tk.Button(button_frame, width=2, font=('System', 14), text='<BS', \
        command=lambda: string_entered.set(string_entered.get()[:-1]))
delete_button.grid(row=3, column=11)
enter_button = tk.Button(button_frame, width=2, font=('System', 14), text='RTN', \
        command=lambda: print_result(string_entered) and sys.exit(0))
enter_button.grid(row=3, column=12)
space_button = tk.Button(button_frame, width=2, font=('System', 14), text='SP', \
        command=lambda: password_field.insert(tk.END, ' '))
space_button.grid(row=3, column=10)

# display available wifi SSID
#ssid_available.set(scan_wifi())
#print(ssid_available.get())

# process events
root.mainloop()





