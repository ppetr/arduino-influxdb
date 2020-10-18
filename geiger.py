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

"""Reads data from a geiger counter."""

import logging
import time

import serial_samples


_MAX_LINE_LENGTH = 10


def OneValuePerMinute(handle):
    """Read data from a geiger counter and write them in the InfluxDB format.

    The device periodically reports moving 1-minute count window. We want to
    get values that can be correctly summed (on average). Therefore we only
    report the first value of every minute.
    """
    serial_samples.SkipUntilNewLine(handle)
    last_minute = time.gmtime(time.time()).tm_min
    while True:
        line = handle.readline(_MAX_LINE_LENGTH)
        logging.debug("Received line %r", line)
        if not line.endswith(b"\n"):
            raise serial_samples.LineOverflowError(line, _MAX_LINE_LENGTH)
        count = int(line.strip())
        minute = time.gmtime(time.time()).tm_min
        if minute != last_minute:
            last_minute = minute
            yield "geiger count_per_minute={:d}".format(count)
