PROGRAMS= settings reader rain scaler framer analyser analysis_to_csv
OBJECTS=
CFLAGS= -g -Wall -O0
LDLIBS= -lcjson -lm
CC=gcc

$(PROGRAMS): %: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o ../build/$@

all: $(PROGRAMS)
