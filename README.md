# pqm-hellebores
Power quality measurement (IiA 20139)

Invest-in-Arup research project to design and make a convenient way to measure and study the power quality and energy performance of single phase small power and lighting devices, that connect via plug-and-socket.

See IiA page for more project details [https://invest.arup.com/?layout=projsheet&projid=20139](https://invest.arup.com/?layout=projsheet&projid=20139)

## System requirements
The software is designed to run on Raspberry Pi and Raspberry Pi Pico microcontroller, communicating with an analog-to-digital converter (ADC: MCP3912) on a custom PCB to source measurements of power parameters: voltage, current (low sensivity), current (high sensitivity) and earth leakage current. Following conversion and scaling to floating point measurement values, the measurement samples are further processed to provide a variety of performance measurements, waveform visualisation and logging. A local display and touch screen provide user interface.

**Raspberry Pi**  
Minimum hardware requirement is Raspberry Pi 3B+. Non-plus models do not have sufficent thermal dissipation for high CPU loads. Touch screen display with DSI interface, 800x480 pixels. Raspberry Pi OS (32 bit) with desktop. Prepare the image with connectivity to local/required wifi, SSH access, and change the default password. If you have one, pair a Bluetooth keyboard for local access.

**Raspberry Pi Pico**  
Use Thonny on your desktop or laptop computer to install MicroPython and verify that you have local REPL access to the microcontroller via USB.

## Installation
**Raspberry PI SD card**
Prepare the SD card using Raspberry Pi Imager.
Enable the option for remote SSH access.
Set the wifi SSID and password to be used for initial access.
Copy the files from ./pi-setup to the boot partition of the SD card.
Edit the firstrun.sh script in the boot partition to copy the files as follows:
This will enable the pi to report it's IP address for remote access on
first boot. Insert the lines just before the command to delete the script at the end.

if [ -f /boot/autorun.sh ]; then
  cp /boot/autorun.sh /home/pi
fi
if [ -f /boot/find-me.desktop ]; then
  cp /boot/find-me.desktop /home/pi/.config/autostart
fi

rm -f /boot/firstrun.sh  ####### NB JUST ABOVE THIS EXISTING LINE ######


**Pico**  
Using Thonny, open `./pico/main.py` and save it to the root folder of the microcontroller.

**Pi**  
Start a terminal session via SSH or use a local keyboard.  

Clone the repository:  
`git clone https://github.com/arup-group/pqm-hellebores.git`

Change to the working directory:  
`cd pqm-hellebores`

Create a virtual environment, and activate it
`python -m venv create venv`
`source venv/bin/activate`

Install the dependencies  
`python -m pip install -r requirements.txt`

See notes file for additional system dependencies

Set up the desktop shortcuts  
cp /boot/find-me.desktop /home/pi/.local/share/applications
cp /boot/hellebores.desktop /home/pi/.local/share/applications

## Running
To use the interactive user interface, run "hellebores" from the Raspberry Pi desktop menu.

## Development
For performance and simplicity reasons, the software is designed as modular, independent programs that are connected in a pipeline with data sent as a text stream. Control settings are stored in a 'settings.json' file: the GUI sends programs a 'signal' whenever the settings file is updated, and this causes them to re-load the settings.

The Pi code will run in WSL, Ubuntu, Mac or similar environments that have a modern python and can support the python dependencies, pipelines and signals. hellebores.py requires SDL. The GUI can run under X-Windows or in native Mac and MS-Windows if the SDL libraries are installed and are reachable from the python runtime environment. The run script will detect whether a serial interface to Pico is available and if not will use simulated (pre-recorded) data for the purpose of testing.

On a Posix system (Raspberry Pi OS, WSL, Ubuntu, Mac etc) execute `run/go.sh` from the terminal to run the full pipeline. This will access live measurements on real PQM hardware, and simulated measurements on other computers.

For Windows computers without WSL, use `run\go.bat` or, from the 'run' directory, `python go.py` from a cmd.exe shell. This implements the waveform and calculation pipelines by setting them up as python sub-processes.


