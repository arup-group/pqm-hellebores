#!/usr/bin/env python3

import settings
import subprocess

s = settings.Settings()
ip = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.rstrip()

print(f'Device identity: {s.identity}')
print(f'MAC address: {s.mac}')
print(f'IP address: {ip}')

