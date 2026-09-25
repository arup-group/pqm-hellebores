#!/bin/bash

# Converts source code listing to PDF with syntax highlighting.
# Usage: pdf_it.sh [sourcefile]

# To install dependencies:
# sudo apt install enscript ghostscript
enscript -Epython -fCourier6 --color=1 -C -o - "$1"| ps2pdf - "$1.pdf"




