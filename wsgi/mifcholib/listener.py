#!/usr/bin/env python
import logging
import socket
import time
import ssl
import os

from mifcholib.connection import Connection
from mifcholib.threadutils import Worker

class Listener(Worker):
    """
    TCP Socket bind/listen/accept on `address`.

    Wrap an accepted socket into a Connection and pass the connection
    off to a dispatcher based on matching in the routing map.
    """

    def __init__(self, cm, address, use_tls):

        self.cm       = cm
        self.use_tls  = use_tls
        self.address  = address
        
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(self.address)
        self.s.listen(5)

        self.cm.bound.append(Connection(self.s, self.use_tls))     # Add to list of bound sockets

        logging.debug('Listening on %s.' % repr(self.s.getsockname()))

        Worker.__init__(self, name='Listener')

    def work(self):

        try:
            new_sock, src_addr = self.s.accept()            # Accept a connection
                        
            if self.use_tls:                        # Wrap it in ssl
                sock = ssl.wrap_socket(
                    new_sock,
                    server_side = True,
                    cert_reqs   = ssl.CERT_NONE,
                    ca_certs    = 'certs'+os.sep+'m3.crt',
                    certfile    = 'certs'+os.sep+'m3.crt',
                    keyfile     = 'certs'+os.sep+'m3.key',
                    #ssl_version = ssl.PROTOCOL_TLSv1
                    ssl_version = ssl.PROTOCOL_SSLv23
                )
                
            else:
                sock = new_sock                     # Dont wrap it in ssl
            
            conn = Connection(sock, self.use_tls)   # Wrap it in Connection
            dest_addr = conn.getsockname()          # Get destination

            self.cm.opened.append(conn)             # Add to opened

            conn_str = "FROM=%s:%s,TO=%s:%s" % (
              src_addr[0],
              src_addr[1],
              dest_addr[0],
              dest_addr[1]
            )
            logging.debug('New connection! [%s]' % conn_str)

                                                      # Add to dispatcher
            self.cm.routing_map[dest_addr[1]]['dispatcher'].dispatch(conn, src_addr, dest_addr)

        except socket.error:
            logging.debug("Socket barf... I give up...", exc_info=3)
            #self.stop()