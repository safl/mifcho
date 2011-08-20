from urllib import unquote
import mimetypes
import logging
import pprint
import os

def app(environ, start_response):
    
    def chunked_read(fd, size=4096):
        """Lazily read a file in chunks of "size" bytes."""
        
        while True:
            data = fd.read(size)
            if not data:
                break
            yield data
    
    #path = os.sep +'tmp'+ environ['PATH_INFO'].replace('/', os.sep)
    path = "/home/safl/Desktop/projects/tecalibre/gui"+environ['PATH_INFO'].replace('/', os.sep)
    
    status      = '404 File Not Found'              # Default to file not found
    content     = '404 - File Not Found'
    mimetype    = 'text/plain'
    logging.debug('H!!!'+path)
    try:                                            # The file exists
        
        if os.path.exists(path):
            
            status          = '200 OK'
            guessed_type    = mimetypes.guess_type(path)[0]
            
            if guessed_type:
                mimetype = guessed_type
            
            if os.path.isdir(path):
                content = (p for p in pprint.pformat(os.listdir(path)))
            else:
                fd      = open(path)
                content = chunked_read(fd)
    
    except:                                         # Error accessing the file
        status      = '500 Internal Server Error'
        content     = '500 - Internal Server Error'
        mimetype    = 'text/plain'
        logging.error("Bad mojo...", exc_info=3)
    
    start_response(
        status,
        [
            ('Content-Type', mimetype),
            ('Access-Control-Allow-Origin', '*')
        ]
    )
    return content