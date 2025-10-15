from http.server import BaseHTTPRequestHandler, HTTPServer

class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(301)  # Temporary Redirect
        self.send_header('Location', f'http://127.0.0.1:9999{self.path}')
        self.end_headers()
        print(f"Redirecting to http://127.0.0.1:9999{self.path}")

    def do_POST(self):
        self.do_GET()

    def do_PUT(self):
        self.do_GET()

    def do_DELETE(self):
        self.do_GET()

    def do_HEAD(self):
        self.send_response(307)
        self.send_header('Location', f'http://127.0.0.1:9999{self.path}')
        self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(('', 8000), RedirectHandler)
    print("Serving on port 8000...")
    server.serve_forever()
