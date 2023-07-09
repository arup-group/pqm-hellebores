#!/usr/bin/env python3

import settings

s = settings.Settings()

mac = s.get_mac_address()
identity = s.get_identity()

print(f'Power quality monitor identity is: {identity}')
print(f'MAC address: {mac}')


