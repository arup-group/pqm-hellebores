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
import settings

def open_pipe_for_input(pipe_name):
    pipe = None
    retries = 6
    while pipe == None and retries > 0:
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
            print(f"mswin_pipes.open_pipe_for_input(): waiting for pipe {pipe_name} to become available.", file=sys.stderr) 
            time.sleep(1.0)
            retries = retries - 1
    if pipe == None:
        print(f"mswin_pipes.open_pipe_for_input(): couldn't open pipe {pipe_name}, quitting.", file=sys.stderr)
        raise SystemExit
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
        print("Couldn't open the requested pipe for output, quitting.", sys.stderr)
        raise SystemExit
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


def close_pipe(pipe):
    win32file.CloseHandle(pipe)


def main():
    # trap incoming signals
    # we don't use st object for any other purpose here
    st=settings.Settings()

    try:
        command = sys.argv[1]
        if command == 'read':
            pipe = open_pipe_for_input(sys.argv[2])
            while True:
                sys.stdout.write(read_from_pipe(pipe))
            close_pipe(pipe)
    
        elif command == 'write':
            pipe = open_pipe_for_output(sys.argv[2])
            while True:
                line = sys.stdin.readline()
                if line:
                    write_to_pipe(line, pipe)
                else:
                    break
            close_pipe(pipe)

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
            close_pipe(pipe1)
            close_pipe(pipe2)

        else:
            pass
    except:
        print(f"{sys.argv[0]}: error processing the command {command}.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    # pipe names need to be in the form \\.\pipe\foo
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} read [pipe], or {sys.argv[0]} write [pipe], or {sys.argv[0]} tee [pipe1] [pipe2]")
        sys.exit(1)
    else:
        main()



