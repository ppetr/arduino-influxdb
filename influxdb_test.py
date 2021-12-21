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

import unittest
from unittest import mock

import influxdb


class TestInfluxDB(unittest.TestCase):

    @staticmethod
    @mock.patch('http.client.HTTPConnection')
    def test_post_successfully(mock_conn):
        mock_conn.return_value.getresponse.return_value = mock.Mock(
            **{"status": "200"})
        influxdb.PostSamples("database", "host", [], ["test_line"])
        mock_conn.assert_called_with("host")
        mock_conn().request.assert_called_with(
            "POST",
            "/write?db=database&precision=ns",
            body="test_line\n",
            headers={})

    @mock.patch('http.client.HTTPConnection')
    def test_post_error(self, mock_conn):
        mock_conn().getresponse.return_value = mock.Mock(**{"status": "500"})
        mock_conn().getresponse.return_value.read.return_value = \
            "{explanation:'foo'}"
        with self.assertRaisesRegex(influxdb.InfluxdbError,
                                    "{explanation:'foo'}"):
            influxdb.PostSamples("database", "host", [400], ["test_line"])

    @mock.patch('http.client.HTTPConnection')
    def test_post_warning(self, mock_conn):
        mock_conn().getresponse.return_value = mock.Mock(**{"status": "400"})
        mock_conn().getresponse.return_value.read.return_value = \
            "{explanation:'foo'}"
        with self.assertLogs(level='WARN') as log:
            influxdb.PostSamples("database", "host", [400], ["test_line"])
        self.assertRegex(log.output[0], "{explanation:'foo'}")


if __name__ == '__main__':
    unittest.main()
