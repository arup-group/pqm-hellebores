PROGRAMS= settings reader rain scaler framer analyser analysis_to_csv
OUTPUT_DIR= ../build
OBJECTS=
CFLAGS= -g -Wall -O0
LDLIBS= -lcjson -lm
CC=gcc

$(PROGRAMS): %: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $(OUTPUT_DIR)/$@

all: $(PROGRAMS)
