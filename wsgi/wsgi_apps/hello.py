def app(environ, start_response):
    
    status  = '200 OK'                          # HTTP Status
    headers = [('Content-Type', 'text/plain')]  # HTTP Headers
    start_response(status, headers)

    # The returned object is going to be printed
    return ["Hello World"]