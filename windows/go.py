import sys
import subprocess
import signal
import os
import time
import settings


def run_on_windows():
    # On Windows, SIGINT (CTRL_C events) are raised by hellebores.py when the user settings are changed.
    # all programs running within the console will receive this signal.

    # when CATCH_SIGINT is set to 'yes', the signal handler in each program will catch CTRL_C events
    # and treat them as a signal to re-load operating settings. If this environment variable is not set, then CTRL_C events
    # will be handled as normal (ie the program will terminate).
    os.environ['CATCH_SIGINT'] = 'yes'
    p1 = subprocess.Popen([sys.executable, 'rain_bucket.py', r'..\sample_files\simulated.out'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen([sys.executable, 'scaler.py'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen([sys.executable, 'mswin_pipes.py', 'tee', r'\\.\pipe\branch1', r'\\.\pipe\branch2'], stdin=p2.stdout)

    p11 = subprocess.Popen([sys.executable, 'mswin_pipes.py', 'read', r'\\.\pipe\branch1'], stdout=subprocess.PIPE)
    p12 = subprocess.Popen([sys.executable, 'trigger.py'], stdin=p11.stdout, stdout=subprocess.PIPE)
    p13 = subprocess.Popen([sys.executable, 'mapper.py'], stdin=p12.stdout, stdout=subprocess.PIPE)
    p14 = subprocess.Popen([sys.executable, 'mswin_pipes.py', 'write', r'\\.\pipe\waveform_pipe'], stdin=p13.stdout)

    p21 = subprocess.Popen([sys.executable, 'mswin_pipes.py', 'read', r'\\.\pipe\branch2'], stdout=subprocess.PIPE)
    p22 = subprocess.Popen([sys.executable, 'analyser.py'], stdin=p21.stdout, stdout=subprocess.PIPE)
    p23 = subprocess.Popen([sys.executable, 'mswin_pipes.py', 'write', r'\\.\pipe\calculation_pipe'], stdin=p22.stdout)

    p4 = subprocess.Popen([sys.executable, 'hellebores.py', r'\\.\pipe\waveform_pipe', r'\\.\pipe\calculation_pipe'])
    os.environ['CATCH_SIGINT'] = ''

    # An earlier attempt at forming the pipelines within a .BAT file worked as follows. However, each instance of the 'start' command creates a new
    # process group, even with the /b switch active. This won't work in our case, because the CTRL_C signal needs to be seen by all programs and it
    # is not possible to discover the various process group IDs and send the signal to them all.

    #rem Start the generator script, then tee it into two pipe files
    #start /b cmd /k "python rain_bucket.py ..\sample_files\simulated.out | python scaler.py | python mswin_pipes.py tee \\.\pipe\pipe1 \\.\pipe\pipe2"

    #rem Read the first pipe branch and drive the data through trigger and mapper and then to waveform pipe
    #start /b cmd /k "python mswin_pipes.py read \\.\pipe\pipe1 | python trigger.py | python mapper.py | python mswin_pipes.py write \\.\pipe\waveform_pipe"

    #rem Read the second pipe branch and drive the data through calculation and then to calculation pipe
    #start /b cmd /k "python mswin_pipes.py read \\.\pipe\pipe2 | python analyser.py | python mswin_pipes.py write \\.\pipe\calculation_pipe"

    #rem Start the GUI providing references to the waveform and calculation pipe files
    #start /b cmd /k "python hellebores.py \\.\pipe\waveform_pipe \\.\pipe\calculation_pipe"

def main():
    if os.name == 'nt':
        run_on_windows()
    else:
        print(f"This run script is for Windows platform only. Use ./go.sh for Linux.", file=sys.stderr)


if __name__ == '__main__':
    main()


