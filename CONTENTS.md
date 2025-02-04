# Outline description of files


## root /

| +---------------------------- | +---------------------------- |
| Filename                      | Description                   |
| +---------------------------- | +---------------------------- |
| `README.md`                   | Overall description of project, with installation and setup instructions. |
| `notes`                       | Additional notes made during development, that may not be relevant. |
| `README.md`                   | Overall description of project, with installation and setup instructions. |
| `CONTENTS.md`                 | Outline description of files (this file). |
| `LICENSE`                     | The MIT license that makes this software open source. |
| `VERSION`                     | Version string used to help identify which version is running. Minor version numbers are incremented using a git hook when a commit is made. |
| `requirements.txt`            | Used with python pip to install libraries that the software needs to run. |
| +---------------------------- | +---------------------------- |

`README.md`

Overall description of project, with installation and setup instructions.

`notes`

Additional notes made during development, that may not be relevant.

`CONTENTS.md`

Outline description of files (this file).

`LICENSE`

The MIT license that makes this software open source.

`VERSION`

Version string used to help identify which version is running. Minor version numbers are incremented using a git hook when a commit is made.

`requirements.txt`

Used with python pip to install libraries that the software needs to run.

`environment.yaml`

Used with conda or mamba to install libraries, as an alternative to python pip.

`.gitignore`

Tells git to ignore certain directories or files that we do not want to accidentally add to the repository.

## .git/

Contains the configuration, staging and commit history for version control

## configuration/

`calibrations.json`

Contains the calibration constants for each meter.

`identity`

Contains the name for a specific meter. This allows the software to apply the correct calibration constants.

`settings.json`

Contains settings and some fixed constants for the meter. A copy of this file is saved in RAMdisk when the meter is running, and is updated dynamically.

## pico/

## pqm/

## run/

## tools/
