# Description of files

## root /

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `README.md` | Overall description of project, with setup instructions. |
| `notes` | Additional notes that may not be relevant. |
| `CONTENTS.md` | Description of files (this file). |
| `LICENSE` | The MIT license that makes this software open source. |
| `VERSION` | Version string used to identify which version is running. Minor version numbers are incremented using a git hook when a commit is made. |
| `requirements.txt` | Used with python pip to install libraries that the software needs to run. |
| `environment.yaml` | Used with conda or mamba to install libraries, as an alternative to python pip. |
| `.gitignore` | Tells git to ignore certain directories or files that we do not want to accidentally add to the repository. |

## .git/

Contains the configuration, staging and commit history for version control

## configuration/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `calibrations.json` | Contains the calibration constants for each meter. |
| `identity` | Contains the name for a specific meter. This allows the software to apply the correct calibration constants. This is the only file that is different on different meters, and is therefore not included in the repository. |
| `settings.json` | Contains settings and some fixed constants for the meter. A copy of this file is saved in RAMdisk when the meter is running, and is updated dynamically by `settings.py`. |

## nb/

Contains Jupyter notebook and sample data for testing and proving the electrical calculations that are implemented in `analyser.py`.

To open the notebook, navigate to this folder on your computer and type `jupyter notebook` in the terminal. This will start a local web server. Open the localhost URL that is offered in your web browser, then open the notebook file.

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `energy_and_power_quality_calculations_2.ipynb` | The notebook file. |
| `data_sample_10_seconds.out` | Sample data used by the notebook. Equivalent to the output from `scaler.py`. |

## output_files/

`output_files/` is a symbolic link to a directory in the RAMdisk filesystem in Raspberry Pi (and other Linux systems).

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `analysis_pipe` | Named pipe that transmits measurements from `analyser.py` to `hellebores.py`. |
| `waveform_pipe` | Named pipe that transmits waveforms from `framer.py` to `hellebores.py`. |
| `error.log` | Output to `stderr` is redirected to this file by the `go.sh` script. The file can help with tracing bugs. |
| `pqm.nnnn.csv` | CSV file with a log of measurement results from `analyser.py`. nnnn corresponds to the PID of analysis_to_csv.py. |
| `settings.json` | Copy of `configuration/settings.json` but updated dynamically according to user input. This is the means of communicating changes of settings to programs in the pipeline. |

## pico/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `main.py` | Interactive process on Pico that can communicate with Pi for launching `stream.py` and update files on the built-in flash storage. |
| `stream.py` | Communicates with the MCP3912 ADC to continuously acquire measurements into buffer memory and send it in blocks to the Pi via USB. This is the source of data for the entire system. |

## pqm/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `reader.py` | Receives binary data from the USB serial port and outputs as hex text, four channels per line. |
| `scaler.py` | Converts data received from `reader.py` to floating point decimal. Applies scaling and calibration constants. Adds 'time axis' and instantaneous power to the stream. |
| `scaler_np.py` | Alternative implementation of `scaler.py` that uses numpy to do the transformation in an array. Turned out slower than native solution. Not used, but retained for reference. |
| `framer.py` | Receives data from `scaler.py` and processes into waveform 'frames'. Implements a trigger to align successive frames on screen. Outputs pixel coordinates that are used for plotting waveforms. |
| `analyser.py` | Receives data from `scaler.py` and processes to calculate electrical measurements. |
| `analysis_to_csv.py` | Receives data from `analyser.py` and formats for `.csv` file. |
| `calibrator.py` | Receives data from `scaler.py` and helps to determine calibration constants during setup. |
| `settings.py` | Imported into all `pqm` programs to provide a data object containing settings. Implements a mechanism to update settings between processes using a shared file and signals. |
| `font/` | Contains the open source Roboto typeface used in the UI. |
| `hellebores.py` | Implements the user interface and runs a custom display update and event loop. Imports all the other `hellebores` programs. |
| `hellebores_constants.py` | Consolidates most of the constants used in the UI. |
| `hellebores_controls.py` | Implements the UI required to alter settings, up/down buttons etc. |
| `hellebores_waveform.py` | Implements the display and control layout for the waveform mode. |
| `hellebores_multimeter.py` | Implements the display and control layout for the multimeter mode. |
| `hellebores_harmonic.py` | Implements the display and control layout for the harmonic analysis modes. |
| `mswin_pipes.py` | Provides functions to emulate `tee` and named pipes which are not available in the shell on Windows systems. |
| `pico_control.py` | Command and control of the Pico. Communicates with `main.py` running on Pico. |
| `rain.py` | Used on laptop computer to take the place of `reader.py` and simulate the generation of sample data. |
| `rain_chooser.py` | Enhanced version of `rain.py` that provides a UI to simulate different source signals. |
| `version.py` | Reads and summarises version information. |


## run/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `go.sh` | Run script for Pi and Unix-like systems. |
| `go.bat` | Run script for Windows, sorts out working directory and environment, then hands off to `go.py`. |
| `go.py` | Run script for Windows. |
| `pqm-launcher.sh` | Launcher script that presents version information and startup buttons. |
| `pqm-launcher.desktop` | Desktop file for `pqm-launcher.sh` that is added to the menu and autostart feature of Pi. |
| `hellebores.desktop` | Desktop file for `go.sh` that is added to the menu of Pi. |
| `pqm.ico` | Project icon. |
| `pqm64.png` | Icon in 64x64 png format. |
| `pqm128.png` | Icon in 128x128 png format. |
| `pqm256.png` | Icon in 256x256 png format. |

## tools/

| Filename                      | Description                   |
| :---------------------------- | :---------------------------- |
| `line_speed.py` | Attached to the end of a pipeline, reports on the number of lines per second received. Used to help verify performance of processing. |
| `raw_reader.py` | Reads from serial port in raw binary format, and passes through to `stdout`. |
| `push_settings.sh` | Sends the `SIGUSR1` signal. Used for testing the `settings.py` update functions. |
| `pico_update.sh` | Script to verify files stored on the Pico flash storage and update to current version if necessary. Communicates with `main.py` running on Pico to do this. |
