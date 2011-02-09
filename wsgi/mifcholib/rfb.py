#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Simon Andreas Frimann Lund
#
# An implementation of the RFB Protocol messages.
# RFB: http://www.realvnc.com/docs/rfbproto.pdf
#
# version / major / minor - Simply "configure" the protocol version.
#                           This implementation is 3.8 only! Not backward compatible.
#
# In addition to the messages described in the standard a couple of additional
# datastructures are available for convenience:
#
# Client struct - Data describing the client (rfb version and data from client init.)
# Server struct - Data describing the server (rfb version and data from server init)
#
# The "struct" module is heavily used to create messages for the network layer
# in an efficient way.
#
# RFB 6 describes the types used, below is a mapping of the types described in
# the standard and the formatting values for the struct.pack function.
#
# Unsigned: u8, u16, u32 = B, H, I
# Signed:   s8, s16, s32 = b, h, i
# Byte-order: big-endian / network order = !
#
# An optimization could be to skip all the static calls to pack, having defined
# all the static protocols messages as simple strings.
# This would reduce readability for people with untrained eyes for hex.
#
# This struct module is a blessing!
#
# -- END_HEADER ---
#
#from struct import *
import binascii
import logging
import pprint
import struct
import math

# Various states
READ_VERSION    = 0
READ_NOST       = 1
READ_SEC_TYPES  = 2
READ_SEC_RESULT = 3
READ_SRV_INIT   = 4
READ_SRV_NAME   = 5

READ_UNKNOWN    = 1000

READ_ERR        = -1
READ_ERR_MSG    = -2

SRV_MSG     = 10

SRV_FBUFFER         = 100
SRV_FBUFFER_RECT    = 101
SRV_FBUFFER_ENC     = 102
SRV_FBUFFER_ENC_RAW         = 110
SRV_FBUFFER_ENC_COPYRECT    = 120
SRV_FBUFFER_ENC_CURSOR      = 130
SRV_FBUFFER_ENC_DSIZE       = 140

SRV_FBUFFER_ENC_POINTER_POS = 150
SRV_FBUFFER_ENC_X11CURSOR   = 160

SRV_COLMAP  = 200
SRV_BELL    = 300
SRV_TEXT    = 400

SRV_UNKNOWN = 100

CLI_SEC_TYPE        = 600
CLI_SHARED          = 610
CLI_MSG             = 620

CLI_PIX_FORMAT  = 630
CLI_ENCODINGS   = 640
CLI_FBUFFER_REQ = 650
CLI_KEY_EVT     = 660
CLI_POINTER_EVT = 670
CLI_CUT_TEXT    = 680

CLI_UNKNOWN = 700

DISCONNECTED    = -3

PIXEL_FORMAT = struct.pack('!BBBBHHHBBBBBB', 32, 24, 0, 1, 255, 255, 255, 16, 8, 0, 0, 0, 0)

# Message types as described in 6.4

# RFB 6.2
security = {
  'INVALID'   : struct.pack('!B', 0),
  'NONE'      : struct.pack('!B', 1),
  'VNC_AUTH'  : struct.pack('!B', 2),
  'RA2'       : struct.pack('!B', 5),
  'RA2NE'     : struct.pack('!B', 6),
  'TIGHT'     : struct.pack('!B', 16),
  'ULTRA'     : struct.pack('!B', 17),
  'TLS'       : struct.pack('!B', 18),
  'VENCRYPT'  : struct.pack('!B', 19)
}

# RFB 6.4
clientMessages = {
  'SET_PIXEL_FORMAT'  : struct.pack('!B', 0),
  'SET_ENCODINGS'     : struct.pack('!B', 2),
  'KEY_EVENT'         : struct.pack('!B', 4),
  'POINTER_EVENT'     : struct.pack('!B', 5),
  'CLIENT_CUT_TEXT'   : struct.pack('!B', 6),
  'FRAMEBUFFER_UPDATE_REQUEST' : struct.pack('!B', 3),
  
  # The registrered / non-standard messagetypes are the same for both client and server
  'VMWARE1' : struct.pack('!B', 254),
  'VMWARE2' : struct.pack('!B', 127),
  'GII'     : struct.pack('!B', 253),
  'ANTHONY_LIGUORI' : struct.pack('!B', 255)
}

# RFB 6.5
serverMessages = {
  'BELL'                    : struct.pack('!B', 2),
  'SERVER_CUT_TEXT'         : struct.pack('!B', 3),
  'FRAMEBUFFER_UPDATE'      : struct.pack('!B', 0),
  'SET_COLOUR_MAP_ENTRIES'  : struct.pack('!B', 1),
  
  # The registrered / non-standard messagetypes are the same for both client and server
  'VMWARE1' : struct.pack('!B', 254),
  'VMWARE2' : struct.pack('!B', 127),
  'GII'     : struct.pack('!B', 253),
  'ANTHONY_LIGUORI' : struct.pack('!B', 255)
}

