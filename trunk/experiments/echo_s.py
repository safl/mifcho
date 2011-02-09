#!/usr/bin/env python
# Echo server program
import socket
import sys
import os
from OpenSSL import SSL

address = (HOST, PORT) = ('mifcho.safl.dk', 4000)
s = None

def verify_cb(conn, cert, errnum, depth, ok):
  print 'Certificate: %s %s' % (cert.get_subject(), ok)
  return ok

cwd = os.curdir

# Initialize context
ctx = SSL.Context(SSL.TLSv1_METHOD)
ctx.set_verify(SSL.VERIFY_NONE, verify_cb)
ctx.use_privatekey_file(os.path.join(cwd, 'certs/m1_host.key'))
ctx.use_certificate_file(os.path.join(cwd, 'certs/m1_host.cert'))
#ctx.load_verify_locations(os.path.join(dir, 'certs/CA.cert'))

# Connect   
s = SSL.Connection(ctx, socket.socket(socket.AF_INET, socket.SOCK_STREAM))
s.bind(address)
s.listen(5)
while True:
  conn, addr = s.accept()
  print 'Connected by', addr
  while 1:
    try:
      data = conn.recv(1024)
      if not data: break
      conn.send(data)
    except:
      print "some error occured"
      break
conn.close()