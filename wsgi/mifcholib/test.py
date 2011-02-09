import logging
import socket
import time
import sys
import rfb

host = 'localhost'
port = 8003
address = (host, port)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(address)

rfb.faked_client(s)