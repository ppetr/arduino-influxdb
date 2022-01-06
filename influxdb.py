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
"""Posts a series of lines in an InfluxDB database."""

import datetime
import io
import logging
import http.client
import urllib.parse
from typing import Dict, FrozenSet, NamedTuple, Optional, Sequence, Union


class InfluxdbError(IOError):
    """Thrown when posting to an InfluxDB database fails."""

    def __init__(self, params, request_body, response):
        # Read the start of the response and include it in the error.
        response_body = response.read(8192)
        super().__init__(
            "Request failed (status='{}', reason='{}', response='{}', "
            "params='{}'): {}".format(response.status, response.reason,
                                      response_body, params, request_body))


# Pylint incorrectly warns on argument indentation.
# See https://github.com/google/yapf/issues/843
# pylint: disable=C0330


def PostLines(
    database: str,
    host: str,
    lines: Sequence[bytes],
    warn_on_status: FrozenSet[int] = frozenset()) -> None:
    """Sends a list of lines to a given InfluxDB database.

    Args:
        database: Target database name.
        host: The host running the database.
        lines: String in the InfluxDB line format.
        warn_on_status: HTTP statuses that are only logged instead of throwing
            an exception.
    Raises:
        IOError when connection to the database fails.
        InfluxdbError if the database returns an error status.
    """
    logging.debug("Sending lines: %s", lines)
    params = urllib.parse.urlencode([('db', database), ('precision', 'ns')])
    conn = http.client.HTTPConnection(host)
    body: bytes = b'\n'.join(lines) + b'\n'
    conn.request("POST", "/write?" + params, body=body, headers={})
    response: http.client.HTTPResponse = conn.getresponse()
    status: int = int(response.status)
    if status // 100 != 2:
        error = InfluxdbError(params, body, response)
        if status in warn_on_status:
            logging.warning(error)
        else:
            raise error


def _Escape(special_characters: str) -> Dict[int, str]:
    """Escapes given special characters with a backslash.

    The backslash character is always escaped."""
    return str.maketrans({
        **{c: "\\" + c for c in special_characters}, "\\": "\\\\"
    })


_MEASUREMENT_ESCAPE_MAP = _Escape(", ")
_FIELD_VALUE_ESCAPE_MAP = _Escape("\"")
_OTHER_ESCAPE_MAP = _Escape(", =")

InfluxdbValue = Union[int, float, bool, str]


def _FieldValue(value: InfluxdbValue) -> str:
    """Converts a value of a sample field to InfluxDB's line format."""
    if isinstance(value, (int, float, bool)):
        return "{}".format(value)
    if isinstance(value, str):
        return "\"" + value.translate(_FIELD_VALUE_ESCAPE_MAP) + "\""
    raise TypeError("Not an InfluxDB type: {!r}".format(value))


class Sample(NamedTuple):
    """Represents a single sample to be stored in InfluxDB."""
    measurement: str
    fields: Dict[str, InfluxdbValue]
    tags: Dict[str, str] = {}
    timestamp: Optional[datetime.datetime] = None

    def ToLine(self) -> bytes:
        """Converts the sample to InfluxDB's line format."""
        # pylint: disable=C0301
        # See https://docs.influxdata.com/influxdb/cloud/reference/syntax/line-protocol/
        if not self.measurement:
            raise ValueError("Sample.measurement must not be empty")
        if not self.fields:
            raise ValueError("Sample.fields must not be empty")
        writer = io.StringIO()
        writer.write(self.measurement.translate(_MEASUREMENT_ESCAPE_MAP))
        for key, value in self.tags.items():
            writer.write(",")
            writer.write(key.translate(_OTHER_ESCAPE_MAP))
            writer.write("=")
            writer.write(value.translate(_OTHER_ESCAPE_MAP))
        for index, (key, value) in enumerate(self.fields.items()):
            writer.write("," if index else " ")
            writer.write(key.translate(_OTHER_ESCAPE_MAP))
            writer.write("=")
            writer.write(_FieldValue(value))
        if self.timestamp:
            writer.write(" ")
            # Convert to nanoseconds:
            writer.write("{:.0f}".format(self.timestamp.timestamp() * 1e9))
        return writer.getvalue().encode("UTF-8")


def PostSamples(
    database: str,
    host: str,
    samples: Sequence[Sample],
    warn_on_status: FrozenSet[int] = frozenset()
) -> None:
    """Sends a list of samples to a given InfluxDB database.

    Args:
        database: Target database name.
        host: The host running the database.
        samples: Instances of `Sample` to be stored.
        warn_on_status: HTTP statuses that are only logged instead of throwing
            an exception.
    Raises:
        IOError when connection to the database fails.
        InfluxdbError if the database returns an error status.
    """
    PostLines(database, host, warn_on_status,
              [sample.ToLine() for sample in samples])
