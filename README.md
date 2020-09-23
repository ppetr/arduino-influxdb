# Script to collect data from Arduino into InfluxDB

_Disclaimer: This is not an official Google product._

[![Build Status](https://travis-ci.com/ppetr/arduino-influxdb.svg?branch=master)](https://travis-ci.com/ppetr/arduino-influxdb)

## Purpose

This script reads data from a serial device, typically Arduino, in InfluxDB's
[line protocol](https://docs.influxdata.com/influxdb/v1.2/write_protocols/line_protocol_tutorial/)
format and forwards it into an Influx database.

## Usage

Write an Arduino program that sends data in InfluxDB's format on the serial
line without timestamps (which are generally unavailable on Arduino). For
example:

    plant,pin=A15 moisture=140,temperature=27.4,humidity=67.3

Prepare an Influx database where you want to store the data. Then run:

    python3 collect.py -d /dev/ttyUSB0 -H localhost:8086 -D plants -T location=foo

This reads data from `/dev/ttyUSB0` and writes them to the database `plants`
running on `localhost:8086` (the default value for `-H`). It also adds tag
`location=foo` to each sample, in addition to the above `pin=A15` sent by
Arduino.

For detailed information about command line arguments run

    python3 collect.py --help

### Running with Telegraf

If the Influx database runs on a different machine, it might be helpful to run
[Telegraf](https://docs.influxdata.com/telegraf/v1.2/) locally. This has the
advantage that Telegraf can buffer messages in the case the connection to the
database fails, and also allows to collect monitoring data about the machine,
which is generally a good thing for long-running systems.

## Requirements

- **Python 3.6+**
- Python libraries:
  - [retrying](https://pypi.python.org/pypi/retrying)
  - [pyserial](https://pypi.python.org/pypi/pyserial)
  - [persistent-queue-log](https://github.com/ppetr/persistent-queue-log) -
    included as a
    [submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules); just
    clone this repository with `--recurse-submodules`.

On Debian the first two can be installed using

    sudo apt-get install python3-retrying python3-serial

## Contributions and future plans

Contributions welcome, please see [Code of Conduct](docs/code-of-conduct.md)
and [Contributing](docs/contributing.md). Currently I'd like to add:

- Thorough, proper testing.
- Packaging for Debian/Ubuntu.
- An option for running the script as a proper Linux daemon.
