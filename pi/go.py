#rem Start the generator script, then tee it into two pipe files
#start /b cmd /k "python rain_bucket.py ..\sample_files\simulated.out | python scaler.py | python mswin_pipes.py tee \\.\pipe\pipe1 \\.\pipe\pipe2"

#rem Read the first pipe branch and drive the data through trigger and mapper and then to waveform pipe
#start /b cmd /k "python mswin_pipes.py read \\.\pipe\pipe1 | python trigger.py | python mapper.py | python mswin_pipes.py write \\.\pipe\waveform_pipe"

#rem Read the second pipe branch and drive the data through calculation and then to calculation pipe
#start /b cmd /k "python mswin_pipes.py read \\.\pipe\pipe2 | python analyser.py | python mswin_pipes.py write \\.\pipe\calculation_pipe"

#rem Start the GUI providing references to the waveform and calculation pipe files
#start /b cmd /k "python hellebores.py \\.\pipe\waveform_pipe \\.\pipe\calculation_pipe"


import sys
import subprocess
import signal
import os
import time

# SIGINT (CTRL_C events) are raised by hellebores.py when the user settings are changed.
# all programs running within the console will receive this signal.

# this script will therefore see SIGINT events, and we need to trap (ignore) them
def signal_handler(signum, frame):
    print('go.py: trapped signal', file=sys.stderr)
    pass

# configure the handler
if os.name == 'posix':
    signal.signal(signal.SIGUSR1, signal_handler)
elif os.name == 'nt':
    signal.signal(signal.SIGINT, signal_handler)
else:
    print(f"Don't know how to set up signals on {os.name} platform.", file=sys.stderr)



# the subprocess programs also receive SIGINT events, which are dealt with within settings.py
# if CTRL_C_RESPONSE is set to read, the settings.json is read into memory
# if CTRL_C_RESPONSE is set to ignore, then the signal is ignored
# if CTRL_C_RESPONSE is not set in the environment, then a python KeyError exception is raised,
# which will terminate the program
os.environ['CTRL_C_RESPONSE'] = 'read'
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

os.environ['CTRL_C_RESPONSE'] = 'ignore'
p4 = subprocess.Popen([sys.executable, 'hellebores.py', r'\\.\pipe\waveform_pipe', r'\\.\pipe\calculation_pipe'])

os.environ['CTRL_C_RESPONSE'] = ''

