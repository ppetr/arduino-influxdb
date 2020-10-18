#!/usr/bin/env python

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Forwards data from a serial device to an InfluxDB database."""

import argparse
import importlib
import logging
import sys
import threading
import time

from retrying import retry
import serial

import influxdb
from persistent_queue import persistent_queue
import serial_samples


def RetryOnIOError(exception):
    """Returns True if 'exception' is an IOError."""
    return isinstance(exception, IOError)

@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def ReadLoop(args, queue):
    """Reads samples and stores them in a queue. Retries on IO errors."""
    if args.serial_function:
        module, fn_name = args.serial_function.rsplit(".", 1)
        serial_fn = getattr(importlib.import_module(module), fn_name)
    try:
        logging.debug("Read loop started")
        with serial.serial_for_url(args.device, baudrate=args.baud_rate,
                                   timeout=args.read_timeout) as handle:
            if serial_fn:
                lines = serial_fn(handle)
            else:
                lines = serial_samples.SerialLines(handle, args.max_line_length)
            for line in lines:
                # Parse 'line', either with or without timestamp.
                words = line.strip().split(" ")
                if len(words) == 2:
                    (tags, values) = words
                    timestamp = int(time.time() * 1000000000)
                elif len(words) == 3:
                    (tags, values, timestamp) = words
                    float(timestamp)
                else:
                    raise ValueError("Unable to parse line {0!r}".format(line))
                tags = ",".join(t for t in (tags, args.tags) if t)
                queue.put("{0} {1} {2:d}".format(tags, values, timestamp))
    except:
        logging.exception("Error, retrying with backoff")
        raise


@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def WriteLoop(args, queue):
    """Reads samples and stores them in a queue. Retries on IO errors."""
    logging.debug("Write loop started")
    warn_on_status = frozenset(int(status) for status in args.warn_on_status)
    try:
        for influxdb_line in queue.get_blocking(tick=60):
            influxdb.PostSamples(args.database, args.host, warn_on_status,
                                 [influxdb_line])
    except:
        logging.exception("Error, retrying with backoff")
        raise

def RunAndDie(fun, *args):
    """Runs 'fn' on 'args'. If 'fn' exists, exit the whole program."""
    try:
        fun(*args)
    finally:
        sys.exit(1)

def main():
    """Parses the command line arguments and invokes the main loop."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
          Collects values from a serial port and sends them to InfluxDB.

          Note that the first received line is discarded to prevent recording
          incomplete data.

          Make sure to set READ_TIMEOUT higher than the longest expected
          period of inactivity of your device. For example, if your device
          sends data every 60 seconds, set --read-timeout=70 (or any similar
          value >60s).
        """,
        epilog="""See
          https://pyserial.readthedocs.io/en/latest/url_handlers.html#urls
          for URL types accepted by -d/--device.
          Run `python -m serial.tools.list_ports` to list of all available
          COM ports.
        """)
    parser.add_argument('-d', '--device', required=True,
                        help='serial device to read from, or a URL accepted '
                             'by serial_for_url()')
    parser.add_argument('-r', '--baud-rate', type=int, default=9600,
                        help='baud rate of the serial device')
    parser.add_argument('-t', '--read-timeout', type=int, required=True,
                        help='read timeout on the serial device; this should '
                             'be longer that the longest expected period of '
                             'inactivity of the serial device')
    parser.add_argument('--max-line-length', type=int, default=1024,
                        help='maximum line length')
    parser.add_argument('--serial-function',
                        help='custom function that reads from a serial device '
                             'passed as its argument and yields InfluxDB '
                             'lines; specified as module.functionname')

    parser.add_argument('-H', '--host', default='localhost:8086',
                        help='host and port with InfluxDB to send data to')
    parser.add_argument('-D', '--database', required=True,
                        help='database to save data to')
    parser.add_argument('-T', '--tags', default='',
                        help='additional static tags for measurements'
                             ' separated by comma, for example foo=x,bar=y')
    parser.add_argument('--warn_on_status', nargs='*', default=[400],
                        help='when one of these HTTP statuses is received from'
                             ' InfluxDB, a warning is printed and the'
                             ' datapoint is skipped; allows to continue on'
                             ' invalid datapoints')

    parser.add_argument('-q', '--queue', default=':memory:',
                        help='path for a persistent queue database file; this '
                             'file will be automatically created and managed '
                             'by the program; it ensures that no datapoints '
                             'are ever lost, even if the database is '
                             'temporarily unreachable; NOTE that at the '
                             'moment old lines are not garbage collected '
                             'from the file, so it grows forever!')
    parser.add_argument('-w', '--wal_autocheckpoint', type=int, default=10,
                        help='switches the queue SQLite database to use the '
                             'WAL mode and sets this parameter in the database')

    parser.add_argument('--debug', action='store_true',
                        help='enable debug level')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    with persistent_queue.Queue(
            args.queue, wal_autocheckpoint=args.wal_autocheckpoint) as queue:
        reader = threading.Thread(name="read", target=RunAndDie,
                                  args=(ReadLoop, args, queue))
        writer = threading.Thread(name="write", target=RunAndDie,
                                  args=(WriteLoop, args, queue))
        reader.start()
        writer.start()
        reader.join()
        writer.join()

if __name__ == "__main__":
    main()
