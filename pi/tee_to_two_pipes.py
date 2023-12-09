######
### Utility file to assist cmd.exe shell on windows systems
### Feeds stdin into two named pipes
######

# install the pywin32 package via pip
import time
import sys
import win32pipe
import win32file


def open_pipes_for_output(pipe1_name, pipe2_name):
    try:
        pipe1 = win32pipe.CreateNamedPipe(
            pipe1_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)
        pipe2 = win32pipe.CreateNamedPipe(
            pipe2_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)
        win32pipe.ConnectNamedPipe(pipe1, None)
        win32pipe.ConnectNamedPipe(pipe2, None)
    except:
        print("Couldn't open the requested pipes for output.", sys.stderr)
    return (pipe1, pipe2)


def stream_data_to_pipes(incoming, pipe1, pipe2):
    for line in incoming.readline():
        win32file.WriteFile(pipe1, line)
        win32file.WriteFile(pipe2, line)


def main():
    pipe1_name = sys.argv[1]   # needs to be in the form \\.\pipe\foo
    pipe2_name = sys.argv[2]   # needs to be in the form \\.\pipe\bar
    pipe1, pipe2 = open_pipes_for_output(pipe1_name, pipe2_name)
    stream_data_to_pipes(sys.stdin, pipe1, pipe2)  



if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {argv[0]} [pipe0] [pipe1]")
        sys.exit(1)
    else:
        main()



