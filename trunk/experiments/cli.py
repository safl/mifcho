#!/usr/bin/env python
import threading
import socket
import struct
import pprint
import time
import sys
import os

class Control:
    
    def __init__(self):
        self.running = True
        
        self.t = []
        
        address = (HOST, PORT) = (sys.argv[1], int(sys.argv[2]))

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # aggressive
        
        s.settimeout(10)
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,    1)                
        #s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE,       2)
        #s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL,      2)
        #s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT,        5)
        
        #value   = 2
        #sec     = int(value)
        #usec    = int((value - sec) * 1e6)
        #timeval = struct.pack('ll', sec, usec)
        
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, timeval)
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, timeval)
        
        #s.settimeout(2)
        
        s.connect(address)
        
        t = threading.Thread(target=sender, args=(s, self))        
        self.t.append(t)
        t = threading.Thread(target=receiver, args=(s, self))        
        self.t.append(t)
        
        for t in self.t:
            t.start()
        
        for t in self.t:
            t.join()
            
        s.close()

def sender(s, c):
    
    while c.running:
        
        try:
            msg = str(time.time())
            print "Sendin %s" % msg
            bytes_sent = s.send(msg)
            print "Sent %d bytes." % bytes_sent
            #s.sendall(msg)
            time.sleep(6)
        except:
            c.running = False
            print "ERROR when sending %s." % msg
            pprint.pprint(sys.exc_info())            

def receiver(s, c):
    
    while c.running:
        
        try:
            data = s.recv(1024)
            if data:
                print 'Received', repr(data)
            else:
                print 'No data when trying to receive.'
            
        except:
            c.running = False
            print "ERROR when receiving,"
            pprint.pprint(sys.exc_info())
            
control = Control()
