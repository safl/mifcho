#!/usr/bin/env python
"""
  ConnectionManager
"""
import threading
import logging
import socket
import pprint
import time
import re
import os

from mifcholib.listener import Listener
from mifcholib.performance_collector import PerformanceCollector
from mifcholib.tunnel import Tunnel
from mifcholib.connection import Connection
from mifcholib.handlers import *
from mifcholib.dispatchers import *
from mifcholib.connectors import *
from mifcholib.threadutils import Worker

class Connector(Worker):
    
    def __init__(self, cm, address, use_tls=False):
        
        self.cm         = cm
        self.address    = address
        self.use_tls    = use_tls    
        
        self.retry_timeout = 60  # Seconds to wait before trying to retry
        
        self.cb_event   = threading.Event()
        
        Worker.__init__(self, name='Connector')
        
    def work(self):
        
        try:
            conn = self.cm.connect(self.address, None, self.use_tls)
        except socket.error:
            conn = None
            logging.error(
                '%s when connecting to %s.' % (                    
                    sys.exc_info()[1],
                    self.address
                )
            )
        
        if conn:            
            conn.callback = self.cb_event   # Associate callback for reconnect
            self.on_connect(conn)           # Call overridden method
            self.cb_event.wait()            # Wait on callback
        else:
            tbegin = time.time()
            while self.running and time.time()-tbegin < self.retry_timeout:
                time.sleep(1)
    
    def deallocate(self):
        self.cb_event.set()
    
    def on_connect(self, conn):        
        logging.error('You got to override me...')

class PeerConnector(Connector):

    def __init__(self, cm, peer, identifier):

        self.buffer_size          = 4096  # Must be "mod 2"...
        
        self.peer = peer        
        self.peer_address   = (peer.interface[0], peer.interface[1])
        self.peer_path      = peer.interface[2]
        
        self.use_tls = peer.interface[3]
        
        Connector.__init__(self, cm, self.peer_address, self.use_tls)

    def on_connect(self, conn):
        
        messages.send_request(                      # Send handshake
            conn,
            'POST',
            '/mifcho/handshake/',
            headers=[
                ('Upgrade',     'mifcho-reverse/0.1'),
                ('Connection',  'Upgrade'),
                ('X-Mifcho-Id', self.cm.identifier)
            ]
        )
        
        response    = (                             # Read response
            version,
            status,
            reason,
            headers
        ) = messages.get_response(conn)
        res_headers = dict(headers)
        
        if int(status) == 101:                      # Store peer

            correct_upgrade =   \
                res_headers.get('Upgrade') == 'mifcho-reverse/0.1' and \
                res_headers.get('Connection') == 'Upgrade'
            
            self.peer.id = res_headers.get('X-Mifcho-Id')   # Update Peer Id
            self.cm.add_peer(self.peer)
        
        while self.running:         # Handle tunnel-requests

            try:

                request = (method, uri, version, headers) = messages.get_request(conn)
                req_headers = dict(headers)
                
                tunnel_id   = req_headers['X-Mifcho-Tunnel-Id']
                ep_address  = (
                    req_headers['X-Mifcho-Tunnel-EndpointHost'],
                    int(req_headers['X-Mifcho-Tunnel-EndpointPort'])
                )
                
                ep_conn = self.cm.connect(ep_address)
                
                if ep_conn: # Inform peer of ep_conn status
                    
                    peer_conn   = self.cm.connect(self.peer_address, None, self.use_tls)
                                    
                    messages.send_response(
                        conn,
                        code=200,
                        message='OK'
                    )
                    
                else:
                    peer_conn   = None
                    
                    messages.send_response(
                        conn,
                        code=404,
                        message='Not Found'
                    )
                
                if ep_conn and peer_conn:
                    messages.send_request(
                        peer_conn,
                        'POST',
                        '/mifcho/tunnel',
                        headers=[
                            ('X-Mifcho-Id',         self.cm.identifier),
                            ('X-Mifcho-Tunnel-Id',  tunnel_id),
                        ]
                    )
                    res = messages.get_response(peer_conn)        
            
                    pipe = Piper(
                        self.cm,
                        ep_conn,
                        peer_conn
                    )
                    pipe.start()
                    self.cm.pipes.append(pipe)
                
            except:
                logging.error('Something happened...', exc_info=3)
                try:
                    self.cm.teardown(conn)
                except:
                    logging.error('And it got even worse!', exc_info=3)
                break

