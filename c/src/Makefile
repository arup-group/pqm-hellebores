PROGRAMS= reader rain scaler framer analysis_to_csv fft_example analyser
OBJECTS= settings.o
LIBRARIES= kissfft
OUTPUT_DIR=../bin
CFLAGS= -g -Wall -O3
LDLIBS= -lcjson -lm
CC=gcc

# Default rule
all: ../bin $(OBJECTS) $(PROGRAMS)

# Recipe for object files
$(OBJECTS): %.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Rewrite program targets so that they are targetted to write to the output
# directory
$(PROGRAMS): %: $(OUTPUT_DIR)/%

# Add settings.o to the linking once the source functions are more developed
$(OUTPUT_DIR)/fft_example $(OUTPUT_DIR)/analyser: $(OUTPUT_DIR)/%: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -lkissfft-float -o $@

$(OUTPUT_DIR)/%: %.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

# Shadow the implicit rule for all .c files, to do nothing for targets that
# don't match the defined patterns.
%: %.c
	$(NOOP)

../bin:
	if [ ! -d ../bin ]; then mkdir ../bin; fi

# kissfft library code is compiled in a sub-directory
# not necessary to compile if library can be installed via repository
# sudo apt install libkissfft-dev
kissfft: kissfft/libkissfft-float.a

kissfft/libkissfft-float.a:
	make --directory=kissfft KISSFFT_STATIC=1 KISSFFT_TOOLS=0

.PHONY: clean

clean:
	rm *.o ../build/*
	#make --directory=kissfft clean
