rem Simplified run script for MS-Windows

rem Start the generator script, then tee it into two pipe files
start /b cmd /k "python rain_bucket.py ..\sample_files\simulated.out | python scaler.py | python mswin_pipes.py tee \\.\pipe\tee1 \\.\pipe\tee2"

rem Read one of the pipe branches and drive the data through trigger and mapper and then to waveform pipe
start /b cmd /k "python mswin_pipes.py read \\.\pipe\tee1 | python trigger.py | python mapper.py | python mswin_pipes.py write \\.\pipe\waveform"

rem Read the other pipe branch and drive the data through calculation and then to calculation pipe
start /b cmd /k "python mswin_pipes.py read \\.\pipe\tee2 | python analyser.py | python mswin_pipes.py write \\.\pipe\calculation"

rem Start the GUI providing references to the waveform and calculation pipe files
start /b cmd /k "python hellebores.py \\.\pipe\waveform \\.\pipe\calculation"



