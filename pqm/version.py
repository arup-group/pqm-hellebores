#!/usr/bin/env python3

import hashlib
import sys
import os
import subprocess
import re

# location of files relative to the root directory of the project tree
PROGRAM_DIR = './pqm'
PICO_DIR = './pico'
RUN_DIR = './run'
VERSION_FILE = 'VERSION'

class Version:

    def resolve_path(self, path, file):
        # we resolve paths relative to the known location of this program file
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path, file)
        resolved_path = os.path.abspath(file_path)
        return resolved_path

    def readfiles(self, list_of_files):
        text = ''
        for file in list_of_files:
            with open(file, 'r') as f:
                try:
                    text = text + f.read()
                except:
                    print(f"version.py: Version.readfiles() couldn't read file {file}",
                            file=sys.stderr)
        return text

    def md5(self, list_of_files):
        contents = self.readfiles(list_of_files)
        md5 = hashlib.md5(contents.encode()).hexdigest()
        return md5

    def list_files(self, paths):
        file_names = [] 
        for path in paths:
            resolved_path = self.resolve_path(path, '')
            file_names.extend([ f for f in os.listdir(resolved_path) if os.path.isfile(f) ])
        return file_names

    def get_version(self):
        version_string = ''
        try:
            version_file = self.resolve_path('.', VERSION_FILE)
            with open(version_file, 'r') as f:
                version_string = f.read().strip() 
        except:
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
            except:
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
        except:
            print(f"version.py: Version.increment_sub_version() couldn't change version {current_version}",
                    file=sys.stderr)
 
    def git_head(self):
        git_head = ''
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, check=True)
            git_head = result.stdout.decode('utf-8').strip()
        except:
            print(f"version.py: Version.git_head() failed to run git command",
                    file=sys.stderr)
        return git_head

    def get_temp_dir(self):
        temp_dir = ''
        try:
            temp_from_env = os.getenv('TEMP')
            if temp_from_env == None:
                temp_dir = ''
            else:
                temp_dir = temp_from_env
        except:
            print(f"version.py: Version.get_temp_dir() failed to succeed",
                    file=sys.stderr)
        return temp_dir 


def main():
    v = Version()
    list_of_files = v.list_files([PROGRAM_DIR, PICO_DIR, RUN_DIR])
    print(f"Temporary files      : {v.get_temp_dir()}")
    print(f"Version              : {v.get_version()}")
    print(f"MD5 checksum         : {v.md5(list_of_files)}")
    print(f"Git HEAD             : {v.git_head()}")



if __name__ == '__main__':
    main()




