# Copyright (c) Microsoft Corporation.  All rights reserved.

"""Synchronized request.
"""

import httplib
import json
import urlparse
import urllib

import pydocumentdb.documents as documents
import pydocumentdb.errors as errors
import pydocumentdb.http_constants as http_constants


def __IsReadableStream(obj):
    """Checks whether obj is a file-like readable stream.

    :Returns:
        boolean

    """
    if (hasattr(obj, 'read') and callable(getattr(obj, 'read'))):
        return True
    return False


def __RequestBodyFromData(data):
    """Gets requestion body from data.

    When `data` is dict and list into unicode string; otherwise return `data`
    without making any change.

    :Parameters:
        - `data`: str, unicode, file-like stream object, dict, list or None

    :Returns:
        str, unicode, file-like stream object, or None

    """
    data_type = type(data)
    if data_type is str or data_type is unicode or __IsReadableStream(data):
        return data
    elif data_type is dict or data_type is list:
        return json.dumps(data, separators=(',',':')).decode('utf8')
    return None


def __ConvertHeadersToDict(headers):
    """Coverts `headers` to a dict.

    :Parameters:
        - `headers`: list of (name, value) tuples.

    :Returns:
        dict

    """
    result = {}
    for (name, value) in headers:
        result[name] = value
    return result


def __InternalRequest(connection_policy, request_options, request_body):
    """Makes one http request.

    :Parameters:
        - `connection_policy`: documents.ConnectionPolicy
        - `request_options`: dict
        - `request_body`: str, unicode or Non

    :Returns:
        tuple of (result, headers), where both result and headers
        are dicts.

    """
    is_media = request_options['path'].find('media') > -1
    connection_timeout = (connection_policy.MediaRequestTimeout
                          if is_media
                          else connection_policy.RequestTimeout)
    connection =  httplib.HTTPSConnection(request_options['host'],
                                          request_options['port'],
                                          timeout=connection_timeout / 1000.0)
    connection.request(request_options['method'],
                       request_options['path'],
                       request_body,
                       request_options['headers'])
    response = connection.getresponse()
    headers = response.getheaders()

    # In case of media response, return the response to the user and the user
    # will need to handle reading the response.
    if (is_media and
        connection_policy.MediaReadMode == documents.MediaReadMode.Streamed):
        return  (response, __ConvertHeadersToDict(headers))

    data = response.read()
    if response.status >= 300:
        raise errors.HTTPFailure(response.status, data)

    result = None
    if is_media:
        result = data
    else:
        if len(data) > 0:
            try:
                result = json.loads(data)
            except:
                raise errors.JSONParseFailure(data)

    return (result, __ConvertHeadersToDict(headers))


def SynchronizedRequest(connection_policy,
                        method,
                        base_url,
                        path,
                        request_data,
                        query_params,
                        headers):
    """Performs one synchronized http request according to the parameters.

    :Parameters:
        - `connection_policy`: documents.ConnectionPolicy
        - `method`: str
        - `base_url`: str
        - `path`: str
        - `request_data`: str, unicode, file-like stream object, dict, list
          or None
        - `query_params`: dict
        - `headers`: dict

    :Returns:
        tuple of (result, headers), where both result and headers
        are dicts.

    """
    request_body = None
    if request_data:
        request_body = __RequestBodyFromData(request_data)
        if not request_body:
           raise errors.UnexpectedDataType(
               'parameter data must be a JSON object, string or' +
               ' readable stream.')

    request_options = {}
    parse_result = urlparse.urlparse(base_url)
    request_options['host'] = parse_result.hostname
    request_options['port'] = parse_result.port
    request_options['path'] = path
    request_options['method'] = method
    if query_params:
        request_options['path'] += '?' + urllib.urlencode(query_params)

    request_options['headers'] = headers
    if request_body and (type(request_body) is str or
                         type(request_body) is unicode):
        request_options['headers'][http_constants.HttpHeaders.ContentLength] = (
            len(request_body))
    elif request_body == None:
        request_options['headers'][http_constants.HttpHeaders.ContentLength] = 0
    return __InternalRequest(connection_policy, request_options, request_body)