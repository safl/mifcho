#!/usr/bin/env python
import threading
import mimetypes
import urlparse
import binascii
import logging
import hashlib
import base64
import pprint
import socket
import struct
import string
import select
import Queue
import math
import json
import uuid
import time
import sys
import re
import os

from binascii import hexlify

import mifcholib.messages as messages
import mifcholib.ws as websocket
from mifcholib import rfb
from mifcholib.threadutils import Worker, WorkerPool
from mifcholib.peer_info import PeerInfo
from mifcholib.piper import Piper, VncPiper, WebsocketPiper, WebsocketVncPiper, HobsPiper, HobsVncPiper
from mifcholib.tunnel import Tunnel

class ManagementHandler(WorkerPool):
    """
    Accepts jobs on the form:

        (conn, address, request_line)
    """

    def __init__(self, cm, workers=10):

        self.cm             = cm
        self.buffer_size    = 4096

        WorkerPool.__init__(self, 'ManagementHandler', workers)

    def work(self, env):
        
        conn = env['mifcho.conn']
        
        opened_sockets = []
        for bo in self.cm.opened:
            try:
                opened_sockets.append({'sockname': bo.getsockname(), 'peername':bo.getpeername()})
            except:
                opened_sockets.append({'sockname': 'Not connected', 'peername':'Not connected'})

        serializable_perf = {
          'peers':          [repr(peer) for peer in self.cm.peers],
          'bound_sockets':  [{'sockname': bs.getsockname()} for bs in self.cm.bound],
          'opened_sockets': opened_sockets,
          'perf_log':       [x for x in self.cm.performance_collector.log()]
        }

        try:
            res_body = json.dumps(serializable_perf)
            res_headers = [('Content-Length', len(res_body)),
                           ('Content-Type', 'text/html'),
                           ('Access-Control-Allow-Origin', '*')]

            messages.send_response(conn, 200, 'OK', 'HTTP/1.1', res_headers)
            conn.sendall(res_body)

            self.cm.teardown(conn)
        except:
            logging.debug('Something went wrong', exc_info=3)

class StaticWebHandler(WorkerPool):
    """
    Serves static files over HTTP.
    
    Accepts jobs on the form:

        (conn, address, (method, uri, version))

    """

    def __init__(self, cm, workers=10, path_prefix=''):

        self.path_prefix = path_prefix

        WorkerPool.__init__(self, 'StaticWebHandler', workers)

    def work(self, env):

        conn = env['mifcho.conn']

        path = self.path_prefix + os.sep + "/".join(env['PATH_INFO'].split('?')[0].split('/')[2:])

        status      = 404
        status_msg  = 'File Not Found'
        res_body    = '404 - File Not Found'
        content_type = ('Content-Type', 'text/plain')

        if os.path.exists(path):

            status      = 200
            status_msg  = 'OK'
            
            if os.path.isdir(path):
                res_body = pprint.pformat(os.listdir(path))
            else:
                fd = open(path)
                res_body = fd.read()
                fd.close()

            content_type    = ('Content-Type', mimetypes.guess_type(path)[0])
        
        res_headers = [
            ('Content-Length', len(res_body)),
            content_type,
            ('Access-Control-Allow-Origin', '*')
        ]

        messages.send_response(
            conn,
            status,
            status_msg,
            'HTTP/1.1',
        res_headers)
        if res_body:
            conn.sendall(res_body)
        
        try:
            conn.close()
        except:
            logging.debug('Something went wrong when trying to close socket.', exc_info=3)

