from json import dumps as encode

def app(environ, start_response):
    
    cm = environ['mifcho.cm']
    
    opened_sockets = []
    for bo in cm.opened:
        try:
            opened_sockets.append({'sockname': bo.getsockname(), 'peername':bo.getpeername()})
        except:
            opened_sockets.append({'sockname': 'Not connected', 'peername':'Not connected'})

    start_response('200 OK', [('Content-Type', 'text/json')])

    return encode({
        'peers':          [repr(peer) for peer in cm.peers],
        'bound_sockets':  [{'sockname': bs.getsockname()} for bs in cm.bound],
        'opened_sockets': opened_sockets,
        'perf_log':       [x for x in cm.performance_collector.log()]
    })