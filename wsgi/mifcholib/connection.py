#!/usr/bin/env python
import logging
import socket
import struct
import ssl

class Connection:
    """Wrapper around socket and OpenSSL."""

    def __init__(self, s, use_tls=False):
        
        self.s          = s
        self.use_tls    = use_tls        
        self.buffer_size = 4096
        
        self.callback = None

    @classmethod
    def fromaddress(cls, address, use_tls=False, aggressive=True):
        """Constructor-factory based on address = (host, port)."""
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if aggressive:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,    1)                
            s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE,       1)
            s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL,      1)
            s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT,        1)
        
        if use_tls:
            sock = ssl.wrap_socket(
                s,
                cert_reqs   = ssl.CERT_NONE,
                ssl_version = ssl.PROTOCOL_TLSv1
            )
        else:
            sock = s
        
        sock.connect(address)      # Connect

        return cls(sock, use_tls)

    def readline(self, term='\r\n'):
        """Read until end-of-line is reached or 'term' is read."""

        line = ''
        c = ''

        while not line.endswith(term):

            c = self.s.recv(1)

            if c:
                line += c
            else:
                break

        return line

    def read_bytes(self, bytes_to_read):
        """Read 'bytes_to_read' amount of bytes."""

        data = ''
        bytes_read  = 0

        while bytes_read < bytes_to_read:
            chunk = self.s.recv(bytes_to_read-bytes_read)

            if not chunk:
                break

            data += chunk
            bytes_read += len(chunk)

        return data

    def send(self, bytes):
        """Send 'bytes'."""
        return self.s.send(bytes)

    def recv(self, length):
        """Receive 'length' bytes."""
        return self.s.recv(length)

    def recv_into(self, buffer, nbytes=0, flags=0):
        return self.s.recv_into(buffer, nbytes, flags)

    def sendall(self, chunk):
        self.s.sendall(chunk)

    def settimeout(self, value):
        self.s.settimeout(value)

    def setblocking(self, flag):
        self.s.setblocking(flag)

    def fileno(self):
        return self.s.fileno()

    def shutdown(self):

        if self.callback:
            self.callback.set()

        if (self.use_tls):
            self.s.shutdown()
        else:
            self.s.shutdown(socket.SHUT_RDWR)

    def close(self):
        self.s.close()

    def setblocking(self, flag):
        return self.s.setblocking(flag)

    def getpeername(self):
        return self.s.getpeername()

    def getsockname(self):
        return self.s.getsockname()

    def getfileno(self):
        return self.s.getfileno()
