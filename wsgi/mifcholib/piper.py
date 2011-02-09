#!/usr/bin/env python
import threading
import logging
import socket
import base64
import pprint
import select
import struct
import Queue
import time
import ssl

import mifcholib.ws as websocket
from mifcholib import rfb

class Websocket:
    """Piping strategy for websocket protocol translation."""
    
    def readsource(self, conn):    
        return base64.b64decode(websocket.receive_frame(conn))
        
    def writesource(self, conn, data):
        websocket.send_frame(conn, data)
        return len(data)

class Hobs:
    """Piping strategy for Hobs protocol translation."""
    
    def on_start(self, source, sink):
        self.hobs_in_queue  = Queue.Queue() # Contains data read from the socket
        self.hobs_out_queue = Queue.Queue() # Contains data that will be written to the socket
    
    def readsource(self, conn):
        
        data = None
        try:
            data = base64.b64decode(self.hobs_in_queue.get())
        except:
            logging.debug('No data for Hobs... or error?', exc_info=3)
        
        return data
    
    def writesource(self, conn, data):
        
        try:
            self.hobs_out_queue.put_nowait(data)
            written = len(data)
        except:
            logging.debug('Error during pseudo-write to queue...')
            written = 0
            
        return written

class Vnc:
    """Binding of RFBStatemachine to the flow of data of a Pipe."""
    
    def on_start(self, source, sink):
        self.rfb_state  = rfb.RFBStatemachine()
        
    def on_readsource(self, data, data_l):
        return self.rfb_state.from_cli(data, data_l)
        
    def on_readsink(self, data, data_l):
        return self.rfb_state.from_srv(data, data_l)

class BasePiper(threading.Thread):
    """
    Pipes payloads between two sockets.
    """

    piper_count = 0

    def __init__(self, cm, source, sink, buffer_size = 4096, source_recovery=None, sink_recovery=None):

        self.cm     = cm
        self.source = source
        self.sink   = sink        
        self.buffer_size    = buffer_size
        
        self.source_recovery = source_recovery
        self.sink_recovery   = sink_recovery
        
        count = Piper.piper_count # Set the object counter
        Piper.piper_count += 1
        thread_name = 'Piper-%d' % count
                
        self.threads = []
        
        self.sink_wait = threading.Event()
        
        self.threads.append(threading.Thread(
            target=self.pipe,
            name=thread_name+'-source-to-sink',
            args=(source, sink, 'source_to_sink')
        ))
        self.threads.append(threading.Thread(
            target=self.pipe,
            name=thread_name+'-sink-to-source',
            args=(sink, source,'sink_to_source')
        ))
        
        for t in self.threads:
            t.daemon = True

        threading.Thread.__init__(self, name=thread_name)
        self.daemon = True      

    def on_start(self, source, sink):
        """Override this to do something before the actual piping starts."""
        pass

    def readsource(self, conn):
        """Override this to handle reading data from the source differently."""
        return conn.recv(self.buffer_size)
        
    def readsink(self, conn):
        """Override this to handle reading data from the sink differently."""
        return conn.recv(self.buffer_size)
    
    def writesource(self, conn, data):
        """
        Override this to handle writing data to the source differently.
        Must return the amount of bytes sent.
        """
        return conn.send(data)
    
    def writesink(self, conn, data):
        """
        Override this to handle writing data to the sink differently.
        Must return the amount of bytes sent.
        """
        return conn.send(data)
    
    def on_readsource(self, data, data_l):
        """Override this to do something with data arriving from the source."""
        return len(data)
    
    def on_readsink(self, data, data_l):
        """Override this to do something with data arriving from the sink."""
        return len(data)

    def pipe(self, input_socket, output_socket, direction=None):
                
        if direction == 'sink_to_source':           # Map piping methods
            read_input      = self.readsink
            on_read_input   = self.on_readsink
            write_output    = self.writesource
        
        elif direction == 'source_to_sink':            
            read_input      = self.readsource
            on_read_input   = self.on_readsource
            write_output    = self.writesink
            
        else:
            # TODO: raise an expection...
            logging.error('Unsupported direction: %s.' % repr(direction))
        
        buff    = bytearray()                                   # Buffer
        buff_l  = len(buff)         
        
        while self.running:                                     # Piping loop
                        
            try:
                to_send     = 0
                bytes_sent  = 0
                
                data = read_input(input_socket)             # Get some data
               
                if data:
                    
                    buff.extend(data)                           # Buffer it
                    buff_l  = len(buff)
                    
                    to_send = on_read_input(buff, buff_l)   # Inspect it
                    
                    while bytes_sent < to_send:                 # Send it
                        bytes_sent += write_output(
                            output_socket, str(buff[bytes_sent:to_send])
                        )
                    else:
                            del buff[:to_send]  # Remove bytes sent from buffer                            
                                                
                else:
                    logging.debug('ERROR receiving, data == None!')
                    self.running = False
               
            except socket.timeout:
                logging.debug('Socket timeout...')
                pass
            
            # Error on the socket so we leave...
            except socket.error:
                logging.debug('Socket error...', exc_info=3)
                self.running = False
                
            except:
                self.running = False
                logging.debug("Unknown exception.", exc_info=3)

        self.cm.teardown(input_socket)
        self.cm.teardown(output_socket)

    def run(self):

        source_name = str(self.source)
        sink_name   = str(self.sink)

        logging.debug('STARTING %s <--> %s', source_name, sink_name)
        self.on_start(self.source, self.sink)
        
        self.running = True

        for t in self.threads:
            t.start()

        for t in self.threads:
            t.join()

        logging.debug('STOPPED %s <--> %s', source_name, sink_name)

    def stop(self):

        self.running = False        # End while-condition

        self.cm.teardown(self.source)
        self.cm.teardown(self.sink)

