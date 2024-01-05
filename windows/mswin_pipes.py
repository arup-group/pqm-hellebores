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

class Pipe:
    def __init__(self, pipe_name, mode):
        self.pfh = None  # pipe file handle
        if mode == 'r':
            self.open_existing_pipe(pipe_name)
        elif mode == 'w':
            self.open_new_pipe(pipe_name)
        else:
            print(f"Can't open pipe with this mode", file=sys.stderr)

    # these two functions facilitate use of the object with the 'with' syntax
    # so that we close the pipe properly even if there's an exception
    def __enter__(self):
        return self
    
    def __exit__(self):
        self.close()

    def open_existing_pipe(self, pipe_name):
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
                print(f"mswin_pipes.open_existing_pipe(): waiting for pipe {pipe_name} to become available.", file=sys.stderr) 
            time.sleep(1.0)
            retries = retries - 1
        if pipe == None:
            print(f"mswin_pipes.open_existing_pipe(): couldn't open pipe {pipe_name}, quitting.", file=sys.stderr)
            raise SystemExit
        self.pfh = pipe
        return self.pfh


    def open_new_pipe(self, pipe_name):
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
        except:
            print(f"mswin_pipes.open_new_pipe(): couldn't open pipe {pipe_name}, quitting.", file=sys.stderr)
            raise SystemExit
        self.pfh = pipe
        return self.pfh


    def readline(self):
        _, received_bytes = win32file.ReadFile(self.pfh, 64*1024)
        return str(received_bytes, encoding='utf-8')


    def writeline(self, line):
        win32file.WriteFile(self.pfh, str.encode(line))


    def is_data_available(self, t):
        t0 = time.time()
        while True:
            _, n, _ = win32pipe.PeekNamedPipe(self.pfh, 0)
            if n > 0:
                return True
            if time.time() - t0 > t:
                return False

    def close(self):
        win32file.CloseHandle(self.pfh)


def main():
    # trap incoming signals
    # we don't use st object for any other purpose here
    st=settings.Settings(reload_on_signal=False)

    try:
        command = sys.argv[1]
        if command == 'read':
            with Pipe(sys.argv[2], 'r') as p:
                while True:
                    sys.stdout.write(p.readline())
    
        elif command == 'write':
            with Pipe(sys.argv[2], 'w') as p:
                for line in sys.stdin:
                    p.writeline(line)
                    
        elif command == 'tee':
            with Pipe(sys.argv[2], 'w') as p1, Pipe(sys.argv[3], 'w') as p2:
                for line in sys.stdin:
                    p1.writeline(line)
                    p2.writeline(line)

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



