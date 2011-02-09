##!/usr/bin/env python
import socket, struct, threading, Queue, time
import base64
from cm import Connection
from collections import deque

# Get framebuffer update
def sucker_q(c, q):
  
  while True:
    data = c.recv(4096)
    if not data:
      break
    q.put_nowait(data)
    
def sucker_d(c, q):
  
  while True:
    data = c.recv(4096)
    if not data:
      break
    q.append(data)

if __name__ == "__main__":
  c = Connection.fromaddress(('localhost', 59000))

  db_q = Queue.Queue()
  db_d = deque()
  
  rfb_ver = c.recv(12)    # Get protocol version
  c.send('RFB 003.008\n') # Send protocol version
  
  (num_sec,) = struct.unpack('b',c.recv(1)) # Get number of security types
  
  print "Num Sec", num_sec
  
  sec_types_raw = c.recv(num_sec) # Get security types
  for i in xrange(num_sec):
    print "Type ", struct.unpack('b', sec_types_raw[i])
  
  c.send(struct.pack('b', 1)) # Ask for "no-auth"
  
  status = struct.unpack('I', c.recv(4)) # Get Security response
  print "Status", status
  
  if status == 1: # Auth failed
    (rsn_length,) = struct.unpack('I', c.recv(4)) # Get reason length
    rsn = c.recv(rsn_length) # Get reason
    print rsn
    
  c.send('1') # Send client-init
  
  srv_init_raw = c.recv(24) # Get server-init
  srv_init = (w, h, bpp, depth, bige, tc, rm, gm, bm, rs, gs, bs, _,_,_, name_len) = struct.unpack('!HHBBBBHHHBBBBBBI', srv_init_raw)
  print srv_init
  
  srv_name = c.recv(name_len) # Get server-name
  print srv_name
  
  # Send fbur
  c.send(struct.pack('!BBHHHH', 3, 0, 0,0,w, h))
  
  # Should get a response now...
  msg_type_raw = c.recv(1)
  (msg_type,) = struct.unpack('!B', msg_type_raw)
  
  print msg_type
  c.recv(1) # padding
  num_rect_raw = c.recv(2)
  (num_rect,) = struct.unpack('!H', num_rect_raw)
  
  print num_rect
  
  rect_raw = c.recv(12)
  rect = (x,y,w,h,enc_type) = struct.unpack('!HHHHI', rect_raw)
  
  num_bytes = w*h*4
  print num_bytes
  
  start = time.time()
  
  t = threading.Thread(target=sucker_q, args=(c, db_q))
  #t = threading.Thread(target=sucker_d, args=(c, db_d))
  t.daemon = True
  t.start()
  
  data = []
  crap = ''
  count = 0
  while True:
    
    # Queue    
    crap = db_q.get()
    db_q.task_done()
    
    count += len(crap)
    data.append(base64.b64encode(crap))
    #data.append(crap)
    
    # Deque
    #if len(db_d) > 0:
    #  while len(db_d)>0:
    #    crap = db_d.popleft()
    #    count += len(crap)
    #    data.append(base64.b64encode(crap))
    #else:
    #  time.sleep(0.001)
      
    if count == num_bytes:
          break
  buf = ''.join(data)
  read_time=time.time()

  print read_time - start
  base64.b64decode(buf)
  print time.time() - read_time
  
  # Try and dump it to file..
  start = time.time()
  fd = open('test.bmp','wb')
  fd.write(buf)
  fd.close()  
  print time.time()-start