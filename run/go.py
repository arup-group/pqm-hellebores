import sys
import subprocess
import signal
import os
import time



def resolve_path(path, file):
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), path, file)
    resolved_path = os.path.abspath(file_path)
    return resolved_path


def run_on_windows():
    # This function (mostly) implements process-to-process pipeline code that can't be expressed
    # completely in Windows command shell.

    # Change working directory to the program directory (NB relative to the location of this file)
    os.chdir(resolve_path('../pqm', ''))
    pyth = sys.executable

    # Display version and initial settings
    os.system(f'{pyth} version.py')
    os.system(f'{pyth} settings.py')

    # An earlier attempt at forming the pipelines within a .BAT file worked using the START
    # command in a batch file. However, each instance of the 'start' command creates a new 
    # process group, even with the /b switch active. This won't work in our case, because the
    # SIGINT signal needs to be seen by all programs and it is not feasible to discover the
    # various process group IDs and send the signal to them all.

    # Named pipe names are defined here
    pipe_branch1 = r'\\.\pipe\branch1'
    pipe_branch2 = r'\\.\pipe\branch2'
    pipe_waveform = r'\\.\pipe\waveform_pipe'
    pipe_analysis = r'\\.\pipe\analysis_pipe'
 
    # We will start four separate command lines
    # mswin_pipes.py is used to help read data into and out of named pipes, and to
    # implement the 'tee' command to duplicate the data stream from scaler.py.
    # Standard shell anonymous pipes are used for the remainder of connections between programs.
    cmd_1 = (f'{pyth} rain_chooser.py | {pyth} scaler.py'
             f' | {pyth} mswin_pipes.py tee {pipe_branch1} {pipe_branch2}')
    cmd_2 = (f'{pyth} mswin_pipes.py read {pipe_branch1} | {pyth} trigger.py | {pyth} mapper.py'
             f' | {pyth} mswin_pipes.py write {pipe_waveform}')
    cmd_3 = (f'{pyth} mswin_pipes.py read {pipe_branch2} | {pyth} analyser.py'
             f' | {pyth} mswin_pipes.py write {pipe_analysis}')
    cmd_4 = f'{pyth} hellebores.py {pipe_waveform} {pipe_analysis}'

    # On Windows, SIGINT (CTRL_C events) are raised by hellebores.py when the user settings are
    # changed. All programs running within the console will receive this SIGINT signal.
    # (NB on Raspberry Pi and Posix, we use SIGUSR1 for this instead of CTRL_C)

    # when CATCH_SIGINT is set to 'yes', the signal handler in each program will catch SIGINT
    # events and treat them as a signal to re-load settings.json. If this environment variable
    # is not set, then SIGINT events will be handled as normal (ie the program will terminate).
    os.environ['CATCH_SIGINT'] = 'yes'

    # start all the programs
    # In addition to the 6 python processes required to actually process the data, there are a
    # further 14 processes required to support on Windows:
    # 1 instance of go.py
    # 4x2 instances of subprocess (one python process at each end of each shell sub-process)
    # 5 instances of mswin_pipes.py
    ps = [ subprocess.Popen(c, shell=True) for c in [cmd_1, cmd_2, cmd_3, cmd_4] ]

    # Restore the environment.
    # Exit from this process is delayed until the sub-processes have exited.
    os.environ['CATCH_SIGINT'] = ''


def main():
    if os.name == 'nt':
        run_on_windows()
    else:
        print(f"This run script is for Windows only. Use ./go.sh for Linux.", file=sys.stderr)


if __name__ == '__main__':
    main()