class Piper(BasePiper):
    """
    Piper for MiG VNC-sessions:
    
    - Inspects VNC bytestream
    - Injects / manipulates bytestream for anonymization
    - Recovers sink-failures based on the current state of the VNC-session.    
    
    """

    def pipe(self, input_socket, output_socket, direction=None):
                
        if direction == 'sink_to_source':           # Map piping methods
            read_input      = self.readsink
            on_read_input   = self.on_readsink
            write_output    = self.writesource
        
        elif direction == 'source_to_sink':            
            read_input      = self.readsource
            on_read_input   = self.on_readsource
            write_output    = self.writesink
            
        else:
            # TODO: raise an expection...
            logging.error('Unsupported direction: %s.' % repr(direction))
        
        buff    = bytearray()                       # Buffer
        buff_l  = len(buff)        
        
        if 'rfb_state' in dir(self) and direction == 'sink_to_source':
            input_socket.settimeout(9.0)
        
        # For attempting to shield an error.
        attempting_recovery = False
        giveup = 5
        
        while self.running:                         # Piping loop
            
            if attempting_recovery and direction == 'sink_to_source' and 'rfb_state' in dir(self) and self.sink_recovery:
                
                logging.debug('Attempting recovery, buff_l %d!' % len(buff))
                                
                logging.debug('STATE: srv_state: %d, srv_cur_msg_bytes: %d cli_state: %d cli_cur_msg_bytes: %d' % (
                    self.rfb_state.state,
                    self.rfb_state.srv_cur_msg_bytes,
                    self.rfb_state.cli_state,
                    self.rfb_state.cli_cur_msg_bytes
                    )
                )
                logging.debug('self.rfb_state.nor %d, buff_l %d.' % (
                    self.rfb_state.nor,
                    len(buff))
                )
                    
                logging.debug('Adding callback...')
                
                self.cm.teardown(self.sink)
                
                e = threading.Event()
                self.cm.register_callback(e, self.sink_recovery[1])
                
                # Send data to the client which it might need
                if self.rfb_state.state == 110:
                    logging.debug('Send pseudo rectangle of these dimensions: %s.' % pprint.pformat(self.rfb_state.rectangle))
                    
                    fb_size = (
                        self.rfb_state.rectangle['w'] * \
                        self.rfb_state.rectangle['h'] * \
                        (self.rfb_state.server['bpp'] / 8 )
                    )
                    fake_fb = struct.pack('!B',100)*fb_size
                    write_output(output_socket, fake_fb)
                    
                    self.rfb_state.nor -= 1
                    
                    fake_fb = struct.pack('!B', 100)*10*10*4
                    
                    for _ in xrange(0, self.rfb_state.nor):
                        write_output(output_socket, rfb.rectangleHeader(0, 0, 10, 10, 0)+fake_fb)
                    
                    self.rfb_state.nor      = 0
                    self.rfb_state.state    = rfb.SRV_MSG                    
                
                elif self.rfb_state.state == 10:
                    logging.debug('New message... you should be able to send fb!')
                
                else:
                    logging.debug('Unsupported state of recovery...')
                
                logging.debug('Sending fake buffer...')
                
                x_pos = int(abs((self.rfb_state.server['w']/2)-int(400/2)))
                y_pos = int(abs((self.rfb_state.server['h']/2))-int(100/2))
                
                fake_fb         = rfb.fb_from_file(x_pos, y_pos, 400, 100, 'mifchomedia/please_wait.bmp')
                fake_fb_sent    = write_output(output_socket, fake_fb)
                logging.debug('Sending f_fb done.')
                
                logging.debug('Added callback, now waiting...')
                e.wait()
                
                input_socket = self.sink = self.cm.connect(self.sink_recovery[0], self.sink_recovery[1])
                                    
                rfb.faked_client(input_socket)      # Do vnc-handshake
                del buff[0:len(buff)]               # Empty the old buffer
                
                self.sink_wait.set()
                
                attempting_recovery     = False
                giveup                  -= 1
            
            elif attempting_recovery and direction == 'source_to_sink' and 'rfb_state' in dir(self):
                
                # NOTE: Trying to keep on reading from source...
                # buffering it until output_socket comes back online...
                # this could exhaust memory...
                logging.debug('Buffering during recovery... buff_l %d.' % len(buff))
                start   = time.time()
                self.sink_wait.wait(1.0)
                elapsed = time.time() - start
                
                if elapsed < 1.0:                    
                    output_socket   = self.sink
                    
                    giveup              -= 1                    
                    attempting_recovery = False
                    self.sink_wait.clear()
                    
                else:
                
                    try:
                        data = read_input(input_socket)                 # Get some data
                    except:
                        logging.debug('ERROR receiving bytes, buff_l %d.' % len(buff))
                        # The client is not also failing... nothing to recover so just quit
                        self.running = False
                        break
                        #raise
                   
                    if data:
                        
                        buff.extend(data)               # Buffer it
                        buff_l  = len(buff)
                        
                    else:
                        logging.debug('ERROR receiving, data == None!')
            
            else:
                
                try:
                    to_send     = 0
                    bytes_sent  = 0
                    
                    try:
                        data = read_input(input_socket)                 # Get some data
                    except:
                        logging.debug('ERROR receiving bytes, buff_l %d.' % len(buff))
                        raise
                   
                    if data:
                        
                        buff.extend(data)                           # Buffer it
                        buff_l  = len(buff)
                        
                        try:
                            to_send     = on_read_input(buff, buff_l)   # Inspect it
                        except:
                            logging.debug('ERROR inspecting! That was odd... to_send %d.' % to_send)
                            raise
                        
                        try:
                        
                            while bytes_sent < to_send:                 # Send it
                                bytes_sent += write_output(
                                    output_socket, str(buff[bytes_sent:to_send])
                                )
                            else:
                                del buff[:to_send]  # Remove bytes sent from buffer                            
                                
                        except:
                            logging.debug('ERROR sending bytes, bytes_sent %d, to_send %d.' % (bytes_sent, to_send))
                            raise
                        
                    else:
                        logging.debug('ERROR receiving, data == None!')
                        
                        if 'rfb_state' in dir(self):
                            if giveup < 1:
                                self.running = False
                                logging.debug('Giving up...')
                            else:
                                attempting_recovery = True
                                logging.debug('About to attempt recovery!')
                        else:
                            self.running = False
                        
                        logging.debug('No data!')
                   
                except socket.timeout:
                    logging.debug('Socket timeout...')
                    #pass
                    if 'rfb_state' in dir(self):
                        if giveup < 1:
                            self.running = False
                            logging.debug('Giving up...')
                        else:
                            attempting_recovery = True
                            logging.debug("Will attempt recovery.")
                    else:
                        #self.running = False
                        pass
                
                except socket.error:
                    logging.debug('Socket error...', exc_info=3)
                    
                    if 'rfb_state' in dir(self):
                        if giveup < 1:
                            self.running = False
                            logging.debug('Giving up...')
                        else:
                            attempting_recovery = True
                            logging.debug("Will attempt recovery.")
                    else:
                        self.running = False
                    
                except websocket.ConnectionTerminatedException:
                    logging.debug('CLIENT LEFT!, just go home...')
                    self.running = False
                    
                except:
                    #self.running = False
                    if 'rfb_state' in dir(self):
                        if giveup < 1:
                            self.running = False
                            logging.debug('Giving up...')
                        else:
                            attempting_recovery = True
                            logging.debug("Will attempt recovery.")

        self.cm.teardown(input_socket)
        self.cm.teardown(output_socket)

        logging.debug('Piping done.')

    def run(self):

        source_name = str(self.source)
        sink_name   = str(self.sink)

        logging.debug('STARTING %s <--> %s', source_name, sink_name)
        self.on_start(self.source, self.sink)
        
        self.running = True

        for t in self.threads:
            t.start()

        for t in self.threads:
            t.join()

        logging.debug('STOPPED %s <--> %s', source_name, sink_name)

    def stop(self):

        self.running = False        # End while-condition

        self.cm.teardown(self.source)
        self.cm.teardown(self.sink)

class VncPiper(Vnc, Piper):
    """Piper with VNC inspection."""
    pass

class HobsVncPiper(Vnc, Hobs, Piper):
    """Piper with translation of Hobs to regular sokcets and VNC inspection."""
    
    def on_start(self, source, sink):
        Vnc.on_start(self, source, sink)
        Hobs.on_start(self, source, sink)

class HobsPiper(Hobs, Piper):
    """Piper with translation of Hobs to regular sockets."""
    pass

class WebsocketPiper(Websocket, Piper):
    """Piper with translation from Websockets to sockets."""
    pass

class WebsocketVncPiper(Vnc, Websocket, Piper):
    """Piper with translation of websockets to sockets and VNC inspection."""
    pass