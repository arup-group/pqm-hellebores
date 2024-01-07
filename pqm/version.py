#!/usr/bin/env python3

import hashlib
import sys

class Version:

    def readfiles(self, list_of_files):
        text = ''
        for file in list_of_files:
            with open(file, 'r') as f:
                try:
                    text = text + f.read()
                except:
                    print(f"version.py: Version.readfiles() Couldn't read file {file}",
                          file=sys.stderr)
        return text

    def md5(self, list_of_files):
        contents = self.readfiles(list_of_files)
        md5 = hashlib.md5(contents.encode()).hexdigest()
        return md5


def main():
    v = Version()
    list_of_files = ['../run/go.sh', 'rain_bucket.py', 'reader.py', 'scaler.py',
                     'trigger.py', 'mapper.py', 'hellebores.py', 'hellebores_constants.py',
                     'hellebores_waveform.py', 'hellebores_multimeter.py',
                     '../pico/main.py']
    print(f"MD5:          {v.md5(list_of_files)}")



if __name__ == '__main__':
    main()




