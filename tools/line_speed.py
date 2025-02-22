#! /usr/bin/env python3

import sys
import time

tl = int(time.time())
t0 = tl
i = 0
ip = 0
lps = 0
lps_mean = 0
for line in sys.stdin:
    t = int(time.time())
    if t != tl:
        tl = t
        lps = i - ip
        ip = i
        lps_mean = int(i/(t - t0))
    print(f'{lps} (average {lps_mean}) lps: {line.rstrip()}', end='\r')
    i += 1
