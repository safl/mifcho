import socket

address = ('127.0.0.1', 8000)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(address)
s.send(
"POST /mifcho/hanshake HTTP/1.1\r\n"+
"X-Mifcho-Id: uuid-of-the-requester\r\n\r\n"
)

data = s.recv(1024)
s.close()
print 'Received', repr(data)
