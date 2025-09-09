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

analyser: analyser.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -lkissfft-float -o $(OUTPUT_DIR)/$@

$(PROGRAMS): %: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $(OUTPUT_DIR)/$@

all: $(PROGRAMS)
