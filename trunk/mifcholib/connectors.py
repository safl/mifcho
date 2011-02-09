#!/usr/bin/env python
import threading
import logging
import sys

from mifcholib.threadutils import Worker
import mifcholib.messages as messages
from mifcholib.piper import Piper

# Define the usefull purpose of the connector class
# i think it might just be overengneered...
class Connector(Worker):
    pass
