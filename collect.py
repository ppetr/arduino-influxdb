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
"""Forwards data from a serial device to an InflixDB database."""

import argparse
import logging
import sys
import threading

from retrying import retry

import influxdb
import persistent_queue
import serial_samples


def RetryOnIOError(exception):
    """Returns True if 'exception' is an IOError."""
    return isinstance(exception, IOError)

@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def ReadLoop(args, queue):
    """Reads samples and stores them in a queue. Retries on IO errors."""
    try:
        logging.debug("Read loop started")
        for sample in serial_samples.SerialLines(args.device, args.baud_rate,
                                                 args.read_timeout,
                                                 args.max_line_length):
            sample.AddTags(args.tags)
            queue.put(sample.FormatInfluxLine())
    except:
        logging.exception("Error, retrying with backoff")
        raise


@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def WriteLoop(args, queue):
    """Reads samples and stores them in a queue. Retries on IO errors."""
    logging.debug("Write loop started")
    try:
        for influxdb_line in queue.get_blocking(tick=60):
            influxdb.PostSamples(args.database, args.host, [influxdb_line])
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
    parser.add_argument('--read-timeout', type=int, default=60,
                        help='read timeout on the serial device')
    parser.add_argument('--max-line-length', type=int, default=1024,
                        help='maximum line length')

    parser.add_argument('-H', '--host', default='localhost:8086',
                        help='host and port with InfluxDB to send data to')
    parser.add_argument('-D', '--database', required=True,
                        help='database to save data to')
    parser.add_argument('-T', '--tags', default='',
                        help='additional static tags for measurements'
                             ' separated by comma, for example foo=x,bar=y')

    parser.add_argument('-q', '--queue', default=':memory:',
                        help='path for a persistent queue database file')
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
