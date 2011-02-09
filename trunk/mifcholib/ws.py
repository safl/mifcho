#!/usr/bin/env python
import logging
import hashlib
import struct
import string
import base64

_CRLF = '\r\n'
_UPGRADE_HEADER = 'Upgrade: WebSocket'+_CRLF
_CONNECTION_HEADER = 'Connection: Upgrade'+_CRLF

_FRAME_TYPES = ['','']

class MsgUtilException(Exception):
    pass

class ConnectionTerminatedException(MsgUtilException):
    pass

def key_to_num(key):
    """Extract the hidden number from a websocket handshake key."""
    
    spaces          = 0
    hidden_number   = []
    
    for k in str(key):
        if k == ' ':
            spaces += 1
        elif k in string.digits:
            hidden_number.append(k)
            
    return int(''.join(hidden_number)) / spaces
    
def keys_to_md5(key1, key2, key3):
    
    return hashlib.md5(struct.pack(
            ">II",
            key_to_num(key1),
            key_to_num(key2)
        ) + key3
    ).digest()

def close_connection(c):
    c.sendall('\xff\x00')

def send_frame(c, data):
    #c.sendall('\x00' + data.encode('utf-8') + '\xff')
    c.sendall('\x00' + base64.b64encode(data).encode('utf-8') + '\xff')

def receive_frame(c):
    # Read 1 byte.
    # mp_conn.read will block if no bytes are available.
    # Timeout is controlled by TimeOut directive of Apache.
    frame_type_str = c.recv(1)
    frame_type = ord(frame_type_str[0])
    if (frame_type & 0x80) == 0x80:
        # The payload length is specified in the frame.
        # Read and discard.
        
        length = _payload_length(c)
        _receive_bytes(c, length)
        # 5.3 3. 12. if /type/ is 0xFF and /length/ is 0, then set the
        # /client terminated/ flag and abort these steps.
        if frame_type == 0xFF and length == 0:
            #request.client_terminated = True
            logging.debug('WSCLI termination.')
            raise ConnectionTerminatedException
        else:
            logging.debug('BINARY READ, THIS SHOULD ACTUALLY NOT BE HAPPENING!')
          
    else:
        # The payload is delimited with \xff.
        bytes = _read_until(c, '\xff')
        
        # The Web Socket protocol section 4.4 specifies that invalid
        # characters must be replaced with U+fffd REPLACEMENT CHARACTER.
        message = bytes.decode('utf-8', 'ignore')
        if frame_type == 0x00:
            return message
        # Discard data of other types.


# The code is modified but based below is based on code from the pywebsocket project msgutil.py
#
# Copyright 2009, Google Inc.
# All rights reserved.
#
def _read_until(c, delim_char):
    bytes = []
    while True:
        ch = c.recv(1)
        if ch == delim_char:
            break
        bytes.append(ch)
    return ''.join(bytes)

def _receive_bytes(c, length):
    bytes = []
    while length > 0:
        new_bytes = c.recv(length)
        bytes.append(new_bytes)
        length -= len(new_bytes)
    return ''.join(bytes)

def _payload_length(c):
    length = 0
    while True:
        b_str = c.recv(1)
        b = ord(b_str[0])
        length = length * 128 + (b & 0x7f)
        if (b & 0x80) == 0:
            break
    return length

def receive_message(c):
    """Receive a Web Socket frame and return its payload as unicode string.

    Args:
        request: mod_python request.
    Raises:
        ConnectionTerminatedException: when client already terminated.
    """

    while True:
        # Read 1 byte.
        # mp_conn.read will block if no bytes are available.
        # Timeout is controlled by TimeOut directive of Apache.
        frame_type_str = c.recv(1)
        frame_type = ord(frame_type_str[0])
        if (frame_type & 0x80) == 0x80:
            # The payload length is specified in the frame.
            # Read and discard.
            length = _payload_length(c)
            _receive_bytes(c, length)
            # 5.3 3. 12. if /type/ is 0xFF and /length/ is 0, then set the
            # /client terminated/ flag and abort these steps.
            #if frame_type == 0xFF and length == 0:
            #    request.client_terminated = True
            #    raise ConnectionTerminatedException
        else:
            # The payload is delimited with \xff.
            bytes = _read_until(c, '\xff')
            # The Web Socket protocol section 4.4 specifies that invalid
            # characters must be replaced with U+fffd REPLACEMENT CHARACTER.
            message = bytes.decode('utf-8', 'replace')
            if frame_type == 0x00:
                return message
            # Discard data of other types.
