# pqm-hellebores
Power quality measurement (IiA 20139)

Invest-in-Arup research project to design and make a convenient way to measure and study the power quality and energy performance of single phase small power and lighting devices, that connect via plug-and-socket.

See IiA page for more project details [https://invest.arup.com/?layout=projsheet&projid=20139](https://invest.arup.com/?layout=projsheet&projid=20139)

## System requirements
The software is designed to run on Raspberry Pi and Raspberry Pi Pico microcontroller, communicating with an analog-to-digital converter (ADC: MCP3912) on a custom PCB to source measurements of power parameters: voltage, current (full range), current (low range) and earth leakage current. Following conversion and scaling to floating point measurement values, the physical measurement samples are further processed to provide a variety of derivative measurements, waveform visualisation and logging. A local touch screen provides user interface.

Partly to enable rapid development cycles, but also to validate calculations, the software will also run on desktop computers using a simulator to take the place of the Pico/ADC to generate sample data.

**Raspberry Pi**  

Minimum hardware requirement is Raspberry Pi 3B+. Non-plus models do not have sufficent thermal dissipation for high CPU loads. Touch screen display with DSI interface, 800x480 pixels. Raspberry Pi OS (32 bit) with desktop. Prepare the image with connectivity to local/required wifi, SSH access, and change the default password. If you have one, pair a Bluetooth keyboard for local access.

**Raspberry Pi Pico**  

Requires Thonny on your laptop computer to install MicroPython on the Pico and verify that you have local REPL access to the microcontroller via a USB cable.

## Installation
**Raspberry PI SD card**

For this step, remove the Raspberry Pi and lid and disconnect the Pico USB connector and the ribbon cable. Apply power from an auxiliary power supply: do not power up the meter PCB. You may also need a USB or bluetooth keyboard to complete the process.

Prepare the SD card using Raspberry Pi Imager. As a convenience, a USB stick with Raspberry Pi OS can be prepared first, plugged in the Pi and then that image booted to write to an in-situ SD card -- avoids the need to remove DSI ribbon cable.

Choose Raspberry Pi 3 hardware, and 32 bit 'Bookworm' operating system.
Set a project specific password.
Enable the option for remote SSH access.
Set the wifi country, SSID and password to be used for initial access.

Proceed to install and verify the SD card.

Shutdown the system, remove the USB stick and re-assemble the Raspberry Pi in the power quality meter, remembering to connect both the USB cable to Pico and the ribbon cable.

**Power quality meter software setup**

1. Start a terminal session via SSH. (As alternative, you could use a bluetooth keyboard and work locally.)
```
ssh -X pi@www.xxx.yyy.zzz
```

2. Clone the repository:  
```
git clone https://github.com/arup-group/pqm-hellebores.git
```

3. Change to the working directory. Create a virtual environment, and activate it:
```
cd pqm-hellebores
python -m venv .venv
source .venv/bin/activate
```

4. Install the dependencies (the additional maths libraries are needed to support the numpy library):
```
sudo apt install libatlas-base-dev libopenblas-dev
python -m pip install -r requirements.txt
```

5. Set the device identity. In place of PQM-n, use the identity of your specific power quality monitor, eg PQM-1:
```
echo PQM-n > configuration/identity
```

6. Install bluetooth file transfer client (optional):
```
sudo apt install blueman
```

7. Enable Raspberry Pi support features:

In the Preferences | Raspberry Pi Configuration menu, enable the VNC server and the on-screen keyboard: the keyboard is found in the 'Display' tab -- select 'Enable always', and the VNC server is found in the 'Interfaces' tab -- verify that SSH and (optionally) VNC are enabled.

8. Add shortcuts to the 'Other' desktop menu:
```
ln -s /home/pi/pqm-hellebores/run/hellebores.desktop /home/pi/.local/share/applications/hellebores.desktop
ln -s /home/pi/pqm-hellebores/run/pqm-launcher.desktop /home/pi/.local/share/applications/pqm-launcher.desktop
```

9. Also add the launcher script to the desktop autostart directory.
```
mkdir /home/pi/.config/autostart
ln -s /home/pi/pqm-hellebores/run/pqm-launcher.desktop /home/pi/.config/autostart/pqm-launcher.desktop
```

10. Update the Raspberry Pi OS.

The OS can be updated from the menu at the top. Alternatively, from a terminal:
```
sudo apt update
sudo apt upgrade
```

Dependencies sometimes change with OS updates. See notes file for potential additional system dependencies and troubleshooting.
  
**Pico setup**

Using Thonny:

Open `./pico/main.py` and save it to the root folder of the microcontroller.
Open `./pico/stream.py` and save it to the root folder of the microcontroller.

## Running
To use the interactive user interface, select "START" from the launcher dialog. Alternatively, run "hellebores" from the Raspberry Pi desktop menu.

It's possible to access the running environment on a Pi using SSH. For working on the Pico microcontroller, use ssh -X to connect to the Pi and then start `thonny` within your SSH session. This will redirect thonny's program window to your local X-server (needs a Linux or WSL2 system, or install an X-server separately).

## Desktop computers
**Ubuntu (incl. WSL) and macOS**

On a system with python3 and git installed, proceed as follows:
```
git clone https://github.com/arup-group/pqm-hellebores.git
cd pqm-hellebores
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
echo PQM-0 > configuration/identity
run/go.sh
```

**Windows**

In a command window with python and git available:
```
git clone https://github.com/arup-group/pqm-hellebores.git
cd pqm-hellebores
python -m venv .venv-windows
.venv-windows\scripts\activate
python -m pip install -r requirements.txt
echo PQM-0 > configuration\identity
run\go
```

NB Some code paths are different on Windows to allow the project to run, and the files `mswin_pipes.py`, `go.bat` and `go.py` are exclusive to Windows. Note that some features of the `go.sh` script (eg software update) are not implemented.


## Development

The software is designed with 'Unix Philosophy' in mind, which helps to simplify and modularise the design while also achieving high performance. Independent programs are connected in a pipeline with data sent from one program to the next as a text stream. Control settings are stored in a `settings.json` file: the GUI program modifies this file and sends other programs a Posix signal whenever the settings file is updated, and they then re-load the `settings.json`. The project is intended to yield to experimentation: the behaviour of the programs at each step of the pipeline can be studied, verified and changed on the command line.

The Pi code will run in WSL, Ubuntu, Mac or similar environments that have a modern python and can support the python dependencies, pipelines and signals. `hellebores.py` and the `rain_chooser.py` simulator require SDL for displaying the GUI and to accept touchscreen or mouse input. The GUI can run under X-Windows or in native Mac and MS-Windows if the SDL libraries are installed and are reachable from the python runtime environment. The run script will test whether a serial interface to Pico is available and if not will use the `rain_chooser.py` simulator as a data source.

You'll find that automatic checking tools, such as within `VS Code` will spuriously identify problems with resolving some python libraries. This is because files within the project target different runtime environments: Linux, Pico (micropython) and Windows.

When working with `git`, it's possible to automate minor version number increments when making a commit, by editing the following lines at the end of `.git/hooks/pre-commit.sample` and then rename the hook file to `.git/hooks/pre-commit`.

```
# If there are whitespace errors, print the offending file names and fail.
#exec git diff-index --check --cached $against --
if ! git diff-index --check --cached $against --; then
    exit 1
fi

# Increment version number and then add the VERSION file to the commit
./pqm/version.py --increment_sub_version
git add ./VERSION
```

## Calibration

The four channels of the ADC each have associated calibration factors: DC offset, analogue gain and timing skew. The calibration factors for each device are stored in the `calibrations.json` file. The identity of the specific device at hand is stored in the `configuration/identity` file. Hardware scaling and calibration factors are applied to the data stream by the `scaler.py` program.

The `calibrator.py` program is used in conjunction with a calibrated true RMS multimeter. The calibration procedure is used to determine device-specific calibration factors to be entered into the `calibrations.json` file.