# RFB 6.6
encodings = {
  'RAW'           : struct.pack('!i', 0),
  'COPY_RECT'     : struct.pack('!i', 1),
  'RRE'           : struct.pack('!i', 2),
  'HEXTILE'       : struct.pack('!i', 5),
  'ZRLE'          : struct.pack('!i', 16),
  'CURSOR'        : struct.pack('!i', -239),
  'DESKTOP_SIZE'  : struct.pack('!i', -223)
}

# A bunch of registrered / non-standard encodings exist. See RFB 6.6 for details.

class Rectangle:
    """
    Experimenting with representing rectangle like this.
    Is this overdoing it?
    """
    
    def __init__(self, x, y, width, height, pixelData, encoding=0):
        
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.encoding = encoding
        self.pixelData = pixelData

def intoN(sequence, n, base=10):
    """
    Helper function to split a string into a list element each n wide.
    Useful for creating input for struct.pack.
    
    example:
    intoN('hello there', 1)->[int('h'), int('e'), ... , int('e')]
    """
    return (int(sequence[i:i+n], base) for i in range(0, len(sequence), n))

def protocolVersion():
    """The first message in the handshake, send by both client and server."""
    return "RFB 003.008\n"

def invalidVersion(reason="VNC Server disconnected because it's got the flue!"):
    """
    Send by the server when the client version is not supported.
    
    RFB 6.1.2
    """
    return  struct.pack('!B', 0) + \
            struct.pack('!I', len(reason)) + \
            reason;

def securityTypes(sec_types=[1, 2]):
    """Server announces supported security types, RFB 6.1.2."""
    return struct.pack('!B%s' % ('B'*len(sec_types)), len(sec_types), *sec_types)
    
def securityType(type):
    """
    Client sends the chosen security type to server.
    Response to securityTypes
    
    RFB 6.1.2
    """
    return struct.pack('!B', type)

def securityResult(succes):
    """
    Security result success,
    
    RFB 6.1.3
    @param success Boolean
    """  
    # True == 1 in Python
    # BUT!!
    # True == 0 in RFB
    # Be aware that in RFB 6.3.1 things are more python-ish
    
    # Hence the negation of the boolean
    return struct.pack('!I', int(not succes))

def vncAuthChallenge():
    """
    VNC Authentification challenge
    
    Generate a random 16-byte challenge.
    
    RFB 6.2.2
    TODO: - a static challenge is provided, randomize the "normal" version
    """
    return struct.pack('!16B', *intoN('29c2a0229ac73a43751a248a975d469d', 2, 16))
  
def vncStaticAuthChallenge():
    """I need to be documented!"""
    return struct.pack('!16B', *intoN('29c2a0229ac73a43751a248a975d469d', 2, 16))

def vncAuthResponse(response):
    """
    VNC Authentification response
   
    Encrypt challenge with DES using a password supplied by the user as the
    key and send the resulting 16-byte response.
   
    RFB 6.2.2
    """
    if len(response) != 16:
        raise NameError
    return response

# Initialization

def clientInit(sharedDesktop):
    """
    Client Initialization
    
    Shared-flag is non-zero (true) if the server should try to share the desktop
    by leaving other clients connected, zero (false) if it should give exclusive
    access to this client by disconnecting all other clients.
    
    RFB 6.3.1
    """
    return struct.pack('!B', int(sharedDesktop))
  
# Server Initialization

def pixelFormat(bpp, depth, big_endian, true_color,
                red_max, green_max, blue_max,
                red_shift, green_shift, blue_shift):
    
    return struct.pack('!BBBBHHHBBBBBB',
        bpp, depth, big_endian, true_color,
        red_max, green_max, blue_max,
        red_shift, green_shift, blue_shift,
        0,0,0   # Padding
    )

# TODO: Pixel format
def serverInit(width, height, format, name):
  return  struct.pack('!HH', width, height) +\
          format +\
          struct.pack('!I', len(name)) +\
          name

# Client to server messages

def setPixelFormat(bpp, depth, bigEndian, trueColor,
                   redMax, greenMax, blueMax,
                   redShift, greenShift, blueShift):
    """
      TODO: Figure out what's wrong here... according to the standard then the message
            below needs padding before and after. But according to reverse engineering
            of x11vnc then that's not the case!
      
      RFB 6.4.1
    """                  
    return struct.pack('!BBBBHHHBBBBBB', bpp, depth, int(bigEndian), int(trueColor),
                                redMax, greenMax, blueMax,
                                redShift, greenShift, blueShift,
                                0, 0, 0)

