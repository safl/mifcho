#!/usr/bin/env python
# Echo client program
import socket
import sys
import os
from OpenSSL import SSL

address = (HOST, PORT) = ('mifcho.safl.dk', 4000)

def verify_cb(conn, cert, errnum, depth, ok):
  print 'Proxy certificate: %s %s' % (cert.get_subject(), ok)
  return ok

cwd = os.curdir
# Initialize context
ctx = SSL.Context(SSL.TLSv1_METHOD)
ctx.set_verify(SSL.VERIFY_NONE, verify_cb)
ctx.use_privatekey_file(os.path.join(cwd, 'certs/m2_host.key'))
ctx.use_certificate_file(os.path.join(cwd, 'certs/m2_host.cert'))
#ctx.load_verify_locations(os.path.join(dir, 'certs/CA.cert'))

s = SSL.Connection(ctx, socket.socket(socket.AF_INET, socket.SOCK_STREAM))
s.connect(address)
s.send('Hello, world')
data = s.recv(1024)
s.close()
print 'Received', repr(data)
