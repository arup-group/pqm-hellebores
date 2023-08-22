#!/usr/bin/env python3

import settings
import subprocess

s = settings.Settings()
ips = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.rstrip().split()

print(f'Device identity: {s.identity}')
print(f'MAC address: {s.mac}')
for ip in ips :
    print(f'IP address: {ip}')