def setPixForm(bpp, depth, bigEndian, trueColor, redMax, greenMax, blueMax, redShift, greenShift, blueShift):
    return struct.pack('!BBBBBBBBHHHBBBBBB',
        0, 0, 0, 0,                         # msg_type, pad, pad, pad
        bpp, depth, bigEndian, trueColor,
        redMax, greenMax, blueMax,
        redShift, greenShift, blueShift,
        0, 0, 0                             # Pad, pad, pad
    )

def setEncodings(encodings=[0, 1, -240, -239, -232]):
    """
    RFB 6.4.2
   
    TODO: Do something sensible the encodings are specifics.
    """
    encString = ''
    for enc in encodings:
        encString += struct.pack('!i', enc)
    return struct.pack('!BBH', 2, 0, len(encodings)) + encString

def framebufferUpdateRequest(incremental, x, y, width, height):
    """
    Framebuffer update request
    
    RFB 6.4.3
    
    @param incremental Boolean
    @param x int
    @param y int
    @param width int
    @param height int
    @return string
    """
    return struct.pack("!BBHHHH", 3, int(incremental), x, y, width, height)

def keyEvent(down, key):
    """
    Key event
    
    RFB 6.4.4
    """
    return struct.pack('!BBBB', 4, int(down), 0, 0) + key

def pointerEvent(button, x, y):
    """
    Pointer Event
    
    RFB 6.4.5
    """
    return struct.pack('!BBHH', 5, button, x, y)

def clientCutText(text):
    """
    Client cut text
    
    RFB 6.4.6
    """
    lengthFormat = "!%dB" % len(text)
    return struct.pack('!BBBBI', 6, 0, 0, 0, len(text)) +\
            struct.pack(lengthFormat, *intoN(text,1))

# Server to client messages

def rectangleHeader(x, y, w, h, enc):
    return struct.pack('!HHHHi', x, y, w, h, enc)

def framebufferUpdate(rectangles):
    """
    Framebuffer Update
    
    TODO: Add a short description, capturing the essentials. 2-3 lines.
    
    RFB 6.5.1
    TODO: Implement support for other encodings.
    @param rectangles list of class rectangle
    """  
    return struct.pack("!BBH", 0, 0, len(rectangles)) +\
            ''.join([struct.pack('!HHHHi', r.x, r.y, r.width, r.height, r.encoding)+ r.pixelData for r in rectangles])

def setColourMapEntries():
    """
    Set colour map entries
    
    When the pixel format uses a “colour map”, this message tells the client that
    the specified pixel values should be mapped to the given RGB intensities.
    
    RFB 6.5.2
    TODO: implement
    """
    return "NOT IMPLEMENTED"

def bell():
    """Ring a bell on the client if it has one."""
    return struct.pack('!B', 2)

def serverCutText(text):
    """ Server cut text RFB 6.5.4."""
    return struct.pack('!BBBBI', 3, 0, 0, 0, len(text)) + text

# Unpacking messages
def unpServerInit(bytes):
    return struct.unpack('!HHBBBBHHHBBBBBBI', bytes)

# Generation
def produce_framebuffer(w, h):
    test = struct.pack('!B', 255)
    r = Rectangle(0,0,w,h, test*w*h*4)
    return framebufferUpdate([r])

def fb_from_file(x, y, w, h, file):

    fd      = open(file,'rb')   # Grab image for FB
    buff    = fd.read()[71:]+struct.pack('B', 0)            # Add pseudo-alpha
    fd.close()
    
    return framebufferUpdate([Rectangle(x, y, w, h, buff)])

def faked_server(conn):
    """
    Needs:
     - path to bitmap.
     - dimensions (w,h) and pixelFormat of server.
     - serverName.
    """
    conn.sendall(protocolVersion())
    
    cli_ver = conn.recv(12)
    print("Received client protocol [%s]" % cli_ver)
    
    if cli_ver[:11] == protocolVersion()[:11]:  # Offer security types
        conn.sendall(securityTypes())
    else:
        conn.sendall(invalidVersion())
        conn.close()
          
    cli_sec_type = conn.recv(1)                     # Client chosen "security"
    print("Received security type [%s] from client" % binascii.hexlify(cli_sec_type))
    
    if cli_sec_type == security['NONE']:
        print("Sending security result OK1 to client")
        conn.sendall(securityResult(True))
    else:
        print('I cant handle that... %s.' % pprint.pformat(cli_sec_type))
        conn.sendall(securityResult(False))        

    cli_shared = conn.recv(1)
    
    conn.send(serverInit(                           # Send server-init
        400,
        100,
        pixelFormat(
            32, 24, 0, 1, 255, 255, 255, 16, 8,0), 'Fake server'
        )
    )
    
    fd      = open('../mifchomedia/please_wait.bmp','rb')   # Grab image for FB
    buff    = fd.read()[71:]+struct.pack('B', 0)            # Add pseudo-alpha
    fd.close()
        
    r = Rectangle(0, 0, 400, 100, buff)    
    conn.send(framebufferUpdate([r]))

