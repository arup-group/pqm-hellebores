PROGRAMS= reader rain scaler framer analysis_to_csv
OBJECTS=
OUTPUT_DIR= ../build
CFLAGS= -g -Wall -O0
LDLIBS= -lcjson -lm
CC=gcc

all: $(PROGRAMS)

settings.o: settings.c
	$(CC) $(CFLAGS) -c $< -o $@

kissfft/kiss_fft.o kissfft/kiss_fftr.o: %: %.c
	$(CC) $(CFLAGS) -c $< -o $@ 

# Add settings.o to the linking once the source functions are more developed
$(PROGRAMS): %: %.c settings.o
	$(CC) $(CFLAGS) $< settings.o $(LDLIBS) -o $(OUTPUT_DIR)/$@

analyser: analyser.c kissfft/kiss_fft.o kissfft/kiss_fftr.o
	$(CC) $(CFLAGS) analyser.c kissfft/kiss_fftr.o kissfft/kiss_fft.o $(LDLIBS) -o $(OUTPUT_DIR)/$@

clean:
	rm kissfft/*.o *.o ../build/*
