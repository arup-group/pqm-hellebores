######
### Utility file to assist cmd.exe shell on windows systems
### Reads from pipe and transfers to stdout
######

# install the pywin32 package via pip
import time
import sys



def open_pipe_for_input(pipe_name):
    try:
        pipe = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        res = win32pipe.SetNamedPipeHandleState(pipe, win32pipe.PIPE_READMODE_MESSAGE, None, None)
    except:
        print("Couldn't open requested pipe name for input.", file=sys.stderr) 
    return pipe


def stream_data_from_pipe(pipe, outgoing):
    for line in win32file.ReadFile(pipe, 64*1024):
        outgoing.write(line)


def main():
    pipe_name = sys.argv[1]   # needs to be in the form \\.\pipe\foo
    pipe = open_pipe_for_input(pipe_name)
    stream_data_from_pipe(pipe, sys.stdout)  




if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {argv[0]} [pipe]")
        sys.exit(1)
    else:
        main()



