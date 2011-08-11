#!/usr/bin/env python
from binascii import hexlify
from urllib import unquote
import mimetypes
import urlparse
import logging
import pprint
import time
import glob
import os
import re

import mifcholib.messages as messages

class Dispatcher:
    """Override dispatch() to implement the dispatching policy."""

    def __init__(self, cm):
        self.cm = cm

    def dispatch(self, conn, src_addr, dst_addr):
        raise NotImplementedError

class TCPDispatcher(Dispatcher):
    """Spits the connection to the first available TCPHandler."""

    def dispatch(self, conn, src_addr, dst_addr):

        logging.debug('TCP Dispatching...')
        self.cm.routing_map[dst_addr[1]]['handlers'][0]['instance'].order(
          (conn, src_addr, self.cm.routing_map[dst_addr[1]]['handlers'][0]['params'])
        )

#def mediastreaming_app(environ, start_response):
#        
#    sources = [os.sep+'tmp', os.sep+'media'+os.sep+'remote01']
#    
#    def chunked_read(fd, size=4096):
#        """Lazily read a file in chunks of "size" bytes."""
#        
#        while True:
#            data = fd.read(size)
#            if not data:
#                break
#            yield data
#            
#    status      = '200 OK'
#    type        = 'text/json'
#    
#    def infix_gen(g, pre='[', post='null]'):
#        
#        yield pre
#        for c in g:
#            yield c
#        yield post
#    
#    try:    
#        
#        rest = "/(?P<database>.*)/(?P<collection>.*)/(?P<cmd>insert|save|update|remove|find|find_one)(?:/|,|(?:(?P<attr>\w+):(?P<val>\w+)))*(?:(?:skip=(?P<skip>\d+))|(?:limit=(?P<limit>\d+))|[/&?])*"
#        args = "(?:(?P<key>\w+?)(?:\.(?P<op>like|match|equal))?:(?P<value>\w+),?)"
#        m = re.match(rest, environ['PATH_INFO']+environ['QUERY_STRING'], re.IGNORECASE).groupdict()
#        a = re.findall(args, environ['PATH_INFO'], re.IGNORECASE)
#        print "MATCH! %s:%s:%s" % (environ, str(m), str(a))
#        
#        conn    = pymongo.Connection("localhost", 27017)
#        db      = conn[m['database']]
#        
#        skip    = int(m['skip'])    if m['skip'] else 0
#        limit   = int(m['limit'])   if m['limit'] else 0
#        
#        content = infix_gen(("%s,\n" % encode(p, default=json_util.default) for p in db[m["collection"]].find(spec=dict(a), skip=skip, limit=limit)))
#        
#    except:
#        logging.debug("Something went wrong....", exc_info=3)
#        status      = '404 File Not Found'          # Default to file not found
#        content     = '404 - File Not Found'
#        type        = 'text/html'
#    
#    start_response(
#        status,
#        [
#            ('Content-Type', type),
#            ('Access-Control-Allow-Origin', '*')
#        ]
#    )
#    return content

