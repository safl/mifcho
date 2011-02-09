#!/usr/bin/env python
# Echo server program
import socket
import struct
import sys
import os

address = (HOST, PORT) = ('', 4000)
s = None

# Connect
value   = 1
sec     = int(value)
usec    = int((value - sec) * 1e6)
timeval = struct.pack('ll', sec, usec)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, timeval)
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, timeval)

s.bind(address)
s.listen(5)
while True:
    conn, addr = s.accept()
    print 'Connected by', addr
    
    while True:
        try:
            data = conn.recv(1024)
            print data
            if not data: break
            conn.send(data)
        except:
            print "some error occured"
            break
conn.close()