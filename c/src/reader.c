// reader.c: Cross-platform serial reader (C translation of reader.py)
// Compile with: gcc -o reader reader.c
// Usage: ./reader

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <dirent.h>
#endif

#define BUFFER_SIZE 128
#define BLOCK_SIZE (BUFFER_SIZE * 8)

#ifdef _WIN32
const char *find_serial_device() {
    static char port[32];
    for (int i = 1; i <= 8; ++i) {
        sprintf(port, "COM%2d", i);
        HANDLE h = CreateFileA(port, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            CloseHandle(h);
            return port;
        }
    }
    return NULL;
}
#else
const char *find_serial_device() {
    static char port[32];
    DIR *d = opendir("/dev");
    struct dirent *entry;
    if (!d) return NULL;
    while ((entry = readdir(d)) != NULL) {
        if (strncmp(entry->d_name, "ttyUSB", 6) == 0) {
            sprintf(port, "/dev/%.16s", entry->d_name);
            closedir(d);
            return port;
        }
    }
    closedir(d);
    return NULL;
}
#endif

void print_hex_block(const uint8_t *bs) {
    char hexstr[BLOCK_SIZE * 2 + 1];
    for (int i = 0; i < BLOCK_SIZE; ++i) {
        sprintf(hexstr + i * 2, "%02x", bs[i]);
    }
    for (int i = 0; i < BLOCK_SIZE * 2; i += 16) {
        printf("%.*s %.*s %.*s %.*s\n", 4, hexstr + i, 4, hexstr + i + 4, 4, hexstr + i + 8, 4, hexstr + i + 12);
    }
}

int main() {
    const char *port_name = find_serial_device();
    if (!port_name) {
        fprintf(stderr, "reader.c: No serial device found.\n");
        return 1;
    }
    fprintf(stderr, "reader.c: Connected to %s.\n", port_name);
#ifdef _WIN32
    HANDLE hSerial = CreateFileA(port_name, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (hSerial == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "reader.c: Failed to open serial port.\n");
        return 1;
    }
    // Set timeouts and config as needed
    uint8_t bs[BLOCK_SIZE];
    DWORD bytesRead;
    int retries = 5;
    while (retries > 0) {
        if (ReadFile(hSerial, bs, BLOCK_SIZE, &bytesRead, NULL) && bytesRead == BLOCK_SIZE) {
            print_hex_block(bs);
            retries = 5;
        } else {
            fprintf(stderr, "reader.c: Failed to read from serial port.\n");
            retries--;
        }
    }
    CloseHandle(hSerial);
#else
    int fd = open(port_name, O_RDWR | O_NOCTTY | O_SYNC);
    if (fd < 0) {
        fprintf(stderr, "reader.c: Failed to open serial port.\n");
        return 1;
    }
    struct termios tty;
    memset(&tty, 0, sizeof tty);
    if (tcgetattr(fd, &tty) != 0) {
        fprintf(stderr, "reader.c: Error from tcgetattr.\n");
        close(fd);
        return 1;
    }
    cfsetospeed(&tty, B115200);
    cfsetispeed(&tty, B115200);
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_iflag = 0;
    tty.c_oflag = 0;
    tty.c_lflag = 0;
    // Minimum number of bytes before firing an event, or VTIME * 0.1 seconds
    // if fewer bytes remaining
    tty.c_cc[VMIN]  = 128;
    tty.c_cc[VTIME] = 2;
    tcsetattr(fd, TCSANOW, &tty);
    uint8_t bs[BLOCK_SIZE];
    int retries = 5;
    while (retries > 0) {
        int n = read(fd, bs, BLOCK_SIZE);
        if (n == BLOCK_SIZE) {
            print_hex_block(bs);
            retries = 5;
        } else {
            fprintf(stderr, "reader.c: Failed to read from serial port.\n");
            retries--;
        }
    }
    close(fd);
#endif
    fprintf(stderr, "reader.c: Read error was persistent, exiting loop.\n");
    return 0;
}