class WSGI(Dispatcher):
    
    server_name = 'MIFCHO'
    server_ver  = '0.1'
    
    http_ver = 'HTTP/1.1'
                                        # HTTP access-control
    ac_origins = ['*']                  # Everybody is welcome
    ac_methods = ['GET', 'POST']        # Allowed methods
    ac_headers = ['x-requested-with']   # Allowed headers
    ac_max_age = 180
    
    def __init__(self, cm):
        
        self.base_environ = {
            'REQUEST_METHOD':   '',
            'SCRIPT_NAME':      '',
            'PATH_INFO':        '',
            'QUERY_STRING':     '',
            'CONTENT_LENGTH':   0,
            'CONTENT_TYPE':     'text/plain',            
            'SERVER_NAME':      WSGI.server_name,
            'SERVER_PORT':      '',
            'SERVER_PROTOCOL':  '',
            
            'wsgi.version':     (1, 0),
            'wsgi.url_scheme':  '',
            'wsgi.input':       None,
            'wsgi.errors':      None,
            
            'wsgi.multithread':     None,
            'wsgi.multiprocess':    None,
            'wsgi.run_once':        None,
            
            'mifcho.id':    cm.identifier,
            'mifcho.conn':  None
        }
    
    def _env(self, src_addr, dst_addr):
        env = self.base_environ.copy()
        logging.debug("%s %s" % (str(src_addr), str(dst_addr)))
        return env
    
    def dispatch(self, conn, src_addr, dst_addr):
        
        req_count = 0
        
        while True:
            
            req_count += 1
            
            #env     = self.base_environ.copy()
            env     = self._env(src_addr, dst_addr)
            status  = '200 OK'
            
            headers         = []    # Populated by start_response()
            headers_sent    = []
            
            def write(value):
                
                # Write or queue value
                if not headers_set:
                    raise AssertionError("write() before start_response()")
                pass
            
            def start_response(status, response_headers, exc_info=None):
                
                status          = status                # Update the non-local var "status"
                headers_sent    = response_headers      # Update the non-local var "headers_sent"
                
                messages.send_response_line(            # Send request-line
                    conn,
                    int(status.split(' ')[0]),
                    status.split(' ')[1],
                    version = WSGI.http_ver
                )
                for k, v in response_headers:
                    messages.send_header(conn, k, v)    # Send some headers
                
                return write
            
            req = None
            try:
                
                req = (
                    req_method,
                    req_uri,
                    req_version,
                    req_headers
                ) = messages.get_request(conn)
            except:
                logging.debug('Failed retrieving request!', exc_info=3)
                break
            
            (scheme, netloc, path, query, fragment) = urlparse.urlsplit(req_uri)
            
            # Populate the environment variable!
            env["REQUEST_METHOD"]   = req_method
            env['SCRIPT_NAME']      = os.path.basename(path)
            env['PATH_INFO']        = path
            env['QUERY_STRING']     = query+fragment
            
            for (hk, hv) in req_headers:    # Transform headers, WSGI-style
                hk = hk.replace('-','_').upper()
                hv = hv.strip()
                
                if hk == 'CONTENT_LENGTH':                    
                    env[hk] = int(hv.strip())
                elif hk == 'CONTENT_TYPE':
                    env[hk] = hv.strip()
                else:
                    env['HTTP_%s' % hk] = hv
            
            env['wsgi.input'] = ''      # wsgi.input to read request content
            if 'CONTENT_LENGTH' in env and int(env['CONTENT_LENGTH']) > 0:
                env['wsgi.input'] = conn.read_bytes(int(env['CONTENT_LENGTH']))
            else:
                logging.debug('No CONTENT-LENGTH header or CONTENT-LENGTH == 0')
            
            # Determine app based on the request...
            import pyremo, hello, info, static
            app = pyremo.app
            #app = hello.app
            
            try:
                content = app(env, start_response)
            except:
                logging.debug('Unhandled app-error', exc_info=3)
                break
                        
            try:
                
                messages.send_header(
                    conn,
                    'Transfer-Encoding',
                    'chunked'
                )
                messages.end_headers(conn)
                
                for chunk in content:                    
                    cl  = len(chunk)     # Length of chunk
                    hcl = hex(cl)[2:]
                    conn.sendall('%s\r\n' % hcl)
                    conn.sendall(chunk+'\r\n')
                    
                conn.sendall('0\r\n\r\n')
                
            except:
                logging.debug('Error sending response!', exc_info=3)
                break
        
        try:
            conn.close()
        except:
            logging.debug('Failed closing the connection...')
            raise

