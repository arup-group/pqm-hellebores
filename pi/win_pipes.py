######
### Utility functions to assist cmd.exe shell on windows systems
### Supports pipe in, pipe out and tee functionality, using APIs supported
### on MS Windows, but not available natively in the shell.
######

# install the pywin32 package via pip
import time
import sys
import win32pipe
import win32file


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
        sys.exit(1)
    return pipe


def open_pipe_for_output(pipe_name):
    try:
        pipe = win32pipe.CreateNamedPipe(
            pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)
        win32pipe.ConnectNamedPipe(pipe, None)
    except:
        print("Couldn't open the requested pipe for output.", sys.stderr)
    return pipe


def read_from_pipe(pipe):
    _, received_bytes = win32file.ReadFile(pipe, 64*1024)
    return str(received_bytes, encoding='utf-8')


def write_to_pipe(line, pipe):
    win32file.WriteFile(pipe, str.encode(line))


def is_data_available(pipe, t):
    t0 = time.time()
    while True:
        _, n, _ = win32pipe.PeekNamedPipe(pipe, 0)
        if n > 0:
            return True
        if time.time() - t0 > t:
            return False


def main():
    command = sys.argv[1]
    if command == 'read':
        pipe = open_pipe_for_input(sys.argv[2])
        while True:
            sys.stdout.write(read_from_pipe(pipe))
    elif command == 'write':
        pipe = open_pipe_for_output(sys.argv[2])
        while True:
            line = sys.stdin.readline()
            if line:
                write_to_pipe(line, pipe)
            else:
                break
    elif command == 'tee':
        pipe1 = open_pipe_for_output(sys.argv[2])
        pipe2 = open_pipe_for_output(sys.argv[3])
        while True:
            line = sys.stdin.readline()
            if line:
                write_to_pipe(line, pipe1)
                write_to_pipe(line, pipe2)
            else:
                break
    else:
        pass


if __name__ == '__main__':
    # pipe names need to be in the form \\.\pipe\foo
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} read [pipe], or {sys.argv[0]} write [pipe], or {sys.argv[0]} tee [pipe1] [pipe2]")
        sys.exit(1)
    else:
        main()



