import pprint

def app(environ, start_response):
    
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers)
    
    return [pprint.pformat(environ)]