class ConnectionManager(threading.Thread):
    """Supplies helpers and maintains state for managing connections and tunnels."""

    cm_count = 0

    def __init__(self, options):

        self.options = options

        self.bound  = []                      # List of bound sockets NOTE: need a lock?
        self.opened = []                      # List of "opened" sockets NOTE: need a lock?

        self.peers      = {}                  # Peer.id  ---> Peer
        self.peer_lock  = threading.Lock()
        self.pipes = []


        self.tunnels      = {}                # Tunnel.id ---> Tunnel
        self.tunnel_lock  = threading.Lock()

        self.listeners    = []                # List of Listeners
        self.connectors   = []                # List of Connectors
        self.dispatchers  = []                # List of Dispatchers
        self.handlers     = []                # List of Handlers
        
        self.callbacks  = {}

        self.identifier = self.options.id

        self.running = False              # We are not running until we are started

        # Listeners bind to addresses
        for l_address in self.options.bind_addresses:
            l = Listener(
                self,
                (l_address['hostname'], int(l_address['port'])),
                l_address['scheme'] == 'tls'
            )
            self.listeners.append(l)

        self.routing_map = {} # The routing map is per example organized as:
                              #
                              # {'8000': {
                              #   'dispatcher': dispatcher_instance,
                              #   'handlers': [{
                              #     'criteria': SOMETHING,
                              #     'instance': handler_instance,
                              #     'params': job_parameters
                              #   }]
                              # },
                              # {'8001': {
                              #   'dispatcher': dispatcher_instance,
                              #   'handlers': [{
                              #     'criteria': SOMETHING,
                              #     'instance': handler_instance,
                              #     'params': job_parameters
                              #   }]
                              # }}

        # Determine dispatchers:
        prot_dispatch_map = {
          'tcp':    TCPDispatcher,
          'tcps':   TCPDispatcher,
          'wsgi':   WSGI,
          'wsgis':  WSGI,
          'http':   HTTPDispatcher,
          'https':  HTTPDispatcher
        }
        handler_map = {           # This mapping should be automaticly loaded
                                  # and mapped in a "safe" way...
          'HobsHandler':          HobsHandler,
          'WebsocketHandler':     WebsocketHandler,
          #'ManagementHandler':    ManagementHandler,
          #'StaticWebHandler':     StaticWebHandler,
          'PeerHandler':          PeerHandler,
          'TCPTunnelingHandler':  TCPTunnelingHandler,
          'MiGISH':    MiGISH
        }
        for o in options.orchestration:

            port      = int(o['port'])
            protocol  = o['protocol']
            handler   = o['handler']

            forward_to_port = o['forward_to_port']

            criteria  = o['dispatch_arg']
            params    = (o['forward_to_host'], int(forward_to_port) if forward_to_port else None, o['forward_via'])

            existing_instance = [h for h in self.handlers if isinstance(h, handler_map[handler])]
            
            if existing_instance:                         # Reuse existing handler
                handler_i = existing_instance[0]
            else:                                         # Instantiate new handler
                handler_params = options.handler_params[handler] if handler in options.handler_params else {}
                handler_i = handler_map[handler](self, **handler_params)
                self.handlers.append(handler_i)

            existing_dispatcher = [d for d in self.dispatchers if isinstance(d, prot_dispatch_map[protocol])]
            if existing_dispatcher:
                dispatcher_i = existing_dispatcher[0]       # Reuse existing dispatcher
            else:
                dispatcher_i = prot_dispatch_map[protocol](self)  # Instantiate new dispatcher
                self.dispatchers.append(dispatcher_i)

            if port in self.routing_map:                  # Setup routing

                # TODO: check if dispatcher is of differnt type => misconfiguration
                self.routing_map[port]['handlers'].append({
                  'instance': handler_i,
                  'criteria': criteria,
                  'params':   params
                })
            else:

                self.routing_map[port] = {
                  'dispatcher': dispatcher_i,
                  'handlers':   [{
                    'instance': handler_i,
                    'criteria': criteria,
                    'params':   params
                  }]
                }

        for p in self.options.peers:               # Instanciate PeerConnectors

            # Note the constructor should also utilize the "path"
            peer_connector = PeerConnector(
              self,
              peer          = p,
              identifier    = self.identifier
            )
            self.connectors.append(peer_connector)

        self.performance_collector = PerformanceCollector(1)

        count = ConnectionManager.cm_count
        ConnectionManager.cm_count += 1
        threading.Thread.__init__(self, name='CM-%d' % count)

    def run(self):
        """Start the connectionmanager."""

        self.running = True                       # Now we are running!

        self.performance_collector.start()        # Start performance collector

        for t in self.handlers + \
                  self.connectors + \
                  self.listeners:                 # Start threads
            t.start()
        
        for t in [self.performance_collector]+ \
          self.handlers+ \
          self.connectors+ \
          self.listeners:                         # Wait for them to exit
            t.join()

    def connect(self, address, peer_id=None, use_tls=False):
        """Create a connection to address. Possible via another mifcho instance."""
        
        conn = None
        peer = self.get_peer(peer_id)
        
        if not peer and not peer_id:        # Connect "directly" to address
            
            try:
                conn = Connection.fromaddress(address, use_tls)
                
                if conn:                        # Add to opened connections
                   self.opened.append(conn)
                   
            except socket.error:
                logging.error(
                '%s when connecting to %s.' % (                    
                    sys.exc_info()[1],
                    address
                    )
                )
            except:
                logging.error('Unexpected error', exc_info=3)
        
        elif peer and peer.interface:       # Connect via peer interface
            
            # Extract address and parameters of peer interface.
            peer_address = (peer.interface[0], peer.interface[1])            
                        
            try:
                peer_conn = self.connect(peer_address)  # Socket Connect
                
                messages.send_request(                  # Send TunnelReq
                    peer_conn,
                    type    = 'POST',
                    url     = '/mifcho/tunnel',
                    headers = [
                        ('X-Mifcho-Id', self.identifier),
                        ('X-Mifcho-Tunnel-EndpointHost', address[0]),
                        ('X-Mifcho-Tunnel-EndpointPort', address[1])
                    ]
                )
      
                resp = (                                # Wait for response
                    version,
                    status,
                    reason,
                    headers
                ) = messages.get_response(peer_conn)
                
            except:
                logging.error('Failed connecting to socket!')
                
                peer_conn = None
                resp = (
                    version,
                    status,
                    reason,
                    headers
                ) = ('', 404, 'Not Found', [])
                
            conn = peer_conn        
        
        elif peer and not peer.interface:   # Connect via peer control-line
                                            # and "callback".
            
            peer.lock.acquire()             # CRITICAL ZONE START...
            tunnel = Tunnel.fromconnections(None, None)
            self.add_tunnel(tunnel)
            
            try:                            # Send request for tunnel
                messages.send_request(
                    peer.connection,
                    type    = 'POST',
                    url     = '/mifcho/tunnel_request',
                    headers = [
                        ('X-Mifcho-Id',         self.identifier),
                        ('X-Mifcho-Tunnel-Id',  tunnel.id),                        
                        ('X-Mifcho-Tunnel-EndpointHost', address[0]),
                        ('X-Mifcho-Tunnel-EndpointPort', address[1])
                    ]
                )
            except:
                logging.error('Error sending request to peer!', exc_info=3)
            
            try:                            # Wait for response
                resp = (
                    version,
                    status,
                    reason,
                    headers
                ) = messages.get_response(peer.connection)
            except:
                logging.error('Failed receiving response!')
                resp = (
                    version,
                    status,
                    reason,
                    headers
                ) = ('', 404, 'Not Found', [])
            
            peer.lock.release()         # CRITICAL ZONE END....
            
            if int(status) == 200: # All is good
                
                # Wait for PeerHandler to set tunnel-event
                wait_for_tunnel = True
                while status == 200 and self.running and wait_for_tunnel:
                    tunnel.event.wait(1)
                    wait_for_tunnel = not tunnel.event.is_set()
                    
                conn = tunnel.peer_connection
            
            else:
                conn = None
        
        elif peer_id and not peer:
            logging.error('Could not find peer %s.' % repr(peer_id))
            
        else:                               
            logging.error('Invalid params.')
        
        return conn

    def teardown(self, conn):
        """Tear down a socket properly and remove it from the connection-manager."""

        if conn in self.opened:
            try:
                self.opened.remove(conn)
            except:
                pass

        if conn in self.bound:
            try:
                self.bound.remove(conn)
            except:
                pass

        try:
            conn.shutdown()
        except:
            pass
        try:
            conn.close()
        except:
            pass
    
    def register_callback(self, event, peer):
        """
        Execute function when peer connects.
        """
        
        if peer in self.callbacks:
            self.callbacks[peer].append(event)
        else:
            self.callbacks[peer] = [event]
    
    def add_peer(self, peer):

        success = False
        
        self.peer_lock.acquire()
        
        self.peers[peer.id] = peer
        
        if peer.id in self.callbacks:
            for e in self.callbacks[peer.id]:
                e.set()
        self.peer_lock.release()        

        return success

    def get_peer(self, id):

        peer = None

        self.peer_lock.acquire()
        if id in self.peers:
            peer = self.peers[id]
        self.peer_lock.release()

        return peer

    def get_any_peer(self):

        peer = None

        self.peer_lock.acquire()
        if len(self.peers) > 0:
            peer = self.peers.values()[0]
        self.peer_lock.release()

        return peer

    def add_tunnel(self, tunnel):
        """Add a tunnel."""

        success = False

        self.tunnel_lock.acquire()
        if tunnel.id not in self.tunnels:
            self.tunnels[tunnel.id] = tunnel
        self.tunnel_lock.release()

        return success

    def stop(self):
        """Shut down connection-manager."""

        self.running = False                # Tell listeners to stop

        self.performance_collector.stop()   # Tell performance collector to stop

        for w in self.listeners + \
                  self.connectors + \
                  self.handlers:            # Tell threads to stop

            w.stop()

        for opened_socket in self.bound + self.opened: # Tear down sockets
            self.teardown(opened_socket)
