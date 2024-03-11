# pqm-hellebores
Power quality measurement (IiA 20139)

Invest-in-Arup research project to design and make a convenient way to measure and study the power quality and energy performance of single phase small power and lighting devices, that connect via plug-and-socket.

See IiA page for more project details [https://invest.arup.com/?layout=projsheet&projid=20139](https://invest.arup.com/?layout=projsheet&projid=20139)

## System requirements
The software is designed to run on Raspberry Pi and Raspberry Pi Pico microcontroller, communicating with an analog-to-digital converter (ADC: MCP3912) on a custom PCB to source measurements of power parameters: voltage, current (full range), current (low range) and earth leakage current. Following conversion and scaling to floating point measurement values, the physical measurement samples are further processed to provide a variety of derivative measurements, waveform visualisation and logging. A local touch screen provides user interface.

**Raspberry Pi**  
Minimum hardware requirement is Raspberry Pi 3B+. Non-plus models do not have sufficent thermal dissipation for high CPU loads. Touch screen display with DSI interface, 800x480 pixels. Raspberry Pi OS (32 bit) with desktop. Prepare the image with connectivity to local/required wifi, SSH access, and change the default password. If you have one, pair a Bluetooth keyboard for local access.

**Raspberry Pi Pico**  
Use Thonny on your desktop or laptop computer to install MicroPython on the Pico and verify that you have local REPL access to the microcontroller via a USB cable.

## Installation
**Raspberry PI SD card**
Prepare the SD card using Raspberry Pi Imager. As a convenience, a USB stick with Raspberry Pi OS can be prepared first, plugged in the Pi and then that image booted to write to an in-situ SD card -- avoids the need to remove ribbon cable. If using this method, note that an non-initialised Pico must be unplugged from the Pi USB port for this to work.
Set a project specific password.
Enable the option for remote SSH access.
Set the wifi country, SSID and password to be used for initial access.

**Pi setup**  
Start a terminal session via SSH or use a bluetooth keyboard.  

Clone the repository:  
`git clone https://github.com/arup-group/pqm-hellebores.git`

Change to the working directory:  
`cd pqm-hellebores`

Create a virtual environment, and activate it:
`python -m venv create venv
source venv/bin/activate`

Install the dependencies  
`python -m pip install -r requirements.txt`

See notes file for additional system dependencies.

Set up the desktop shortcuts:  
`cp ./pi-setup/find-me.desktop /home/pi/.local/share/applications
cp ./pi-setup/hellebores.desktop /home/pi/.local/share/applications
cp ./pi-setup/autorun.sh /home/pi`
  
**Pico setup**  
Using Thonny, open `./pico/main.py` and save it to the root folder of the microcontroller.

## Running
To use the interactive user interface, run "hellebores" from the Raspberry Pi desktop menu.

## Development
For performance and simplicity benefits, the software is designed with independent programs that are connected in a pipeline with data sent from one program to the next as a text stream. Control settings are stored in a `settings.json` file: the GUI program modifies this file and sends other programs a Posix signal whenever the settings file is updated, and they then re-load the `settings.json`.

The Pi code will run in WSL, Ubuntu, Mac or similar environments that have a modern python and can support the python dependencies, pipelines and signals. `hellebores.py` and the `rain_chooser.py` simulator require SDL for displaying the GUI and to accept touchscreen or mouse input. The GUI can run under X-Windows or in native Mac and MS-Windows if the SDL libraries are installed and are reachable from the python runtime environment. The run script will detect whether a serial interface to Pico is available and if not will use the `rain_chooser.py` simulator as a data source.

On a Posix system (Raspberry Pi OS, WSL, Ubuntu, Mac etc) execute `run/go.sh` from the terminal to run the full pipeline. This will access live measurements on real PQM hardware, and simulated measurements on other computers.

For Windows computers without WSL, use `run\go.bat` or, from the 'run' directory, `python go.py` from a cmd.exe shell. This sets up extra python code to implement named pipes and signals sufficiently to meet the needs of the app. However, some features of the go.sh script (eg software update) aren't implemented.

It's possible to access the running environment on a Pi using SSH. For working on the Pico microcontroller, use ssh -X and start `thonny` within your SSH session. This will redirect thonny's program window to your local X-server (needs a Linux or WSL2 system, or install X-server separately).

## Calibration
The four channels of the ADC each have an associated DC offset and gain calibration factor. The calibration factors for each device are stored in the `calibrations.json` file. The identity of the specific device at hand is stored in the `identity` file. Hardware scaling and calibration factors are applied to the data stream by the `scaler.py` program.



