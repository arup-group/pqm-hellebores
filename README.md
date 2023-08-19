# pqm-hellebores
Power quality measurement (IiA 20139)

Invest-in-Arup research project to design and make a convenient way to measure and study the power quality and energy performance of single phase small power and lighting devices, that connect via plug-and-socket.

See IiA page for more project details [https://invest.arup.com/?layout=projsheet&projid=20139](https://invest.arup.com/?layout=projsheet&projid=20139)

## System requirements
The software in this repository is designed to run on standard Rasperry Pi and Raspberry Pi Pico microcontroller, but communicating with an analog-to-digital converter (ADC) on a custom PCB to take measurements of power parameters: voltage, current (low sensivity), current (high sensitivity) and earth leakage current. Following conversion and scaling to floating point measurement values, the measurement samples are processed by the software to provide a variety of performance measurements, waveform visualisation and logging. A local display and touch screen provide user interface.

**Raspberry Pi**  
Minimum hardware requirement is Raspberry Pi 3B+. Non-plus models do not have sufficent thermal dissipation to maintain sustained processing. Touch screen display with DSI interface, 800x480 pixels. Raspberry Pi OS (32 bit) with desktop. Prepare the image with connectivity to local/required wifi, SSH access, and change the default password. If you have one, pair a Bluetooth keyboard for local access.

**Raspberry Pi Pico**  
Use Thonny on your desktop or laptop computer to install MicroPython and verify that you have local REPL access to the microcontroller via USB.

## Installation
**Pico**  
Using Thonny, open `./pico/main.py` and save it to the root folder of the microcontroller.

**Pi**  
Start a terminal session via SSH or use a local keyboard.  

Clone the repository:  

`git clone https://github.com/arup-group/pqm-hellebores.git`

Change to the working directory:  

`cd pqm-hellebores/pi`

Install the dependencies  

`python3 -m pip install -r requirements.txt`

Set up the desktop shortcuts  

[tbc]

## Running
To use the interactive user interface, run "hellebores" from the Raspberry Pi desktop menu, or execute go.sh from the terminal.

## Development
For development work, the Pi code will run in WSL, Ubuntu, Mac or similar environments that have a modern python and can support the dependencies. hellebores.py requires SDL and can run under X-Windows or in native Mac and MS-Windows if the SDL libraries are installed and are reachable from the python run environment. The run script will detect whether a serial interface to Pico is available and if not will use simulated (pre-recorded) data for the purpose of testing.



