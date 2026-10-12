"""Local simulator fault proxy: replace one committed withdrawal response with 503.

Never logs request bodies or authentication headers. Upstream is loopback only.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class Handler(BaseHTTPRequestHandler):
    dropped = False
    lock = Lock()

    def log_message(self, *args):
        pass

    def forward(self):
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in {'host', 'connection', 'transfer-encoding'}}
        headers['Connection'] = 'close'
        connection = http.client.HTTPConnection('127.0.0.1', 18081, timeout=15)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            status = response.status
            content_type = response.getheader('Content-Type', 'application/json')
        finally:
            connection.close()
        with Handler.lock:
            drop = (not Handler.dropped and self.command == 'POST'
                    and self.path == '/api/app/v1/withdrawals' and status == 201)
            if drop:
                Handler.dropped = True
        if drop:
            status = 503
            payload = b'{"detail":"Local fault injection: committed response unavailable"}'
            print('Withheld one committed withdrawal response', flush=True)
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward


if __name__ == '__main__':
    with ThreadingHTTPServer(('127.0.0.1', 18082), Handler) as server:
        print('Local response-fault proxy: 18082 -> 18081', flush=True)
        server.serve_forever()
