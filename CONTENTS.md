# Description of files

## root /

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `README.md` | Overall description of project, with installation and setup instructions. |
| `notes` | Additional notes made during development, that may not be relevant. |
| `README.md` | Overall description of project, with installation and setup instructions. |
| `CONTENTS.md` | Outline description of files (this file). |
| `LICENSE` | The MIT license that makes this software open source. |
| `VERSION` | Version string used to help identify which version is running. Minor version numbers are incremented using a git hook when a commit is made. |
| `requirements.txt` | Used with python pip to install libraries that the software needs to run. |
| `environment.yaml` | Used with conda or mamba to install libraries, as an alternative to python pip. |
| `.gitignore` | Tells git to ignore certain directories or files that we do not want to accidentally add to the repository. |

## .git/

Contains the configuration, staging and commit history for version control

## configuration/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `calibrations.json` | Contains the calibration constants for each meter. |
| `identity` | Contains the name for a specific meter. This allows the software to apply the correct calibration constants. |
| `settings.json` | Contains settings and some fixed constants for the meter. A copy of this file is saved in RAMdisk when the meter is running, and is updated dynamically. |

## pico/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `main.py` | Basic server on Pico that can communicate with Pi for launching `stream.py` and maintaining software on the built-in flash storage. |
| `stream.py` | Communicates with the MCP3912 ADC to continuously acquire measurements into buffer memory and send it in blocks to the Pi via USB. |

## pqm/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `reader.py` | Receives binary data from the USB serial port and outputs as hex text, four channels per line. |
| `scaler.py` | Converts data received from `reader.py` to floating point decimal, applying scaling and calibration constants. Adds 'time axis' and instantaneous power to the stream. |
| `scaler_np.py` | Alternative implementation of `scaler.py` that uses numpy to do the transformation in an array. Turned out slower than naive solution. |
| `framer.py` | Receives data from `scaler.py` and processes into waveform 'frames'. Implements a trigger to align successive frames on screen. |
| `analyser.py` | Receives data from `scaler.py` and processes to calculate electrical measurements. |
| `analysis_to_csv.py` | Receives data from `analyser.py` and formats for `.csv` file |
| `calibrator.py` | Receives data from `scaler.py` and helps to determine calibration constants during setup. |
| `settings.py` | Imported into all `pqm` programs to provide a data object containing settings. Implements a mechanism to update settings between processes using a shared file and signals. |
| `font/` | Contains the open source Roboto typeface used in the UI. |
| `hellebores.py` | Implements the user interface and runs a custom display update and event loop. Imports all the other `hellebores` programs. |
| `hellebores_constants.py` | Consolidates most of the constants used in the UI. |
| `hellebores_controls.py` | Implements the UI required to alter settings, up/down buttons etc. |
| `hellebores_waveform.py` | Implements the display and control layout for the waveform mode. |
| `hellebores_multimeter.py` | Implements the display and control layout for the multimeter mode. |
| `hellebores_harmonic.py` | Implements the display and control layout for the harmonic analysis modes. |
| `mswin_pipes.py` | Provides functions to emulate `tee` and named pipes which are not available in the native shell on Windows systems. |
| `pico_control.py` | Command and control of the Pico. |
| `rain.py` | Used in development to take the place of `reader.py` and simulate the generation of sample data. |
| `rain_chooser.py` | Enhanced version of `rain.py` that provides a basic UI to simulate different source signals. |
| `version.py` | Reads and summarises version information. |


## run/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `pico_update.sh` | Contains settings and some fixed constants for the meter. A copy of this file is saved in RAMdisk when the meter is running, and is updated dynamically. |

## tools/