class HobsHandler(WorkerPool):
    """
    Accepts jobs in the form:

        (conn, addr, (method, uri, status))
    """

    hobs_sessions = {}
    _HOBS_CREATE        = re.compile('create/(\d+)/(\d+)/([a-z\-.0-9]+)/(\d+)')
    _HOBS_SESSION_SEND  = re.compile('session/(\d+)/(\d+)')
    _HOBS_SESSION_RECV  = re.compile('session/(\d+)')

    def __init__(self, cm, workers=10):

        self.cm = cm
        WorkerPool.__init__(self, 'HobsHandler', workers)

    def deallocate(self):        

        for hsession in HobsHandler.hobs_sessions:
            try:
                HobsHandler.hobs_sessions[hsession]['queue'].put('')
            except:
                logging.debug('Error when trying to put "end-job" into Hobs-session queue.', exc_info=3)

    def work(self, env):
        
        conn = env['mifcho.conn']

        i = 0;

        try:
            
            if env['REQUEST_METHOD'] == 'GET' and string.find(env['PATH_INFO'], 'create') > -1:

                ep_stuff  = None
                prefix  = ''
                method  = ''
                rid     = 0
                wait    = 50                    
                ep_host = ''
                ep_port = 0
                peer_id = None
                req_path  = env['PATH_INFO'].split('/')

                if len(req_path) == 7:  # Directly
                    ep_stuff = ( _, prefix, method, rid, wait, ep_host, ep_port ) = req_path
                    
                elif len(req_path) == 8: # Via Peer
                    ep_stuff = ( _, prefix, method, rid, wait, ep_host, ep_port, peer_id ) = req_path
                    
                else:
                    logging.error('Invalid path! %s' % repr(data))                    
                logging.debug('EPSTUFF! %s' % pprint.pformat(ep_stuff))
                rid         = int(rid)
                wait        = int(wait)
                ep_address  = (ep_host, int(ep_port))

                # Assume failure, overwritten on successful connect
                sid = ''
                ep_status = 404
                ep_status_msg = 'Connection Denied.'

                # Try and connect to end-point
                try:
                    vnc_conn = self.cm.connect(ep_address, peer_id)

                    if not vnc_conn:
                        logging.error('Could not connect to endpoint!')

                    sid = "%d" % uuid.uuid1().int
                    ep_status = 200
                    ep_status_msg = 'OK'
                    
                    pipe = HobsVncPiper(self.cm, None, vnc_conn, sink_recovery=(ep_address, peer_id))
                    
                    HobsHandler.hobs_sessions[sid] = {'rid': rid, 'wait': wait, 'pipe':pipe}
                    pipe.start()

                except:
                    logging.debug('Error when connecting to end-point host %s' % repr(ep_address), exc_info=3)

                headers = [ ('Content-Length', len(sid)),
                            ('Access-Control-Allow-Origin', '*')
                          ]
                messages.send_response(conn, ep_status, ep_status_msg, 'HTTP/1.1', headers)
                conn.sendall(sid)

            # Receive data that should be forwarded
            elif env['REQUEST_METHOD'] == 'POST' and string.find(env['PATH_INFO'], 'session') > -1:

                hobs  = HobsHandler._HOBS_SESSION_SEND.search(env['PATH_INFO'])
                sid   = hobs.group(1)                
                rid   = int(hobs.group(2))
                
                session = HobsHandler.hobs_sessions[sid]
                if (session['rid']+1) == rid:
                    session['rid'] = rid
                else:
                    logging.debug('Incorrect RID, %d, %d.' % (rid, session['rid']))

                req_txt = ''
                
                if len(env['wsgi.input']) > 0:
                    
                    #stuff it into the piper                    
                    session['pipe'].hobs_in_queue.put(env['wsgi.input'])
                    
                headers = [
                    ('Content-Length',  '0'),
                    ('Access-Control-Allow-Origin', '*')
                ]

                messages.send_response(conn, 200, 'OK', 'HTTP/1.1', headers)

            # GET, hang on to this until we have something to send...
            elif env['REQUEST_METHOD'] == 'GET' and string.find(env['PATH_INFO'], 'session') > -1:

                hobs  = HobsHandler._HOBS_SESSION_RECV.search(env['PATH_INFO'])
                sid   = hobs.group(1)

                data = []
                q = HobsHandler.hobs_sessions[sid]['pipe'].hobs_out_queue

                # Grab data until buffer is empty
                block   = False
                timeout = 0

                while self.running:

                    # This is so far the best strategy... but it seems way too inefficient... severe latency issues..
                    try:
                        # Get from piper queue
                        data.append(q.get(block, timeout)) # NOTE: This blocking halt delays the exit of mifcho
                        q.task_done()

                        if len(data) > 0 and block: # Data arrived while blocking, timeout is "reset"
                            block   = False
                            timeout = 0

                    except Queue.Empty:

                        if len(data)>0: # Buffer has been sucked dry
                            break

                        elif block:     # No data and we have already blocked and timed out
                            break

                        else:       # No data so block until data is available or timeout exceeds
                            block = True
                            timeout = 30
            
                buf = base64.b64encode(''.join(data))
                headers = [
                            ('Content-Length', str(len(buf))),
                            ('Content-Type',    'text/plain'),
                            ('Access-Control-Allow-Origin', '*')
                          ]
                
                messages.send_response(conn, 200, 'OK', 'HTTP/1.1', headers)
                conn.sendall(buf)
            else:
                logging.error('Unsupported HOBS request! %s.' % (repr(req_uri)))

        except:
            logging.debug('Something went terribly wrong in the Hobs-handling...', exc_info=3)
        
        i += 1

        self.cm.teardown(conn)

