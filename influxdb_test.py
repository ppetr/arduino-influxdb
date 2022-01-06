# -*- coding: UTF-8 -*-

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
"""Test posting of data to an InfluxDB database."""

# pylint: disable=missing-docstring,invalid-name

import collections
import datetime
import unittest
from unittest import mock

import influxdb


class TestInfluxDB(unittest.TestCase):

    @staticmethod
    @mock.patch('http.client.HTTPConnection')
    def test_post_successfully(mock_conn):
        mock_conn.return_value.getresponse.return_value = mock.Mock(
            **{"status": "200"})
        influxdb.PostLines("Database", "host", [b"test_line"])
        mock_conn.assert_called_with("host")
        mock_conn().request.assert_called_with(
            "POST",
            "/write?db=database&precision=ns",
            body=b"test_line\n",
            headers={})

    @mock.patch('http.client.HTTPConnection')
    def test_post_error(self, mock_conn):
        mock_conn().getresponse.return_value = mock.Mock(**{"status": "500"})
        mock_conn().getresponse.return_value.read.return_value = \
            "{explanation:'foo'}"
        with self.assertRaisesRegex(influxdb.InfluxdbError,
                                    "{explanation:'foo'}"):
            influxdb.PostLines("database",
                               "host", [b"test_line"],
                               warn_on_status=[400])

    @mock.patch('http.client.HTTPConnection')
    def test_post_warning(self, mock_conn):
        mock_conn().getresponse.return_value = mock.Mock(**{"status": "400"})
        mock_conn().getresponse.return_value.read.return_value = \
            "{explanation:'foo'}"
        with self.assertLogs(level='WARN') as log:
            influxdb.PostLines("database",
                               "host", [b"test_line"],
                               warn_on_status=[400])
        self.assertRegex(log.output[0], "{explanation:'foo'}")

    def test_to_line_basic(self):
        sample = influxdb.Sample(measurement="my measurement",
                                 fields={"key": "string value"})
        self.assertEqual(sample.ToLine(),
                         b"my\\ measurement key=\"string value\"")
        sample = influxdb.Sample(measurement="measurement",
                                 fields=collections.OrderedDict({
                                     "bool": True,
                                     "int": 42,
                                     "float": 3.14
                                 }))
        self.assertEqual(sample.ToLine(),
                         b"measurement bool=True,int=42,float=3.14")
        sample = influxdb.Sample(measurement="measurement",
                                 tags=collections.OrderedDict({
                                     "tag1": "1",
                                     "tag2": "2"
                                 }),
                                 fields={"int": 42})
        self.assertEqual(sample.ToLine(), b"measurement,tag1=1,tag2=2 int=42")

    def test_to_line_timestamp(self):
        sample = influxdb.Sample(measurement="measurement",
                                 fields={"int": 42},
                                 timestamp=datetime.datetime.fromisoformat(
                                     "1970-01-01T01:00:00+00:00"))
        self.assertEqual(sample.ToLine(), b"measurement int=42 3600000000000")

    def test_to_line_utf8(self):
        sample = influxdb.Sample(measurement="measurement",
                                 tags={"tag": "🍭"},
                                 fields={"field": "Launch 🚀"})
        self.assertEqual(sample.ToLine(),
                         "measurement,tag=🍭 field=\"Launch 🚀\"".encode("UTF-8"))

    def test_to_line_missing_fields(self):
        with self.assertRaises(ValueError):
            influxdb.Sample(measurement="", fields={"key": "value"}).ToLine()
        with self.assertRaises(ValueError):
            influxdb.Sample(measurement="measurement", fields={}).ToLine()


if __name__ == '__main__':
    unittest.main()
