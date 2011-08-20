from json import dumps as encode
from json import loads as decode
import logging
import re
import os

from pymongo.objectid import ObjectId
import pymongo.json_util as json_util
import pymongo.connection
import pymongo

conn_params = {
    "host": "localhost",
    "port": 27017,            
    "pool_size":            None,
    "auto_start_request":   None,
    "slave_okay":       False,
    "timeout":          None,
    "network_timeout":  None,
    "document_class":   dict,
    "tz_aware": False,
    "_connect": True            
}

def chunked_read(fd, size=4096):
    """Lazily reads a file-descriptor/"fd" in chunks of "size" bytes."""
    
    while True:
        data = fd.read(size)
        if not data:
            break
        yield data

def infix_gen(g, pre='[', post='null]'):
        
    yield pre
    for c in g:
        yield c
    yield post

def q_parse(path, query):
    
    # This REST interface implementation is limited in the means of naming.
    # chars such as "\" is a valid in a mongo key-name it is however not valid
    # in this interface...
    
    regex = {        
        "db":   "(?P<database>\w+)",
        "coll":	"(?P<collection>[\w\._]+)",
        "cmd":	"(?P<cmd>find(?:_one)?|insert|save|update|remove|drop|count|distinct|download)",
        #"spec":
        #    "(?:"                             +\
        #    "(?P<key>\w+?)"                   +\
        #    "(?:\.(?P<op>like|match|equal))"  +\
        #    "(?:(?P<value>\w+),?)"            +\
        #    ")",        
        #"spec":
        #    "(?P<spec>"                             +\
        #    "(?:\w+?)"                   +\
        #    "\.(?:like|match|equal)"  +\
        #    "(?:\w+,?)"            +\
        #    ")",
        #"spec":
        #    "(?:"                             +\
        #    "(?P<key>\w+?)"                   +\
        #    "(?:\.(?P<op>like|match|equal))"  +\
        #    "(?:(?P<value>\w+),?)"            +\
        #    ")",
        "spec":     "(?P<spec>(?:\w+_(?:like|eq|gt|lt|geq|leq):[\w]+,?)+)",
        "fields":	"(?P<fields>(?:\w+,?)+)",
        
        "sort":     "(?:sort=(?P<sort>(?:\w+:(?:ASC|DESC),?)+)+)",
        "skip":     "(?:skip=(?P<skip>\d+))",
        "limit":	"(?:limit=(?P<limit>\d+))"
    }
    
    rest    = "/%(db)s/%(coll)s/%(cmd)s(/%(spec)s)?(/%(fields)s)?" % regex
    args    = "(?:(?:%(skip)s|%(limit)s|%(sort)s)&?)+" % regex
    
    m = re.match(rest, path+query, re.IGNORECASE)
    a = re.search(args, query, re.IGNORECASE)
    
    return (
        m.groupdict() if m else None,
        a.groupdict() if a else None
    )
    
def compose(f, a):
    
    func = {
        'db':   f['database'],
        'coll': f['collection'],
        'cmd':  f['cmd']
    }
    
    args = {
        'spec':     None,
        'fields':   None,
        'sort':     None,
        'skip':     0,
        'limit':    0,
    }
    
    sort_order = {
        'ASC':  pymongo.ASCENDING,
        'DESC': pymongo.DESCENDING,
        'GEO2': pymongo.GEO2D
    }
    
    if f:
        if 'fields' in f and f['fields']:
            args['fields'] = f['fields'].split(',')
        
        if 'spec' in f and f['spec']:
            args['spec'] = f['spec'].split(':')
            
    if a:
        if 'sort' in a and a['sort']:
            args['sort'] = [(field, sort_order[mt]) for field, mt in [tuple(pair.split(':')) for pair in a['sort'].split(',')]]
            
        if 'skip' in a and a['skip']:
            args['skip'] = int(a['skip'])
        
        if 'limit' in a and a['limit']:
            args['limit'] = int(a['limit'])
    
    return func, args

def app(environ, start_response):
    
    status      = '200 OK'
    mimetype    = 'application/json'
    
    try:
        
        f, a = q_parse(environ['PATH_INFO'], environ['QUERY_STRING'])
        func, args = compose(f, a)
        coll = pymongo.Connection()[func['db']][func['coll']]
        
        if func['cmd'] == 'find':

            content = infix_gen(("%s,\n" %
                encode(p, default=json_util.default) for p in coll.find(**args)
            ))
        
        elif func['cmd'] == 'find_one':            
            pass
        
        elif func['cmd'] == 'count':
            content = [encode(coll.count(), default=json_util.default)]
        
        elif func['cmd'] == 'insert':            
            pass
        
        elif func['cmd'] == 'save':
            pass
        
        elif func['cmd'] == 'update':
            pass
        
        elif func['cmd'] == 'drop':
            
            coll.drop();
        
        elif func['cmd'] == 'download':
            
            prop    = environ['PATH_INFO'].split('/')[-2].strip()
            oid     = environ['PATH_INFO'].split('/')[-1].strip()
            doc     = coll.find_one(ObjectId(oid))
            
            mimetype    = 'image/jpeg'
            if not prop in doc or not os.path.exists(doc[prop]):
                raise Exception("File does not exist!")
                
            #fd = open(doc['path'],'r')
            fd = open(doc[prop],'r')
            content = chunked_read(fd)
            
        elif func['cmd'] == 'tmb':
            
            oid = environ['PATH_INFO'].split('/')[-1].strip()            
            doc = coll.find_one(ObjectId(oid))
            
            mimetype    = 'image/jpeg'
            
            fd = open(doc['tmb'],'r')
            content = chunked_read(fd)
        
        else:
            raise Exception("Command %s is not yet implemented." % func['cmd'])

    except:
        logging.debug("Something went wrong....", exc_info=3)
        status      = '404 File Not Found'          # Default to file not found
        content     = '404 - File Not Found'
        mimetype    = 'text/html'
    
    start_response(
        status,
        [
            ('Content-Type', mimetype),
            ('Access-Control-Allow-Origin', '*')
        ]
    )
    return content

if __name__ == '__main__':
    print ""