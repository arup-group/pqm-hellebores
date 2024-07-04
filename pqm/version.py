#!/usr/bin/env python3

import hashlib
import sys
import os
import argparse
import subprocess
import re
from settings import Settings

# location of files relative to the root directory of the project tree
PROGRAM_DIR = './pqm'
PICO_DIR = './pico'
RUN_DIR = './run'
VERSION_FILE = 'VERSION'

class Version:

    def __init__(self):
        self.st = Settings()

    def about(self):
        list_of_files = self.list_files([PROGRAM_DIR, PICO_DIR, RUN_DIR])
        ver =      f'Version              : {self.get_version()}'
        md5 =      f'SHA256 checksum      : {self.sha256(list_of_files)}'
        git_h =    f'Git commit id        : {self.git_head()}'
        tf =       f'Temporary files      : {self.get_temp_dir()}'
        identity = f'Identity             : {self.st.identity}'
        offsets =  f'Calibration offsets  : {self.st.cal_offsets}'
        gains =    f'Calibration gains    : {self.st.cal_gains}'
        about = '\n'.join( [ver, md5, git_h, tf, identity, offsets, gains] )
        return about

    def resolve_path(self, path, file):
        # we resolve paths relative to the base directory of the project, using the known location
        # of this program file as a starting point
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path, file)
        resolved_path = os.path.abspath(file_path)
        return resolved_path

    def readfiles(self, list_of_files):
        text = ''
        for file in list_of_files:
            with open(file, 'r') as f:
                try:
                    text = text + f.read()
                except IOError:
                    print(f"version.py: Version.readfiles() couldn't read file {file}",
                            file=sys.stderr)
        return text

    def sha256(self, list_of_files):
        contents = self.readfiles(list_of_files)
        sha256 = hashlib.sha256(contents.encode()).hexdigest()
        return sha256

    def list_files(self, paths):
        file_names = [] 
        for path in paths:
            resolved_path = self.resolve_path(path, '')
            # only accept files, not directories, that do not start with '.'
            file_names.extend([ f for f in os.listdir(resolved_path) if os.path.isfile(f)
                                             and f[0] != '.'])
        return file_names

    def get_version(self):
        version_string = ''
        try:
            version_file = self.resolve_path('.', VERSION_FILE)
            with open(version_file, 'r') as f:
                version_string = f.read().strip() 
        except IOError:
            print(f"version.py: Version.get_version() couldn't read file {f}",
                    file=sys.stderr)
        return version_string

    def set_version(self, new_version):
        if new_version != '':
            try:
                version_file = self.resolve_path('.', VERSION_FILE)
                with open(version_file, 'w') as f:
                    f.write(new_version)
                    f.close()
            except IOError:
                print(f"version.py: Version.set_version() couldn't write file {f}",
                       file=sys.stderr)

    def increment_sub_version(self):
        current_version = self.get_version()
        # major.minor.sub_codename
        match_pattern = r'(\d+)\.(\d+)\.(\d+)(.*)'
        try:
            m = re.search(match_pattern, current_version)
            (major, minor, sub, codename) = m.groups()
            sub = int(sub)
            if sub < 999:
                sub = sub + 1
                self.set_version(f"{major}.{minor}.{sub:003d}{codename}")
        except ValueError:
            print(f"version.py: Version.increment_sub_version() couldn't change version {current_version}",
                    file=sys.stderr)
 
    def git_head(self):
        git_head = ''
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, check=True)
            git_head = result.stdout.decode('utf-8').strip()
        except FileNotFoundError:
            print(f"version.py: Version.git_head() failed to run git command",
                    file=sys.stderr)
        return git_head

    def get_temp_dir(self):
        temp_dir = self.resolve_path(os.getenv('TEMP', '.'), '.')
        return temp_dir 


def get_command_args():
    cmd_parser = argparse.ArgumentParser(description='Maintain device instance and software version information.')
    cmd_parser.add_argument('--increment_sub_version', action='store_true', \
        help='Increment the sub-version number of the current VERSION string.')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return (program_name, args)

def main():
    program_name, args = get_command_args()
    v = Version()
    if args.increment_sub_version:
        v.increment_sub_version()
        print(v.get_version())
    else:
        print(v.about())


if __name__ == '__main__':
    main()




