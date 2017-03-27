#!/usr/bin/env python

import argparse
import logging
from retrying import retry
import serial
import time

import httplib
import urllib

class Sample(object):
    """Represents a single sample that is to be sent to the database."""

    def __init__(self, line):
        """Parses a given line and stores in a new Sample.

        Raises ValueError if the line can't be parsed.
        """
        self.timestamp = time.time()
        (self.tags_line, self.values_line) = line.strip().split(" ")

    def AddTags(self, tag_line):
        if tag_line:
            self.tags_line += ","
            self.tags_line += tag_line
        return self

    def FormatInfluxLine(self):
        return "{0} {1} {2:d}".format(
                self.tags_line, self.values_line, long(self.timestamp * 1000000000))

    def __str__(self):
        return '{0}(tags_line={1},values_line={2},timestamp={3})'.format(
                self.__class__.__name__, self.tags_line, self.values_line,
                self.timestamp)

    def __repr__(self):
        return "{0}({1!r})".format(self.__class__.__name__,
                                   self.FormatInfluxLine())

def SkipUntilNewLine(f, max_line_length):
    """Skips data until a new-line character is received.
    
    This is needed so that the first sample is read from a complete line.
    """
    logging.debug("Skipping until the end of a new line.")
    while not f.readline(max_line_length).endswith('\n'):
        pass

def SerialLines(args):
    """A generator that yields lines from a configured serial line."""
    # TODO: Auto reconnect / recover from errors indefinitely.
    with serial.Serial(port=args.device, baudrate=args.baud_rate,
                       timeout=args.read_timeout) as ser:
        SkipUntilNewLine(ser, args.max_line_length)
        while True:
            line = ser.readline(args.max_line_length)
            logging.debug("Received line %s", repr(line))
            if not line.endswith('\n'):
                break
            yield line.rstrip()

def LinesToSamples(lines):
    """Converts each input line into a Sample."""
    for line in lines:
        try:
            yield Sample(line)
        except ValueError:
            logging.exception("Failed to parse Sample from '%s'", sample)

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
    return isinstance(exception, IOError)

@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000,
       retry_on_exception=RetryOnIOError)
def loop(args):
    """Main loop that retries automatically on IO errors."""
    try:
        ProcessSamples(args, AddTags(args, LinesToSamples(SerialLines(args))))
    except:
        logging.exception("Error, retrying with backoff")
        raise

def main():
    parser = argparse.ArgumentParser(
            description="Collects values from a serial port and sends them"
                        " to InfluxDB")
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
    loop(args)

if __name__ == "__main__":
    main()
