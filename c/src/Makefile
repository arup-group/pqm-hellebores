OUTPUT_DIR=../bin
SOURCES= reader.c rain.c scaler.c framer.c analysis_to_csv.c fft_example.c analyser.c settings.c
PROGRAMS := $(patsubst %.c, $(OUTPUT_DIR)/%, $(SOURCES))
SETTINGS= settings.o
JSON= cJSON/cJSON.o
FFT= kissfft/kiss_fft.o kissfft/kiss_fftr.o
CFLAGS= -Wall -O3
LDLIBS= -lm
CC=gcc

# Default rule
# Rewrite program targets so that they are targetted to write to the output
# directory
all: $(JSON) $(FFT) $(SETTINGS) $(PROGRAMS)

# Object files
$(SETTINGS) $(JSON) $(FFT): %.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Programs requiring FFT
$(OUTPUT_DIR)/fft_example $(OUTPUT_DIR)/analyser: $(OUTPUT_DIR)/%: %.c $(SETTINGS) $(JSON) $(FFT) | $(OUTPUT_DIR)
	$(CC) $(CFLAGS) $< $(SETTINGS) $(JSON) $(FFT) $(LDLIBS) -o $@

# Settings program
$(OUTPUT_DIR)/settings: settings.c $(JSON) | $(OUTPUT_DIR)
	$(CC) -DSETTINGS_HAS_MAIN $(CFLAGS) $< $(JSON) $(LDLIBS) -o $@

# All other programs
$(OUTPUT_DIR)/%: %.c $(SETTINGS) $(JSON) | $(OUTPUT_DIR)
	$(CC) $(CFLAGS) $< $(SETTINGS) $(JSON) $(LDLIBS) -o $@

# Shadow the implicit rule for all .c files, to do nothing for targets that
# don't match the defined patterns.
%: %.c
	$(NOOP)

$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

# kissfft library code is compiled in a sub-directory
# not necessary to compile if library can be installed via repository
# sudo apt install libkissfft-dev
# kissfft: kissfft/libkissfft-float.a

#kissfft/libkissfft-float.a:
#	make --directory=kissfft KISSFFT_STATIC=1 KISSFFT_TOOLS=0

.PHONY: clean

clean:
	rm *.o ../bin/* ./kissfft/*.o ./cJSON/*.o