class HTTPDispatcher(Dispatcher):
    """
    Spits the connection a matching handler based on the query-url.
    
    I did not know about WSGI when i made this... but this could have been
    implemented as WSGI middleware...    
    """

    server_name = 'MIFCHO'
    server_ver  = '0.1'

    # HTTP header-properties
    http_ver = 'HTTP/1.1'

    # HTTP access-control
    ac_origins = ['*']                  # Everybody is welcome
    ac_methods = ['GET', 'POST']        # Basic GET/POST
    ac_headers = ['x-requested-with']   # Only simple headers allowed
    ac_max_age = 180

    def __init__(self, cm):
        
        self.base_environ = {           # If only i had known about WSGI...
            'REQUEST_METHOD':   '',
            'SCRIPT_NAME':      '',
            'PATH_INFO':        '',
            'QUERY_STRING':     '',
            'CONTENT_LENGTH':   0,
            'CONTENT_TYPE':     'text/plain',            
            'SERVER_NAME':      '',
            'SERVER_PORT':      '',
            'SERVER_PROTOCOL':  '',
            
            'wsgi.version':     (1, 0),
            'wsgi.url_scheme':  '',
            'wsgi.input':       None,
            'wsgi.errors':      None,
            
            'wsgi.multithread':     None,
            'wsgi.multiprocess':    None,
            'wsgi.run_once':        None,
            
            'mifcho.id':    cm.identifier,
            'mifcho.conn':  None

        }
        
        Dispatcher.__init__(self, cm)

    def start_response(self, status, response_headers, exc_info=None):
        pass

    def dispatch(self, conn, src_addr, dst_addr):
                
        env = self.base_environ.copy()
        
        logging.debug('Dispatching...')
        try:
                        
            req = (method, uri, version) = messages.get_request_line(conn)            
            req_headers = messages.get_headers(conn)
            
            # Setup environment for handler
            env['REQUEST_METHOD']   = method.upper()
            env['SERVER_NAME']      = dst_addr[0]
            env['SERVER_PORT']      = dst_addr[1]
            env['SERVER_PROTOCOL']  = version
            env['PATH_INFO']        = uri
            
            env['REMOTE_ADDR']  = src_addr[0]
            env['REMOTE_HOST']  = ''
            env['REMOTE_PORT']  = src_addr[1]
            
            for (hk, hv) in req_headers:    # Transform headers, WSGI-style
                hk = hk.replace('-','_').upper()
                hv = hv.strip()
                
                if hk == 'CONTENT_LENGTH':                    
                    env[hk] = int(hv.strip())
                elif hk == 'CONTENT_TYPE':
                    env[hk] = hv.strip()
                else:
                    env['HTTP_%s' % hk] = hv
                            
            env['wsgi.input'] = ''      # wsgi.input to read request content
            if 'CONTENT_LENGTH' in env and int(env['CONTENT_LENGTH']) > 0:
                env['wsgi.input'] = conn.read_bytes(int(env['CONTENT_LENGTH']))
            else:
                logging.debug('No CONTENT-LENGTH header or CONTENT-LENGTH == 0')
            
            env['mifcho.conn']          = conn  # not WSGI compatible!
            env['mifcho.parsed_url']    = urlparse.urlparse(
                url=uri,
                scheme='http'
            )
            
            passed = False                  # Find a handler
            for handler_d in self.cm.routing_map[dst_addr[1]]['handlers']:

                criteria  = handler_d['criteria']
                handler_i = handler_d['instance']
                
                if env['PATH_INFO'][:len(criteria)] == criteria:

                    handler_i.order(env)
                    passed = True
                    break

            if not passed:
                logging.debug('No components!')
                self.cm.teardown(conn)

        except:
            logging.debug('Error during dispatching...', exc_info=3)

    def same_origin_sec(self, conn):

        # Doing options
        res_headers = [
            ('Server', '%s/%s' % (self.server_name, self.server_ver)),
            ('Access-Control-Allow-Origin',   ','.join(self.ac_origins)),
            ('Access-Control-Allow-Methods',  ','.join(self.ac_methods)),
            ('Access-Control-Allow-Headers',  ','.join(self.ac_headers)),
            ('Access-Control-Max-Age', repr(self.ac_max_age)),
            ('Content-Length', '0'),
            ('Connection', 'Keep-Alive')
        ]
        messages.send_response(conn, 200, 'OK', self.http_ver, res_headers)
