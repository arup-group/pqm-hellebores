SETTINGS_LIB= settings
ANALYSER= analyser
PROGRAMS= reader rain scaler framer analysis_to_csv
OUTPUT_DIR= ../build
OBJECTS=
CFLAGS= -g -Wall -O0
LDLIBS= -lcjson -lm
CC=gcc


settings.o: settings.c
	$(CC) $(CFLAGS) -o $(OUTPUT_DIR)/$@

# need to work on this to form the correct target file
kissfft/kiss_fft.o kissfft/kiss_fftr.o: %: %.c
	$(CC) $(CFLAGS) -c $< -o $@ 

analyser: analyser.c kissfft/kiss_fft.o kissfft/kiss_fftr.o
	$(CC) $(CFLAGS) analyser.c kissfft/kiss_fftr.o kissfft/kiss_fft.o $(LDLIBS) -o $(OUTPUT_DIR)/$@

$(PROGRAMS): %: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $(OUTPUT_DIR)/$@

all: $(PROGRAMS)