class WebsocketHandler(WorkerPool):
    """    
    Handles (conn, address, data) jobs.
    Parses the communication based on the websocket draft 76 / hixie.
    """
    
    def __init__(self, cm, workers=10):
        
        self.cm = cm
        self.buffer_size = 4096
        
        WorkerPool.__init__(self, 'WebsocketHandler', workers)
        
    def _ws_handshake(self, env):
        
        conn = env['mifcho.conn']
        
        headers = [
            ('Upgrade',             'WebSocket'),
            ('Connection',          'Upgrade'),
            ('Sec-WebSocket-Origin',    env['HTTP_ORIGIN']),
            ('Sec-WebSocket-Protocol',  'sample'),
            ('Sec-WebSocket-Location',  'ws://%s%s' % (env['HTTP_HOST'], env['PATH_INFO'])),            
        ]
        
        key1 = env['HTTP_SEC_WEBSOCKET_KEY1']
        key2 = env['HTTP_SEC_WEBSOCKET_KEY2'],
        key3 = conn.recv(8)
        
        server_key = websocket.keys_to_md5(key1, key2, key3)
        
        messages.send_response(
            conn,
            101,
            'Web Socket Protocol Handshake',
            'HTTP/1.1',
            headers
        )
        conn.send(server_key)

        # Grab connection parameters
        
        ep_stuff  = None
        peer_id   = None
        req_path  = env['PATH_INFO'].split('/')

        if len(req_path) == 4:  # Directly
            ep_stuff = (_, _, ep_host, ep_port) = req_path

        elif len(req_path) == 5: # Via Peer
            ep_stuff = (_, _, ep_host, ep_port, peer_id) = req_path
        else:
            logging.error('Invalid path! %s' % repr(data))

        if ep_stuff:
            ep_address = (ep_host, int(ep_port))

            # Initiate endpoint connection
            vnc_conn = self.cm.connect(ep_address, peer_id)
            
        sink_recovery = (ep_address, peer_id)
        return (conn, vnc_conn, sink_recovery)

    def work(self, env):

        conn = env['mifcho.conn']

        (ws, s, sink_r) = self._ws_handshake(env)
        if s:
        
            pipe = WebsocketVncPiper(self.cm, ws, s, sink_recovery=sink_r)
            pipe.start()
            
            while self.running:
                time.sleep(0.1)
        else:
            self.cm.teardown(ws)

