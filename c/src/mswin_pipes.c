// mswin_pipes.c: Windows named pipe utility (C translation of mswin_pipes.py)
// Compile with: cl mswin_pipes.c
// Usage: mswin_pipes.exe read <pipe> | write <pipe> | tee <pipe>

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUF_SIZE 65536

typedef struct {
    HANDLE pfh;
} Pipe;

int open_existing_pipe(Pipe *p, const char *pipe_name, int retries) {
    while (retries-- > 0) {
        p->pfh = CreateFileA(
            pipe_name,
            GENERIC_READ | GENERIC_WRITE,
            0,
            NULL,
            OPEN_EXISTING,
            0,
            NULL
        );
        if (p->pfh != INVALID_HANDLE_VALUE) {
            DWORD mode = PIPE_READMODE_MESSAGE;
            SetNamedPipeHandleState(p->pfh, &mode, NULL, NULL);
            return 1;
        }
        Sleep(1000);
    }
    fprintf(stderr, "mswin_pipes: couldn't open pipe %s\n", pipe_name);
    return 0;
}

int open_new_pipe(Pipe *p, const char *pipe_name) {
    p->pfh = CreateNamedPipeA(
        pipe_name,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        1, BUF_SIZE, BUF_SIZE,
        0,
        NULL
    );
    if (p->pfh == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "mswin_pipes: couldn't create pipe %s\n", pipe_name);
        return 0;
    }
    ConnectNamedPipe(p->pfh, NULL);
    return 1;
}

void close_pipe(Pipe *p) {
    if (p->pfh != INVALID_HANDLE_VALUE) CloseHandle(p->pfh);
}

int readline(Pipe *p, char *buf, DWORD bufsize) {
    DWORD bytesRead = 0;
    if (!ReadFile(p->pfh, buf, bufsize - 1, &bytesRead, NULL)) return 0;
    buf[bytesRead] = '\0';
    return bytesRead;
}

int writeline(Pipe *p, const char *line) {
    DWORD bytesWritten = 0;
    return WriteFile(p->pfh, line, (DWORD)strlen(line), &bytesWritten, NULL);
}

int peek_pipe(Pipe *p, double timeout_sec) {
    DWORD bytesAvail = 0;
    DWORD start = GetTickCount();
    while (1) {
        if (PeekNamedPipe(p->pfh, NULL, 0, NULL, &bytesAvail, NULL) && bytesAvail > 0) return 1;
        if ((GetTickCount() - start) > (DWORD)(timeout_sec * 1000)) break;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        printf("Usage: %s read <pipe> | write <pipe> | tee <pipe>\n", argv[0]);
        return 1;
    }
    char *command = argv[1];
    char *pipe_name = argv[2];
    Pipe p;
    if (strcmp(command, "read") == 0) {
        if (!open_existing_pipe(&p, pipe_name, 10)) return 1;
        char buf[BUF_SIZE];
        while (1) {
            int n = readline(&p, buf, BUF_SIZE);
            if (n > 0) printf("%s", buf);
        }
        close_pipe(&p);
    } else if (strcmp(command, "write") == 0) {
        if (!open_new_pipe(&p, pipe_name)) return 1;
        char buf[BUF_SIZE];
        while (fgets(buf, BUF_SIZE, stdin)) {
            writeline(&p, buf);
        }
        close_pipe(&p);
    } else if (strcmp(command, "tee") == 0) {
        if (!open_new_pipe(&p, pipe_name)) return 1;
        char buf[BUF_SIZE];
        while (fgets(buf, BUF_SIZE, stdin)) {
            writeline(&p, buf);
            printf("%s", buf);
        }
        close_pipe(&p);
    } else {
        fprintf(stderr, "%s: error processing the command %s.\n", argv[0], command);
        return 1;
    }
    return 0;
}
