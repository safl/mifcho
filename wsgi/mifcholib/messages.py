#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# Messages - Parse/Unparse of textbased http-like requests/response protocols.
#
# @author Simon Andreas Frimann Lund
#
# -- END_HEADER ---
#
import urlparse
import logging
import pprint
import re

crlf = "\r\n"
http_version  = 'HTTP/[0-9]+\.[0-9]+'
status_code   = '[1-5][0-9][0-9]'
methods       = 'OPTIONS|GET|HEAD|POST|PUT|DELETE|TRACE|CONNECT'

# Groups: method, uri, protocol-version
request_regex_pattern = '('+methods+')\s(.+)\s('+http_version+')'+crlf
request_regex = re.compile(request_regex_pattern)

# Groups: protocol-version, status-code, reason-text.
response_regex_pattern = '('+http_version+')\s('+status_code+')\s(.+)'+crlf
response_regex = re.compile(response_regex_pattern)

def get_response_line(c):
    """
    Parse status-line

        Return (version "string", status "int", reason "string")
    """

    response        = c.readline()
    response_match  = response_regex.search(response)

    version = response_match.group(1)
    status  = int(response_match.group(2))
    reason  = response_match.group(3)

    return (version, status, reason)

def get_response(c):
    """
    Parse status-line and headers of incoming response

        return (version "string", status "int", reason "string", headers "list of (header, value) tuples")
    """

    (version, status, reason) = get_response_line(c)
    headers = get_headers(c)

    return (version, status, reason, headers)

def get_request_line(c):
    """
    Parse request-line

        return (method "string", urlparse object, version "string")
    """

    rql     = None
    request = c.readline()
        
    if request:
        request_match   = request_regex.search(request)
        rql = (
            request_match.group(1),
            request_match.group(2),
            request_match.group(3)
        )
    
    return rql

#def get_request_line(c):
#    """
#    Parse request-line
#
#        return (method "string", urlparse object, version "string")
#    """
#
#    request         = c.readline()
#    logging.debug('rql: %s' % str(request))
#    request_match   = request_regex.search(request)
#    
#    return (
#        request_match.group(1),
#        request_match.group(2),
#        request_match.group(3)
#    )

def get_request(c): 
    """
    Parse a request without body

        return (method "string", urlparse object, version "string")
    """

    rql = (method, uri, version) = get_request_line(c)
    
    headers = get_headers(c)
    logging.debug('r-h: %s' % headers)

    return (method, uri, version, headers)

def send_response_line(c, code, message=None, version='HTTP/1.1'):

    response = "%s %d %s%s" % (version, code, message, crlf)
    c.sendall(response)

def send_response(c, code, message=None, version='HTTP/1.1', headers=[]):
    """
    Send response-line and response-headers.
    The response-body is sent "manually" on c.

    e.g. send_reponse(200, 'OK', 'HTTP/1.1') => "HTTP/1.1 200 OK\r\n"
    """

    send_response_line(c, code, message, version)
    send_headers(c, headers)

def send_request_line(c, type="GET", url='/', version='HTTP/1.1', address=('localhost', 8080)):

    request = '%s %s %s%s' % (type, url, version, crlf)
    request = request + 'Host: %s:%d%s' % (address[0], address[1], crlf)

    c.sendall(request)

def send_request(c, type="GET", url='/', version='HTTP/1.1', address=('localhost', 8080), headers=[]):
    """
    Sends the request-line of a request and the obligatory host header

    e.g. send_request(c, 'GET', '/', 'HTTP/1.1', ('localhost', 8080))
    """

    send_request_line(c, type, url, version, address)
    send_headers(c, headers)

def get_headers(c):
    """
    Parse headers from incoming request/response

        return dict header => value, eg. 'Content-Length' : '430'
    """

    # Parse headers
    headers = []
    line = c.readline()
    while line != crlf:

        (header, value) = line.split(':', 1)
        headers.append((header, value.strip()))

        line = c.readline()

    return headers

def send_headers(c, headers=[]):

    for h in headers:
        send_header(c, h[0], h[1])
    end_headers(c)

def send_header(c, keyword, value):
    """
    Send header::

        send_header('Content-Length', 340) => "Content-Length: 340\r\n"
    """

    header = "%s: %s%s" % (keyword, str(value), crlf)
    c.sendall(header)

def end_headers(c):
    """
    Sends the carriage-return + line-feed to indicate end of headers.

    Any send_request or send_response must be eventually followed by end_headers()
    """
    c.sendall(crlf)

def path_to_fun(path):

    model_fun_args = path.split('/')

    # A path will be split like: " /agent/{id} => ('', 'agent', '{id}') "
    model = model_fun_args[1]
    fun   = model_fun_args[2]
    args  = model_fun_args[3:]

    return (model, fun, args)

#
# MICHO messages
#
def tunneling_request(tunnel_id, address):
    return '/peer/tunnel/%s/%s/%d' % (tunnel_id, address[0], address[1])
