#!/usr/bin/env python
import unittest
import re

class TestOrchestrationParsing(unittest.TestCase):
  
  def setUp(self):
    self.regex = re.compile('(?P<port>\d+)\s+(?P<protocol>http|https|tcp|tcps)\s+(?P<dispatch_arg>/[\w]+)\s(?P<handler>\w+)(?P<forward_to>\s+forward\s+to\s+[\w.]+:\d+(?P<forward_via>\svia [\w\-\d]+)?)?')
    self.orchestration = """
  8000 http /hobs HobsHandler
  8000 http /wsocket WebsocketHandler
  8000 http /admin ManagementHandler
  8000 http /agent PeerHandler
  8000 http /jsvnc StaticWebHandler
  8001 tcp /None TCPTunnelingHandler forward to safl.dk:80
  8002 tcp /None TCPTunnelingHandler forward to safl.dk:80 via 1234
  """
  
  def test_parse(self):
    for m in self.regex.finditer(self.orchestration):
      print repr(m), m.groupdict()
      
if __name__ == '__main__':
  unittest.main()