class PeerHandler(WorkerPool):

    def __init__(self, cm, workers=10):

        self.cm = cm

        WorkerPool.__init__(self, 'PeerHandler', workers)

    def work(self, env):

        conn = env['mifcho.conn']
        
        request_mapping = {
            'HANDSHAKE':        self.handshake,
            'TUNNEL':           self.tunnel,
            'TUNNEL_REQUEST':   self.tunnel_request
        }
        
        (_,
         operation,
         _) = messages.path_to_fun(env['PATH_INFO'])    # Extract request-information

        if env['REQUEST_METHOD'] == 'POST' and operation.upper() in request_mapping:
            
            request_mapping[operation.upper()](conn, env)   # Handle request

        else:
            logging.error('Error!', exc_info=3)

    def handshake(self, conn, env):

        peer_id   = env['HTTP_X_MIFCHO_ID']

        res_status      = 200                       # Regular connection
        res_status_msg  = 'OK'
        res_headers     = [
          ('X-Mifcho-Id', self.cm.identifier)
        ]
                                                    # "Reversed" connection
        reverse = env.get('HTTP_UPGRADE') == 'mifcho-reverse/0.1'

        if reverse:
            res_status      = 101
            res_status_msg  = 'Switching Protocol'

            res_headers.append(('Upgrade', env['HTTP_UPGRADE']))

        try:                                      # Inform peer

            messages.send_response(
              conn,
              res_status,
              res_status_msg,
              'HTTP/1.1',
              res_headers
            )

        except:
            logging.error('Failed sending response to "handshake".')
            raise

        if reverse: # Store for later use (tunnel requests)
            self.cm.add_peer(PeerInfo(peer_id, conn))

    def tunnel_request(self, conn, env):
        
        logging.debug('TUNNEL_REQUEST')
        
        # Get params from request
        peer_id     = env['HTTP_X_MIFCHO_ID']
        tunnel_id   = env['HTTP_X_MIFCHO_TUNNEL_ID']
        ep_address  = (
            headers['HTTP_X_MIFCHO_TUNNEL_ENDPOINTHOST'],
            int(headers['HTTP_X_MIFCHO_TUNNEL_ENDPOINTPORT'])
        )
                
        # Lookup the peer in peer-list to get the interface to connect to
        peer = self.cm.get_peer(peer_id)
        
        # Connect to peer, with the carrier-connection
        peer_conn   = self.cm.connect((peer.interface[0], peer.interface[1]))
        messages.send_request(
            peer_conn,
            type        = 'POST',
            url         = '/mifcho/tunnel',
            headers=[
                ('X-Mifcho-Id',         self.cm.identifier),
                ('X-Mifcho-Tunnel-Id',  tunnel_id),
              ]
        )

        # Connect to end-point        
        ep_conn = self.cm.connect(ep_address)        
        
        if peer_conn and ep_conn:   # All is good
            pipe = Piper(self.cm, peer_conn, ep_conn, 4096, sink_recovery=(ep_address, peer_id))
            pipe.start()
            self.cm.pipes.append(pipe)
            
        elif not ep_conn:           # Inform peer that we could not create connection
            self.cm.teardown(conn)
        else:
            logging.error('Some other error [%s].' % repr(address))
            self.cm.teardown(conn)
        
    def tunnel(self, conn, env):
        
        logging.debug('TUNNEL')
        
        if 'HTTP_X_MIFCHO_TUNNEL_ID' in env: # We requested the tunnel
            
            logging.debug('We requested the tunnel...')
            
            tunnel = self.cm.tunnels[env['HTTP_X_MIFCHO_TUNNEL_ID']]
            tunnel.peer_connection = conn
            
            messages.send_response(conn,
                code      = 101,
                message   = 'Switching Protocols',
                headers   = [
                  ('X-Mifcho-Id', env['mifcho.id'])
                ]
            )
            
            tunnel.event.set()
            
        else:   # We did not request the tunnel so this is an indirect tunnel carrier.
            
            logging.debug('We did not request it...')
            ep_address = (
                env['HTTP_X_MIFCHO_TUNNEL_ENDPOINTHOST'],
                int(headers['X_MIFCHO_TUNNEL_ENDPOINTPORT'])
            )        
            
            ep_conn = self.cm.connect(ep_address)
            
            if conn and ep_conn:
                
                logging.debug('Successfully contacted endpoint...')
                tunnel    = Tunnel.fromconnections(conn, ep_conn)
                tunnel.id = str(uuid.uuid4())
                
                self.cm.add_tunnel(tunnel)
                
                messages.send_response(conn,
                    code      = 101,
                    message   = 'Switching Protocols',
                    headers   = [
                      ('X-Mifcho-Id', self.cm.identifier)
                    ]
                )            
            
                pipe = Piper(self.cm, conn, ep_conn, 4096, sink_recovery=(ep_address, None))
                pipe.start()
                self.cm.pipes.append(pipe)
            else:
                logging.error('Failed connecting to endpoint [%s].' % repr(address))
                self.cm.teardown(conn)

class MiGISH(WorkerPool):
    """
    MiG interactive session handler.
    """
    
    def __init__(self, cm, workers=10):
        
        self.cm = cm
        WorkerPool.__init__(self, 'MIGSession')
    
    def work(self, job):
        
        
        (cli_conn, address, data) = job
        srv_conn = self.cm.connect(('localhost', 5900), '2222')
        pipe = VncPiper(self.cm, cli_conn, srv_conn, buffer_size=4096)
        pipe.start()

class TCPTunnelingHandler(WorkerPool):
    """
    Jobs on the form:

        (connection, address, (peer_id, ep_host, ep_port))

    Providing a peer_id will cause the tunneling to be routed through the
    peer identified by peer_id.
    """

    def __init__(self, cm, workers=10):

        self.cm = cm
        self.buffer_size  = 4096

        WorkerPool.__init__(self, 'TCPTunnelingHandler', workers)

    def work(self, job):

        try:
            (conn, address, data) = job
            (ep_host, ep_port, peer_id) = data
            address=(ep_host, ep_port)
        except:
            logging.debug("Error when unwrapping arguments...", exc_info=3)

        try:
            ep_conn = self.cm.connect(address, peer_id, False) # TODO: tls should be optional

            if ep_conn:
                pipe = Piper(self.cm, conn, ep_conn, self.buffer_size)
                pipe.start()
                self.cm.pipes.append(pipe)
            else:
                logging.error('Failed connecting to endpoint [%s].' % repr(address))
                self.cm.teardown(conn)

        except:
            logging.debug('Probably a connection-failure... %s.', exc_info=3)
            self.cm.teardown(conn)