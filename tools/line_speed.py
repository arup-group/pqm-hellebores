#! /usr/bin/env python3

import sys
import time

i = 0
ip = 0
lps = 0
tp = int(time.time())
for line in sys.stdin:
    tn = int(time.time())
    if tn != tp:
        tp = tn
        lps = i - ip
        ip = i
    print(f'{lps} lps: {line.rstrip()}', end='\r')
    i += 1
