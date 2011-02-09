#!/usr/bin/env python
import re

ORCHESTRATION_REGEX = re.compile("".join([
  '(?P<port>\d+)\s+(?P<protocol>http|https|tcp|tcps)\s+',
  '(?P<dispatch_arg>/[\w]+)\s(?P<handler>\w+)',
  '(?:\s+forward\s+to\s+(?P<forward_to_host>[\w.]+):(?P<forward_to_port>\d+)',
  '(?:\svia (?P<forward_via>[\w\-\d]+))?)?'
]))

def urlparse(text):
    """
    Unstable behavior was observed with the urlparse module so this
    method is used as a replacement.
    """
    res = re.compile('(?:([a-z]+)://)?([a-zA-Z\-.0-9_]+)(?::(\d+))?(.*)').search(text)

    url = None
    if res:
        url = {'scheme': res.group(1), 'hostname': res.group(2), 'port': int(res.group(3)), 'path': res.group(4)}

    return url
