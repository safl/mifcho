#!/usr/bin/env python
from OpenSSL import SSL
import socket
import os

def _verify_cb(conn, cert, errnum, depth, ok):          # Helper for tls
    return ok

ctx = SSL.Context(SSL.TLSv1_METHOD)                     # Initialize context
ctx.set_verify(SSL.VERIFY_NONE, _verify_cb)
ctx.use_privatekey_file('certs'+os.sep+'m1.key')
ctx.use_certificate_file('certs'+os.sep+'m1.crt')

bindsocket = SSL.Connection(ctx, socket.socket(socket.AF_INET, socket.SOCK_STREAM))

bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
bindsocket.bind(('', 10022))
bindsocket.listen(5)

while True:
    sock, src_addr = bindsocket.accept()
    
    while True:
        
        data = sock.recv(1024)
        if not data:
            break
        print data