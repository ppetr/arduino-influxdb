# Copyright 2017 Petr Pudlak
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

import logging
import httplib
import urllib


class InfluxdbError(IOError):
    """Thrown when posting to an InfluxDB database fails."""
    def __init__(self, params, body, response):
        super(InfluxdbError, self).__init__(
            "Request failed (status='{}', reason='{}', params='{}'): {}".format(
            response.status, response.reason, params, body))

def PostSamples(database, host, lines):
    """Sends a list of lines to a given InfluxDB database.
    
    Args:
        database: Target database name.
        host: The host running the database.
        lines: String in the InfluxDB line format.
    Raises:
        IOError when connection to the database fails.
    """
    logging.debug("Sending lines: %s", lines)
    params = urllib.urlencode({'db': database, 'precision': 'ns'})
    conn = httplib.HTTPConnection(host)
    body = '\n'.join(lines) + '\n'
    conn.request("POST", "/write?" + params, body=body, headers={})
    response = conn.getresponse()
    if int(response.status) / 100 != 2:
        raise InfluxdbError(params, body, response)
