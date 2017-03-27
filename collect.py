#!/usr/bin/env python

import logging
from retrying import retry
import serial
import time

import httplib
import urllib

SERIAL = '/dev/ttyACM0'
BAUDRATE = 9600
READ_TIMEOUT = 60
MAX_LINE_LENGTH = 1024

INFLUX_HOST = 'localhost:8186'
INFLUX_DB = 'plants'
INFLUX_TAGS = {'location': 'luzna', 'board': 'raspberrypi'}

_INFLUX_TAGS_LINE = ",".join(map(lambda (k, v): str(k) + "=" + str(v),
                             INFLUX_TAGS.items()))

class Sample(object):
    """Represents a single sample that is to be sent to the database."""

    def __init__(self, line):
        """Parses a given line and stores in a new Sample.

        Raises ValueError if the line can't be parsed.
        """
        self.timestamp = time.time()
        (self.tags_line, self.values_line) = line.strip().split(" ")
        if _INFLUX_TAGS_LINE:
            self.tags_line += ","
            self.tags_line += _INFLUX_TAGS_LINE

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

def SkipUntilNewLine(f):
    """Skips data until a new-line character is received.
    
    This is needed so that the first sample is read from a complete line.
    """
    logging.debug("Skipping until the end of a new line.")
    while not f.readline(MAX_LINE_LENGTH).endswith('\n'):
        pass

def SerialLines():
    """A generator that yields lines from a configured serial line."""
    # TODO: Auto reconnect / recover from errors indefinitely.
    with serial.Serial(port=SERIAL, baudrate=BAUDRATE, timeout=READ_TIMEOUT) as ser:
        SkipUntilNewLine(ser)
        while True:
            line = ser.readline(MAX_LINE_LENGTH)
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

def PostSamples(samples):
    """Sends a list of samples to the configured influxdb database."""
    logging.debug("Sending samples: %s", samples)
    params = urllib.urlencode({'db': INFLUX_DB, 'precision': 'ns'})
    headers = {}
    body = '\n'.join([sample.FormatInfluxLine() for sample in samples]) + '\n'
    try:
        conn = httplib.HTTPConnection(INFLUX_HOST)
        conn.request("POST", "/write?" + params, body=body, headers=headers)
        response = conn.getresponse()
        if int(response.status) / 100 != 2:
            logging.error("Sending samples %s failed: %s, %s, %s: %s",
                          samples, response.status, response.reason, params,
                          body)
    except IOError:
        logging.exception("Failed to send samples %s", samples)

def ProcessSamples(queue):
    """Processes a queue, whose elements are lists of samples."""
    for sample in queue:
        PostSamples([sample])

@retry(wait_exponential_multiplier=1000, wait_exponential_max=60000)
def main():
    try:
        ProcessSamples(LinesToSamples(SerialLines()))
    except:
        logging.exception("Error, retrying with backoff")
        raise

if __name__ == "__main__":
    main()
