#!/usr/bin/env python
"""
Reads data from a serial device, typically Arduino, in InfluxDB's
line protocol format and forwards it into an Influx database.

Copyright 2017 Petr Pudlak

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import logging
import time
import httplib
import urllib

from retrying import retry
import serial

class Sample(object):
    """Represents a single sample that is to be sent to the database."""

    def __init__(self, line):
        """Parses a given line and stores in a new Sample.

        Raises ValueError if the line can't be parsed.
        """
        words = line.strip().split(" ")
        if len(words) == 2:
            (self.tags_line, self.values_line) = words
            self.timestamp = time.time()
        elif len(words) == 3:
            (self.tags_line, self.values_line, timestamp) = words
            self.timestamp = float(timestamp) / 1000000000.0
        else:
            raise ValueError("Unable to parse line {0!r}".format(line))

    def AddTags(self, tag_line):
        """Adds tags from 'tag_line' into 'self.tags_line'."""
        if tag_line:
            self.tags_line += ","
            self.tags_line += tag_line
        return self

    def FormatInfluxLine(self):
        """Formats the accumulated tags and values into an InfluxDB line."""
        return "{0} {1} {2:d}".format(
            self.tags_line, self.values_line, long(self.timestamp * 1000000000))

    def __str__(self):
        return '{0}(tags_line={1},values_line={2},timestamp={3})'.format(
            self.__class__.__name__, self.tags_line, self.values_line,
            self.timestamp)

    def __repr__(self):
        return "{0}({1!r})".format(self.__class__.__name__,
                                   self.FormatInfluxLine())

def SkipUntilNewLine(handle, max_line_length):
    """Skips data until a new-line character is received.

    This is needed so that the first sample is read from a complete line.
    """
    logging.debug("Skipping until the end of a new line.")
    while not handle.readline(max_line_length).endswith('\n'):
        pass

def SerialLines(args):
    """A generator that yields lines from a configured serial line."""
    # TODO: Auto reconnect / recover from errors indefinitely.
    with serial.Serial(port=args.device, baudrate=args.baud_rate,
                       timeout=args.read_timeout) as ser:
        SkipUntilNewLine(ser, args.max_line_length)
        while True:
            line = ser.readline(args.max_line_length)
            logging.debug("Received line %r", line)
            if not line.endswith('\n'):
                break
            yield line.rstrip()

def LinesToSamples(lines):
    """Converts each input line into a Sample."""
    for line in lines:
        try:
            yield Sample(line)
        except ValueError:
            logging.exception("Failed to parse Sample from '%s'", line)

def AddTags(args, samples):
    """Adds tags from command line arguments to every sample."""
    for sample in samples:
        sample.AddTags(args.tags)
        yield sample

def PostSamples(args, samples):
    """Sends a list of samples to the configured influxdb database."""
    logging.debug("Sending samples: %s", samples)
    params = urllib.urlencode({'db': args.database, 'precision': 'ns'})
    headers = {}
    body = '\n'.join([sample.FormatInfluxLine() for sample in samples]) + '\n'
    try:
        conn = httplib.HTTPConnection(args.host)
        conn.request("POST", "/write?" + params, body=body, headers=headers)
        response = conn.getresponse()
        if int(response.status) / 100 != 2:
            logging.error("Sending samples %s failed: %s, %s, %s: %s",
                          samples, response.status, response.reason, params,
                          body)
    except IOError:
        logging.exception("Failed to send samples %s", samples)

def ProcessSamples(args, queue):
    """Processes a queue, whose elements are lists of samples."""
    for sample in queue:
        PostSamples(args, [sample])

def RetryOnIOError(exception):
    """Returns True if 'exception' is an IOError."""
    return isinstance(exception, IOError)

@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def Loop(args):
    """Main loop that retries automatically on IO errors."""
    try:
        ProcessSamples(args, AddTags(args, LinesToSamples(SerialLines(args))))
    except:
        logging.exception("Error, retrying with backoff")
        raise

def main():
    """Parses the command line arguments and invokes the main loop."""
    parser = argparse.ArgumentParser(
        description="Collects values from a serial port and sends them"
                    " to InfluxDB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--device', required=True,
                        help='serial device to read from')
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

    parser.add_argument('--debug', action='store_true',
                        help='enable debug level')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    Loop(args)

if __name__ == "__main__":
    main()
