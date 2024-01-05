#!/usr/bin/env python3

import subprocess
# local
from settings import Settings

s = Settings()
ips = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.rstrip().split()

print(f'Device identity: {s.identity}')
for ip in ips :
    print(f'IP address: {ip}')

