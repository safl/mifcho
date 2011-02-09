import threading
import socket
import time

import rfb

addr = (host, port) = ('', 5900)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(addr)
s.listen(1)

while True:
	conn, addr = s.accept()
	print 'Connected by', addr
	t = threading.Thread(target=rfb.faked_server, args=(conn,))
	t.start()
	rfb.faked_server(conn)

conn.close()
