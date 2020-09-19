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

"""Reads and parses lines from a serial device.

Typically from an Arduino. Lines are expected to follow the InfluxDB's line
protocol format (with the difference that the timestamp is allowed to be
missing).
"""

import logging
import time
import serial


class Sample(object):
    """Represents a single sample in the InfluxDB format."""

    def __init__(self, line):
        """Parses a given line and stores in a new Sample.

        If timestamp is missing, the current time is used.

        Args:
          line: String to be parsed.
        Raises:
          ValueError if the line can't be parsed.
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
            self.tags_line, self.values_line, int(self.timestamp * 1000000000))

    def __str__(self):
        return '{0}(tags_line={1},values_line={2},timestamp={3})'.format(
            self.__class__.__name__, self.tags_line, self.values_line,
            self.timestamp)

    def __repr__(self):
        return "{0}({1!r})".format(self.__class__.__name__,
                                   self.FormatInfluxLine())

def SkipUntilNewLine(handle):
    """Skips data until a new-line character is received.

    This is needed so that the first sample is read from a complete line.
    """
    logging.debug("Skipping until the end of a new line.")
    while not handle.readline(4096).endswith('\n'):
        pass

class LineOverflowError(IOError):
    """Thrown when a line longer than a given limit is received."""
    def __init__(self, line, max_line_length):
        if not line:
            message = "Timeout on device inactivity, no data received"
        elif len(line) >= max_line_length:
            message = "Read line overflow: {0!r}".format(line)
        else:
            message = "Read timeout; received incomplete line: {0!r}".format(
                line)
        super(LineOverflowError, self).__init__(message)

def SerialLines(device_url, baud_rate, read_timeout, max_line_length):
    """A generator that yields lines from a configured serial line.

    Will never exit normally, only with an exception when there is an error
    in the serial communication.
    """
    with serial.serial_for_url(device_url, baudrate=baud_rate,
                               timeout=read_timeout) as handle:
        SkipUntilNewLine(handle)
        while True:
            line = handle.readline(max_line_length)
            logging.debug("Received line %r", line)
            if not line.endswith('\n'):
                raise LineOverflowError(line, max_line_length)
            try:
                yield Sample(line.rstrip())
            except ValueError:
                logging.exception("Failed to parse Sample from '%s'", line)
