#!/usr/bin/env python
import socket
import ssl
import os

bindsocket = socket.socket()
bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
bindsocket.bind(('127.0.0.1', 10022))
bindsocket.listen(5)

while True:
    newsocket, fromaddr = bindsocket.accept()
    connstream = ssl.wrap_socket(
        newsocket,
        server_side = True,
        cert_reqs   = ssl.CERT_NONE,
        ca_certs    = 'certs'+os.sep+'m3.crt',
        certfile    = 'certs'+os.sep+'m3.crt',
        keyfile     = 'certs'+os.sep+'m3.key',
        ssl_version = ssl.PROTOCOL_TLSv1
    )
    
    while True:
        
        data = connstream.read()
        if not data:
            break
        print data
        
    connstream.close()