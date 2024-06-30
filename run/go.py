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
    temp_dir = os.getenv('TEMP', '..')
    analysis_log_file = resolve_path(temp_dir, f'pqm.{os.getpid()}.csv')

    # Display version and initial settings
    os.system(f'{pyth} version.py')
    os.system(f'{pyth} settings.py')
    print('Starting processing...')
    print(f'Measurement source: {pyth} rain_chooser.py')
    print(f'Analysis log file: {analysis_log_file}')

    # An earlier attempt at forming the pipelines within a .BAT file worked using the START
    # command in a batch file. However, each instance of the 'START' command creates a new 
    # process group, even with the /b switch active. This won't work in our case, because the
    # SIGINT signal needs to be seen by all programs and it is not feasible to discover the
    # various process group IDs and send the signal to them all.

    # Named pipe names are defined here
    branch1 = r'\\.\pipe\branch1'
    waveform_pipe = r'\\.\pipe\waveform_pipe'
    analysis_pipe = r'\\.\pipe\analysis_pipe'
    # Contractions of the pipe handling commands
    # mswin_pipes.py is used to help read data into and out of named pipes, and to
    # implement the 'tee' command to duplicate a data stream.
    read = f'{pyth} mswin_pipes.py read'
    write = f'{pyth} mswin_pipes.py write'
    tee = f'{pyth} mswin_pipes.py tee'
 
    # We start three command lines. Standard shell anonymous pipes are used for anonymous
    # connections between programs, and named pipes are used when the data needs to be
    # accessed in another command. In addition to the 7 python processes required to actually
    # process the data, we will be running a further 4 python processes to drive the named
    # pipes on Windows.
    cmd_1 = (f'{pyth} rain_chooser.py | {pyth} scaler.py | {tee} {branch1}'
             f' | {pyth} trigger.py | {pyth} mapper.py | {write} {waveform_pipe}')
    cmd_2 = (f'{read} {branch1} | {pyth} analyser.py | {tee} {analysis_pipe}'
             f' | {pyth} analysis_to_csv.py > {analysis_log_file}')
    cmd_3 = f'{pyth} hellebores.py --waveform_file="{waveform_pipe}" --analysis_file="{analysis_pipe}"'

    # On Windows, SIGINT (CTRL_C events) are raised by hellebores.py when the user settings are
    # changed. All programs running within the console will receive this SIGINT signal.
    # (NB on Raspberry Pi and Posix, we use SIGUSR1 for this instead of CTRL_C)

    # when CATCH_SIGINT is set to 'yes', the signal handler in each program will catch SIGINT
    # events and treat them as a signal to re-load settings.json. If this environment variable
    # is not set, then SIGINT events will be handled as normal (ie the program will terminate).

    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
    os.environ['CATCH_SIGINT'] = 'yes'
    # strangely, Windows needs a moment to compose itself here
    time.sleep(1)
    # start all the programs
    ps = [ subprocess.Popen(c, shell=True) for c in [cmd_1, cmd_2, cmd_3] ]
    os.environ['CATCH_SIGINT'] = ''



def main():
    if os.name == 'nt':
        run_on_windows()
    else:
        print(f"This run script is for Windows only. Use ./go.sh for macOS and Linux.", file=sys.stderr)


if __name__ == '__main__':
    main()


