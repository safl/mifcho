#!/usr/bin/env python
import threading
import uuid

class Tunnel:

    def __init__(self, id, client_connection, peer_connection, event):

        self.id = id
        self.event = event
        self.client_connection  = client_connection
        self.peer_connection    = peer_connection

    @classmethod
    def fromconnections(cls, client_connection, peer_connection):

        id = str(uuid.uuid1())
        event = threading.Event()

        return cls(id, client_connection, peer_connection, event)
