#!/usr/bin/env python

def bosh_responder(c, req):
  
  stuff = 'hello'
  headers = [ ('Content-Length', len(stuff)),
              ('Access-Control-Allow-Origin', '*')
            ]
  
  now = time.time()
  
  # Grab respond to five requests
  i = 0;
  while True:
    
    i += 1
    logging.debug(repr(req))
    logging.debug('Response %d' % i)
    messages.send_response(c, 200, 'OK', 'HTTP/1.1', headers)
    c.sendall(stuff)
    
    # Grab another request
    req = messages.get_request(c)
    
def http_responder(c, req):
  
  stuff = 'hello'
  headers = [ ('Content-Length', len(stuff)),
              ('Access-Control-Allow-Origin', '*')
            ]
  
  now = time.time()
  
  # Grab respond to five requests
  for i in xrange(5):
    
    logging.debug(repr(req))
    logging.debug('Response %d' % i)
    messages.send_response(c, 200, 'OK', 'HTTP/1.1', headers)
    c.sendall(stuff)
    
    # Grab another request
    req = messages.get_request(c)

def http_chunker(c, req, padding=False):
  
  def pad_string(s, size=4096):
    p = '0'*size
    return s+p[len(s):]

  (method, uri, version, headers) = req
  
  headers = [
              ('Content-Type', 'text/plain'),
              ('Transfer-Encoding', 'chunked'),
              ('Access-Control-Allow-Origin', '*'),
            ]

  logging.debug(repr(req))
  messages.send_response(c, 200, 'OK', 'HTTP/1.1', headers)
  hej = 'world'
  
  big_chunk = 'aasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadasaasdsadsadas'
  small_chunk = 'time has come to push the button'
  
  if padding:
    msg = pad_string(small_chunk)
  
  now = time.time()

  # Send five chunks
  while (now +5 > time.time()):
    c.sendall(hexlify(struct.pack('!i', len(msg)))+'\r\n'+msg+'\r\n')
    time.sleep(1)

  c.sendall(hexlify(struct.pack('!b', 0))+'\r\n\r\n')
  
# Handles (socket, address) jobs.
# Parses the communication based on the websocket draft
#
class LongPollWorker(server.Worker):

  client_worker_count = 0

  def __init__(self, work_queue):
    
    name = 'LongPollWorker-%d' % LongPollWorker.client_worker_count
    LongPollWorker.client_worker_count += 1
    server.Worker.__init__(self, work_queue, name)

  def work(self, job):
    
    (s, address) = job
    logging.debug('Doing job! %s' % repr(job))
    
    # Wrap socket into Connection
    c = entities.Connection(s)
            
    logging.debug('Grabbing!')
    
    # Parse the first request
    req = (method, uri, version, headers) = messages.get_request(c)
      
    # Handle it in different ways
    if uri.path == '/test':    
      http_responder(c, req)
    else:
      http_chunker(c, req)
    
    c.close()
    logging.debug('End of job')
    
# Send ws handshake response
def ws_responder(c, req):
  
  headers = [
              ('Upgrade',             'WebSocket'),
              ('Connection',          'Upgrade'),
              ('WebSocket-Origin',    'null'),
              ('WebSocket-Location',  'ws://wstest.local:8081/vnc'),
              ('WebSocket-Protocol',  'sample')
            ]
  
  messages.send_response(c, 101, 'Web Socket Protocol Handshake', 'HTTP/1.1', headers)