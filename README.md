# Purpose

This script reads data from a serial device, typically Arduino, in InfluxDB's
[line protocol](https://docs.influxdata.com/influxdb/v1.2/write_protocols/line_protocol_tutorial/)
format and forwards it into an Influx database.

# Usage

Write an Arduino program that sends data in InfluxDB's format on the serial
line without timestamps (which are generally unavailable on Arduino). For
example:

    plant,pin=A15 moisture=140,temperature=27.4,humidity=67.3

Prepare an Influx database where you want to store the data. Then run:

    python collect.py -d /dev/ttyUSB0 -H localhost:8086 -D plants -T location=foo

This reads data from `/dev/ttyUSB0` and writes them to the database `plants`
running on `localhost:8086` (the default value for `-H`). It also adds tag
`location=foo` to each sample, in addition to the above `pin=A15` sent by
Arduino.

## Running with Telegraf

If the Influx database runs on a different machine, it might be helpful to run
[Telegraf](https://docs.influxdata.com/telegraf/v1.2/) locally. This has the
advantage that Telegraf can buffer messages in the case the connection to the
database fails, and also allows to collect monitoring data about the machine,
which is generally a good thing for long-running systems.

# Contributions and future plans

Welcome. Currently I'd like to add:

- Packaging for Debian/Ubuntu.
- Add an option for running the script as a proper daemon.
