#!/usr/bin/env python
import threading

class PeerInfo:

    def __init__(self, id, connection, interface=None):
        """
        If the peer accepts incoming connections it will a peer-connection running
        on peer_interface::

          (host, port, path)

        Example::

          ('127.0.0.1', 8000, '/mifcho')
        """

        self.id           = id
        self.connection   = connection
        self.lock         = threading.Lock()

        self.interface = interface
