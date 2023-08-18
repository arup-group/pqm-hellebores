#! /usr/bin/env python3

import sys
import time

tl = int(time.time())
i = 0
lps = 0
for line in sys.stdin:
    t = int(time.time())
    if t != tl:
        tl = t
        lps = i
        i = 0
    print(f'{lps} lps: {line.rstrip()}', end='\r')
    i = i + 1



