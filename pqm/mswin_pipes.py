######
### Utility functions to assist cmd.exe shell on windows systems
### Supports pipe in, pipe out and tee functionality, using APIs supported
### on MS Windows, but not available natively in the cmd.exe shell.
######

# install the pywin32 package via pip
import time
import sys
import win32pipe
import win32file
import msvcrt
import pywintypes
import io

# local
from settings import Settings


class Pipe:
    def __init__(self, pipe_name, mode):
        self.pfh = None  # pipe file handle
        self.open(pipe_name, mode)

    # these two functions facilitate use of the object with the 'with' syntax
    # so that we close the pipe properly even if there's an exception
    def __enter__(self):
        return self
    
    def __exit__(self, e_type, e_value, e_traceback):
        self.close()


    def open(self, pipe_name, mode):
        if mode == 'r':
            pipe = self.open_existing_pipe(pipe_name)
        elif mode == 'w':
            pipe = self.open_new_pipe(pipe_name)
        else:
            print(f"Can't open pipe with this mode", file=sys.stderr)
        self.pfh = pipe


    def open_existing_pipe(self, pipe_name, retries=10):
        """open a pipe for reading using Windows file API"""
        pipe = None
        if retries > 0:
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
            except (pywintypes.error, FileNotFoundError, PermissionError, OSError, IOError):
                time.sleep(1.0)
                pipe = self.open_existing_pipe(pipe_name, retries-1)
        else:
            print(f"mswin_pipes.open_existing_pipe(): couldn't open pipe {pipe_name}, "
                  f"quitting.", file=sys.stderr)
            raise SystemExit
        return pipe


    def open_new_pipe(self, pipe_name):
        """open a pipe for writing using Windows named pipe API"""
        pipe = None
        try:
            pipe = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536,
                0,
                None)
            win32pipe.ConnectNamedPipe(pipe, None)
        # need to check which exception is raised when CreateNamedPipe fails
        except (pywintypes.error, PermissionError, OSError, IOError):
            print(f"mswin_pipes.open_new_pipe(): couldn't open pipe {pipe_name}, "
                  f"quitting.", file=sys.stderr)
            raise SystemExit
        return pipe


    def get_handle(self):
        return self.pfh


    def readline(self):
        _, received_bytes = win32file.ReadFile(self.pfh, 64*1024)
        return str(received_bytes, encoding='utf-8')


    def writeline(self, line):
        win32file.WriteFile(self.pfh, str.encode(line))


    def close(self):
        win32file.CloseHandle(self.pfh)



def get_pipe_from_stream(stream):
    pfh = msvcrt.get_osfhandle(stream.fileno())
    return pfh


# windows lacks a 'select' function and so we have to do weird
# stuff to be able to check if data is available in the pipe
def peek_pipe(pfh, t):
    """boolean predicate to check if there is data waiting in the pipe"""
    data_waiting = False
    t0 = time.time()
    # need to run through the loop at least once, so don't test the time in
    # the while condition.
    while True:
        _, n, _ = win32pipe.PeekNamedPipe(pfh, 0)
        if n > 0:
            data_waiting = True
            break
        if time.time() - t0 > t:
            break
    return data_waiting


def main():
    # The only purpose we create st object is to to trap CTRL-C (SIGINT) signal.
    # This signal is used to control reload of settings in other programs 
    # in the project but unavoidably also received by this program.
    st=Settings(reload_on_signal=False)

    try:
        command = sys.argv[1]
        if command == 'read':
            # open an existing pipe for reading then copy to stdout
            with Pipe(sys.argv[2], 'r') as p:
                while True:
                    sys.stdout.write(p.readline())
    
        elif command == 'write':
            # open a new pipe for writing then copy data from stdin
            with Pipe(sys.argv[2], 'w') as p:
                for line in sys.stdin:
                    p.writeline(line)
                    
        elif command == 'tee':
            # open two pipes for writing then copy from stdin to both
            with Pipe(sys.argv[2], 'w') as p1, Pipe(sys.argv[3], 'w') as p2:
                for line in sys.stdin:
                    p1.writeline(line)
                    p2.writeline(line)

    except:
        print(f"{sys.argv[0]}: error processing the command {command}.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    # on windows, pipe names need to be in the form \\.\pipe\foo
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} read [pipe], or {sys.argv[0]} write [pipe], "
              f"or {sys.argv[0]} tee [pipe1] [pipe2]")
        sys.exit(1)
    else:
        main()



