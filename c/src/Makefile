OUTPUT_DIR=../bin
SOURCES = reader.c rain.c scaler.c framer.c analysis_to_csv.c fft_example.c analyser.c settings.c
OBJECTS= settings.o
PROGRAMS := $(patsubst %.c, $(OUTPUT_DIR)/%, $(SOURCES))
LIBRARIES= kissfft
CFLAGS= -g -Wall -O3
LDLIBS= -lcjson -lm
CC=gcc

# Default rule
# Rewrite program targets so that they are targetted to write to the output
# directory
all: $(OBJECTS) $(PROGRAMS)

# Recipe for object files
$(OBJECTS): %.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Add settings.o to the linking once the source functions are more developed
$(OUTPUT_DIR)/fft_example $(OUTPUT_DIR)/analyser: $(OUTPUT_DIR)/%: %.c settings.o | $(OUTPUT_DIR)
	$(CC) $(CFLAGS) $< settings.o $(LDLIBS) -lkissfft-float -o $@

$(OUTPUT_DIR)/settings: settings.c | $(OUTPUT_DIR)
	$(CC) -DSETTINGS_HAS_MAIN $(CFLAGS) $< $(LDLIBS) -o $@

$(OUTPUT_DIR)/%: %.c settings.o | $(OUTPUT_DIR)
	$(CC) $(CFLAGS) $< settings.o $(LDLIBS) -o $@

# Shadow the implicit rule for all .c files, to do nothing for targets that
# don't match the defined patterns.
%: %.c
	$(NOOP)

$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

# kissfft library code is compiled in a sub-directory
# not necessary to compile if library can be installed via repository
# sudo apt install libkissfft-dev
kissfft: kissfft/libkissfft-float.a

kissfft/libkissfft-float.a:
	make --directory=kissfft KISSFFT_STATIC=1 KISSFFT_TOOLS=0

.PHONY: clean

clean:
	rm *.o ../bin/*
	#make --directory=kissfft clean