def faked_client(conn):
    
    secType = 1 # AuthentificationType = None
          
    # Receive protocol version, send protocol version
    srv_ver = conn.recv(12)
    logging.debug('Received protocol [%s] from vncserver ' %  srv_ver)
    
    if srv_ver == protocolVersion():
      logging.debug('Sending protocol [%s] to vncserver ' % protocolVersion())
      conn.sendall(protocolVersion())
    else:
      logging.debug('Closed connection due to invalid version.')
    
    # Receive security type count, choose one and send it back  
    srv_sec_count =  struct.unpack('!B', conn.recv(1))
    
    if (srv_sec_count > 0):
      srv_sec_types = conn.recv(srv_sec_count[0])
      logging.debug('Received security types [%s] from vncserver ' % binascii.hexlify(srv_sec_types))
      logging.debug('Sending choice [%s] to vncserver ' % binascii.hexlify(securityType(secType)))
      
      conn.sendall(securityType(secType))
        
    srv_sec_res = conn.recv(4)      # Receive security result
    
    conn.sendall(clientInit(1))    
    srv_init    = unpServerInit(conn.recv(24))
    #logging.debug('ServerInit %s.' % pprint.pformat(srv_init))
    pprint.pprint(srv_init)
    
    srv_name    = conn.recv(srv_init[-1])
    #logging.debug('ServerName %s.' % srv_name)
    pprint.pprint(srv_name)
            
    # Send setEncodings
    conn.sendall(setPixForm(32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
    conn.sendall(setEncodings([0,1]))
    
    conn.send(framebufferUpdateRequest(0,0,0,800,600))

class RFBStatemachine:
    """
    Monitors the state of a RFB session based on the bytes sent between
    RFB client and server.
    
    State is updated by the two methods:
    
    from_srv(buffer) - Data from the server to the client
    from_cli(buffer) - Data from the client to the server
    
    """
    
    def __init__(self):
        
        # State manipulations for server
        self.state              = READ_VERSION
        self.prev_state         = READ_VERSION
        self.srv_bytes_read     = 0
        self.srv_cur_msg_bytes  = 0
        
        self.nost       = 0     # Number Of Security Types
        self.nor        = 0     # Number of rectangles
        
        self.noc        = 0     # Number of colors
        self.fc         = 0     # First Color
        
        self.sec_result = 0     # Security Result
        self.sec_types = []     # Parsed Security Types        
        self.snl     = 0        # ServerName Length
        self.eml     = 0        # Error Message Length
        
        self.text_l     = 0     # Server cut-text-length        
        
        self.server = {
            'w': 0, 'h':0, 'bpp':0, 'depth': 0, 'true_color':0, 'big_endian':0,
            'rgb_max': (0,0,0), 'rgb_shift': (0,0,0),
            'name': '', 'security_types': [], 'protocol': ''
        }
        
        self.rectangle = {
            'x': 0,
            'y': 0,
            'w': 0,
            'h': 0,
            'enc': 0
        }
            
        # State manipulations for client
        self.cli_state          = READ_VERSION
        self.cli_prev_state     = READ_VERSION
        self.cli_bytes_read     = 0
        self.cli_cur_msg_bytes  = 0
        
        self.client = {
            'protocol':     '',
            'encodings':    []
        }
        
        self.noe = 0        # Number of encodings
        self.cli_text_l = 0 # Client cut text length

    def from_cli(self, buff, buff_l, cursor=0):
        
        deeper          = True
        delay_bytes     = 0
        current_state   = self.cli_state
        
        # Handshaking
        if self.cli_state == READ_VERSION and buff_l >= cursor+12:
            
            logging.debug('Reading version...')
            self.client['protocol'] = str(buff[cursor:cursor+12])
            logging.debug('Version %s.' % pprint.pformat(self.client))
            
            cursor += 12
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_SEC_TYPE            
        
        elif self.cli_state == CLI_SEC_TYPE and buff_l >= cursor+1:
            
            logging.debug('Reading chosen security type...')
            
            sec_type = buff[cursor+0]
            logging.debug('SecType: %d.' % sec_type)
            
            cursor += 1
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_SHARED
            
        elif self.cli_state == CLI_SHARED and buff_l >= cursor+1:
            
            logging.debug('Reading shared flag...')
            
            shared_flag = buff[cursor+0]
            logging.debug('Shared=%d.' % shared_flag)
            
            cursor += 1
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
            
        elif self.cli_state == CLI_MSG and buff_l >= cursor+1:
            
            logging.debug('Reading client message type...')
            
            msg_type = buff[cursor+0]
            logging.debug('MSG_TYPE %d.' % msg_type)
                        
            cursor += 1
            self.cli_prev_state = self.cli_state
            if msg_type == 0:
                self.cli_state = CLI_PIX_FORMAT
            
            elif msg_type == 2:
                self.cli_state = CLI_ENCODINGS
                # MiG Specific, we want to restrict the encodings!
                delay_bytes += 1
                
            elif msg_type == 3:
                self.cli_state = CLI_FBUFFER_REQ
                
            elif msg_type == 4:
                self.cli_state = CLI_KEY_EVT
            
            elif msg_type == 5:
                self.cli_state = CLI_POINTER_EVT
                
            elif msg_type == 6:
                self.cli_state = CLI_CUT_TEXT
            else:
                self.cli_state = CLI_UNKNOWN
            
        elif self.cli_state == CLI_PIX_FORMAT and buff_l >= cursor+19:
            
            logging.debug('Reading set_pixel_format...')
            
            pixel_format = struct.unpack('!BBBBBBBHHHBBBBBB', str(buff[cursor:cursor+19]))
            logging.debug('pixel_format %s.' % pprint.pformat(pixel_format))
                        
            cursor += 19
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
        
        elif self.cli_state == CLI_ENCODINGS and buff_l >= cursor+3:
            
            logging.debug('Reading NOE...')
            
            (self.noe, ) = struct.unpack('!H', str(buff[cursor+1:cursor+3]))
            logging.debug('NOE %d.' % self.noe)
            
            cursor      += 3
            delay_bytes += 3
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_ENCODINGS + 1
        
        elif self.cli_state == (CLI_ENCODINGS +1) and buff_l >= cursor+(self.noe*4):
            
            logging.debug('Reading encodings...')
            
            encodings = struct.unpack('!%s' % ('i'*self.noe), str(buff[cursor:cursor+self.noe*4]))
            logging.debug('Encodings %s.' % pprint.pformat(encodings))
            
            # MiG specific, remove encodings that this statemachine cannot handle.
            delay_bytes     = 4
            msg_start       = cursor - delay_bytes
            msg_end         = cursor + (self.noe*4)
            del buff[msg_start:msg_end]
                    
            new_encodings   = setEncodings([0, 1])
            i = 0
            for c in new_encodings:
                buff.insert(msg_start+i, c)
                i += 1
            
            cursor = msg_start + len(new_encodings)
            
            delay_bytes     = 0
            self.cli_prev_state = self.cli_state
            self.cli_state  = CLI_MSG
            
        elif self.cli_state == CLI_FBUFFER_REQ and buff_l >= cursor+9:
            
            logging.debug('Reading FBUFFER Req...')
            
            fbuffer_req = struct.unpack('!BHHHH', str(buff[cursor:cursor+9]))
            logging.debug('Request %s.' % pprint.pformat(fbuffer_req))
                        
            cursor += 9
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
            
        elif self.cli_state == CLI_KEY_EVT and buff_l >= cursor+7:
            
            logging.debug('Reading KeyEvent...')
            
            key_event = struct.unpack('!BBBI', str(buff[cursor:cursor+7]))
            logging.debug('KeyEvent %s.' % pprint.pformat(key_event))
                        
            cursor += 7
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
            
        elif self.cli_state == CLI_POINTER_EVT and buff_l >= cursor+5:
            
            logging.debug('Reading PointerEvent...')
            
            pointer_event = struct.unpack('!BHH', str(buff[cursor:cursor+5]))
            logging.debug('PointerEvent %s.' % pprint.pformat(pointer_event))
                        
            cursor += 5
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
            
        elif self.cli_state == CLI_CUT_TEXT and buff_l >= cursor+7:
            
            logging.debug('Reading ClientCutText Headers...')
            
            (self.cli_text_l,) = struct.unpack('!I', str(buff[cursor+3:cursor+7]))
            logging.debug('CCT headers %d.' % self.cli_text_l)
            
            cursor += 7
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_CUT_TEXT + 1
        
        elif self.cli_state == CLI_CUT_TEXT + 1 and buff_l >= cursor+self.cli_text_l:
        
            logging.debug('Reading ClientCutText...')
            cct = buff[cursor:cursor+self.cli_text_l]
            logging.debug('ClientCutText %s.' % cct)
                        
            cursor += self.cli_text_l
            self.cli_prev_state = self.cli_state
            self.cli_state = CLI_MSG
        
        elif self.cli_state == CLI_UNKNOWN:
            deeper = False
        
        # No matching states with satisfying buffers, returning to receive data.
        else:
            deeper = False
            logging.debug('%d, %d' % (self.cli_state, buff_l))        
        
        if deeper and len(buff) > cursor:    # Investigate the remaining buffer
            
            #logging.debug('Going deeper buff_l B=%d, C=%d.' % (len(buff), cursor))
            return self.from_cli(buff, len(buff), cursor)
            
        else:
            if current_state == self.cli_state:
                self.cli_cur_msg_bytes += cursor-delay_bytes
            else:
                self.cli_cur_msg_bytes = 0
            logging.debug('Bytes read on the current message %d.' % self.cli_cur_msg_bytes)
            return cursor
    
    def from_srv(self, buff, buff_l, cursor=0, delay_bytes=0):
        
        deeper          = True
        current_state   = self.state
        
        # Handshaking
        if self.state == READ_VERSION and buff_l >= cursor+12:
            
            logging.debug('Reading version...')
            self.server['protocol'] = str(buff[cursor:cursor+12])
            logging.debug('Version %s.' % pprint.pformat(self.server))
                        
            cursor += 12
            self.prev_state = self.state
            self.state      = READ_NOST
            
        elif self.state == READ_NOST and buff_l >= cursor+1:
            
            logging.debug('Reading NOST...')
            
            self.nost = buff[cursor]
            logging.debug('NOST = %s.' % pprint.pformat(self.nost))
                        
            cursor += 1
            self.prev_state = self.state
            self.state = READ_SEC_TYPES
            
        elif self.state == READ_SEC_TYPES and buff_l >= cursor+self.nost:
            
            logging.debug('Reading %d security types...' % self.nost)
            self.sec_types = struct.unpack('!%s' % ('B'*self.nost), str(buff[cursor:cursor+self.nost]))
            logging.debug('sec_types %s.' % pprint.pformat(self.sec_types))
            
            cursor += self.nost
            
            self.prev_state = self.state
            if len(self.sec_types) > 0:
                
                self.state = READ_SEC_RESULT
                
                # TODO: Handle states of various auth-methods
                
            else:                   # No security types => unsupported version
                self.state = READ_ERR
            
        elif self.state == READ_SEC_RESULT and buff_l >= cursor+4:
            
            logging.debug('Reading security result...')
            
            (self.sec_result,) = struct.unpack('!I', str(buff[cursor:cursor+4]))
            logging.debug('sec_result %d' % self.sec_result)
                        
            cursor += 4
            self.prev_state = self.state
            self.state = READ_SRV_INIT
        
        # Initialization
        elif self.state == READ_SRV_INIT and buff_l >= cursor+24:
            
            logging.debug('Reading server init...')
            
            srv_init = struct.unpack('!HHBBBBHHHBBBBBBI', str(buff[cursor:cursor+24]))
            
            self.server['w']            = srv_init[0]
            self.server['h']            = srv_init[1]
            self.server['bpp']          = srv_init[2]
            self.server['depth']        = srv_init[3]
            self.server['true_color']   = srv_init[4]
            self.server['big_endian']   = srv_init[5]
            self.server['rgb_max']      = (srv_init[6], srv_init[7], srv_init[8])
            self.server['rgb_shift']    = (srv_init[9], srv_init[10], srv_init[11])            
            
            self.snl = srv_init[-1]
            logging.debug('ServerInit: %s.' % pprint.pformat(self.server))
            
            cursor      += 24
            
            # MiG-Specific!
            #
            # Delay bytes to be able to send a the server-name-length
            # header with a different name for anonymization purposes.
            delay_bytes += 4
            self.prev_state = self.state
            self.state = READ_SRV_NAME
            
        elif self.state  == READ_SRV_NAME and buff_l >= cursor+self.snl:
        
            logging.debug('Reading servername...')
            self.server['name'] = str(buff[cursor:cursor+self.snl])
            logging.debug('ServerName %s.' % pprint.pformat(self.server))
            
            # MiG-Specific!
            #
            # Anonymization of server-name, for use with MiG.
                
            name        = 'MiG Desktop'
            name_l      = len(name)            
            anon_msg    = struct.pack('!I', name_l) + name
            
            msg_start   = cursor - delay_bytes
            msg_end     = cursor + self.snl
            
            del buff[msg_start:msg_end]         # Delete old server-name            
            
            i = 0                               # Insert "MiG Desktop"
            for c in anon_msg:
                buff.insert(msg_start+i, c)
                i += 1
            
            cursor      = msg_start + len(anon_msg)
            
            delay_bytes = 0
            self.prev_state = self.state
            self.state = SRV_MSG
        
        # Server Message
        elif self.state == SRV_MSG and buff_l >= cursor+1:
            
            logging.debug('Reading server message type...')
            
            msg_type = buff[cursor]
            logging.debug('Server message type %d.' % msg_type)
            
            cursor += 1
            
            self.prev_state = self.state
            if msg_type == 0:
                self.state = SRV_FBUFFER
            elif msg_type == 1:
                self.state = SRV_COLMAP
            elif msg_type == 2:
                self.state = SRV_BELL
            elif msg_type == 3:
                self.state = SRV_TEXT
            else:
                self.state = SRV_UNKNOWN
        
        # Server Message, framebuffer update
        elif self.state == SRV_FBUFFER and buff_l >= cursor+3:
            
            logging.debug('Reading NOR...')
            (self.nor,) = struct.unpack('!H', str(buff[cursor+1:cursor+3]))
            logging.debug('NOR %d.' % self.nor)
                        
            cursor += 3
            
            self.prev_state = self.state
            if self.nor > 0:                
                self.state = SRV_FBUFFER_RECT
            else:
                self.state = SRV_MSG
        
        # Server Message, framebuffer update, rectangle
        elif self.state == SRV_FBUFFER_RECT and buff_l >=cursor+12:
            
            logging.debug('Reading Rectangle...')
            
            rectangle       = struct.unpack('!HHHHi', str(buff[cursor:cursor+12]))
            self.rectangle  = {
                'x':    rectangle[0],
                'y':    rectangle[1],
                'w':    rectangle[2],
                'h':    rectangle[3],
                'enc':  rectangle[4]
            }
            
            logging.debug('Rectangle: %s.' % pprint.pformat(self.rectangle))
                        
            cursor += 12
            self.prev_state = self.state
            if self.rectangle['enc'] == 0:
                self.state = SRV_FBUFFER_ENC_RAW
                
            elif self.rectangle['enc'] == 1:                
                self.state = SRV_FBUFFER_ENC_COPYRECT
                
            elif self.rectangle['enc'] == -223:
                self.state = SRV_FBUFFER_ENC_DSIZE
                
            elif self.rectangle['enc'] == -232:
                self.state = SRV_FBUFFER_ENC_POINTER_POS
            
            elif self.rectangle['enc'] == -240:
                self.state = SRV_FBUFFER_ENC_X11CURSOR
                
            elif self.rectangle['enc'] == -239:
                self.state = SRV_FBUFFER_ENC_CURSOR
            
            else:
                self.state = SRV_UNKNOWN
        
        elif self.state == SRV_FBUFFER_ENC_RAW:
            # Waiting for framebuffer-data.
            
            required_bytes = (
                self.rectangle['w'] * \
                self.rectangle['h'] * \
                (self.server['bpp'] / 8 )
            )
            if buff_l >= cursor+required_bytes:
                
                self.nor -= 1
                
                cursor += required_bytes
                self.prev_state = self.state
                if self.nor > 0:
                    self.state = SRV_FBUFFER_RECT
                else:
                    self.state = SRV_MSG
                    
            else:
                deeper = False
        
        elif self.state == SRV_FBUFFER_ENC_COPYRECT:
            
            logging.debug('Reading COPY_RECT...')
            
            coord = struct.unpack('!HH', str(buff[cursor:cursor+4]))
            logging.debug('Coord %s.' % pprint.pformat(coord))
            
            cursor += 4
            self.nor -= 1
            self.prev_state = self.state
            if self.nor > 0:
                self.state = SRV_FBUFFER_RECT
            else:
                self.state = SRV_MSG            
        
        elif self.state == SRV_FBUFFER_ENC_POINTER_POS:
            logging.debug('Reading pointer pos...')
            logging.debug('PointerPos.')
            
            self.nor -= 1
            self.prev_state = self.state
            if self.nor > 0:
                self.state = SRV_FBUFFER_RECT
            else:
                self.state = SRV_MSG
            
        elif self.state == SRV_FBUFFER_ENC_X11CURSOR:
            logging.debug('Reading X11 cursor...')
            logging.debug('X11Cursor.')
            
            self.nor -= 1
            self.prev_state = self.state
            if self.nor > 0:
                self.state = SRV_FBUFFER_RECT
            else:
                self.state = SRV_MSG
        
        elif self.state == SRV_FBUFFER_ENC_CURSOR:
            
            cursor_pixel_bytes =    int(
                self.rectangle['w'] * \
                self.rectangle['h'] * \
                (self.server['bpp']/8)
            )
            
            cursor_bitmask_bytes =  int(
                math.floor( (self.rectangle['w']+7)/8 ) * self.rectangle['h']
            )
            
            required_bytes = (cursor_pixel_bytes + cursor_bitmask_bytes)
            
            if buff_l >= cursor+required_bytes:
                logging.debug('Reading cursor pseudo-encoding pixel-bytes=%d bitmask-bytes: %d.' % (
                        cursor_pixel_bytes,
                        cursor_bitmask_bytes
                    )
                )
                
                self.nor -= 1
                
                cursor += required_bytes
                
                self.prev_state = self.state
                if self.nor > 0:
                    self.state = SRV_FBUFFER_RECT
                else:
                    self.state = SRV_MSG
                
            else:
                deeper = False
        
        # Server Message - Server Cut Text
        elif self.state == SRV_TEXT and buff_l >= cursor+7:
            
            logging.debug('Reading server-text-header...')
            
            (self.text_l,) = struct.unpack('!I', str(buff[cursor+3:cursor+7]))
            logging.debug('Text_l %d.' % self.text_l)
                        
            cursor += 7
            self.prev_state = self.state
            self.state = SRV_TEXT + 1
        
        # Server Message - Server Cut Text, continued
        elif self.state == (SRV_TEXT + 1) and buff_l >= cursor+self.text_l:
            
            logging.debug('Reading server-text...')
            text = str(buff[cursor:cursor+self.text_l])
            logging.debug('Text %s.' % text)
            
            cursor += self.text_l
            self.prev_state = self.state
            self.state = SRV_MSG
        
        # Server Message - Color Map
        elif self.state == SRV_COLMAP and buff_l >= cursor+5: # TODO: implement handling of color-map
            
            logging.debug('Reading color-map headers...')
            
            (self.fc, self.noc) = struct.unpack('!HH', str(buff[cursor+1:cursor+5]))
            logging.debug('FC = %d, NC= %d.' % (fc, self.noc))
            
            cursor += 5
            self.prev_state = self.state
            if self.noc > 0:
                self.state = SRV_COLMAP + 1
            else:
                self.state = SRV_MSG
        
        # Server Message - Color Map, continued
        elif self.state == SRV_COLMAP + 1 and buff_l >= cursor+(self.noc * 6):
            
            logging.debug('Reading color-map colors...')
            color_map = struct.unpack('!%s' % ('HHH'*self.noc), str(buff[cursor:cursor+self.noc*6]))
            logging.debug('ColorMap %s.' % pprint.pformat(color_map))
            
            cursor += self.noc*6
            self.prev_state = self.state
            self.state = SRV_MSG
        
        # Server Message - Bell
        elif self.state == SRV_BELL:
            
            logging.debug('Reading server-bell...')
            logging.debug('Bell.')
            
            self.prev_state = self.state
            self.state = SRV_MSG
        
        # Error
        elif self.state == READ_ERR and buff_l >= cursor+4:
            
            logging.debug('Reading EML...')
            (self.eml,) = struct.unpack('!I', str(buff[cursor:cursor+4]))
            logging.debug('EML = %d...' % self.eml)
            
            cursor += 4
            self.prev_state = self.state
            self.state = READ_ERR_MSG
        
        # Error, continued
        elif self.state == READ_ERR_MSG and buff_l >= cursor+self.eml:
            
            logging.debug('Reading err-msg...')
            
            error_msg = str(buff[cursor:cursor+self.eml])
            logging.debug('Msg [%s]' % error_msg)
            
            cursor += self.eml
            self.prev_state = self.state
            self.state = DISCONNECTED
        
        elif self.state == SRV_UNKNOWN:
            deeper = False
        
        # No matching states with satisfying buffers, returning to receive data.
        else:
            deeper = False
            logging.debug('%d, %d' % (self.state, buff_l))        
        
        if deeper and len(buff) > cursor:    # Investigate the remaining buffer
            
            #logging.debug('Going deeper buff_l B=%d, C=%d' % (len(buff), cursor))            
            return self.from_srv(buff, len(buff), cursor, delay_bytes)
            
        else:
            if current_state == self.state:
                self.srv_cur_msg_bytes += cursor-delay_bytes
            else:
                self.srv_cur_msg_bytes = 0
            logging.debug('Bytes read on the current message %d, cursor %d, buff_l %d.' % (self.srv_cur_msg_bytes, cursor, buff_l))
            return cursor-delay_bytes
