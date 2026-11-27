"""Local mirror server: isolation headers, byte ranges, and engine batch I/O."""
import argparse, gzip, io, json, mimetypes, re, socket, ssl, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs

ROOT = Path(__file__).resolve().parent / 'mirror' / 'playgta5.com'
SUPPORT = Path(__file__).resolve().parent / 'support'
if not (ROOT / 'index.html').is_file():
    nested_root = ROOT.parent / 'mirror' / 'playgta5.com'
    if (nested_root / 'index.html').is_file():
        ROOT = nested_root
mimetypes.add_type('application/wasm', '.wasm')
mimetypes.add_type('text/javascript', '.js')

def improve_game_page(code):
    """Improve support text at serving/build time, preserving verified release files."""
    if 'game-progress' not in code:
        return code
    code = code.replace(': the device may be out of memory. Close other tabs, or reload.',
                        ': loading has paused. Use Help / browser checks and collect the first console error.')
    code = code.replace('If the tab shows "Aw, Snap!" or SIGILL it ran out of memory.',
                        'A tab crash needs its error details; it does not by itself prove insufficient RAM.')
    link = '<a href="/__support/" target="_blank" rel="noopener" style="position:fixed;top:12px;right:12px;z-index:10000;background:#182621;color:#fff;padding:10px 14px;border-radius:5px;font:14px system-ui;text-decoration:none">Help / browser checks</a>'
    fx = ('<script>(function(){var f=new URLSearchParams(location.search).get("fx");'
          'if(f&&["sharp","pixel","punch","hd","cinema","vivid","noir","cool"].indexOf(f)>-1){document.documentElement.className+=" fx-"+f;}})();</script>'
          '<style>html.fx-sharp #canvas{filter:url(#fx-sharpen) saturate(1.08) contrast(1.03);will-change:filter;}'
          'html.fx-pixel #canvas{image-rendering:pixelated;}'
          'html.fx-punch #canvas{filter:saturate(1.1) contrast(1.05);will-change:filter;}'
          'html.fx-hd #canvas{filter:url(#fx-hd) saturate(1.04) contrast(1.02);will-change:filter;}'
          'html.fx-cinema #canvas{filter:url(#fx-hd) saturate(1.12) contrast(1.10) sepia(0.10) hue-rotate(-8deg);will-change:filter;}'
          'html.fx-vivid #canvas{filter:saturate(1.25) contrast(1.07) brightness(1.03);will-change:filter;}'
          'html.fx-noir #canvas{filter:grayscale(1) contrast(1.22) brightness(1.02);will-change:filter;}'
          'html.fx-cool #canvas{filter:saturate(0.92) contrast(1.06) hue-rotate(14deg);will-change:filter;}</style>'
          '<svg width="0" height="0" style="position:absolute;overflow:hidden" aria-hidden="true">'
          '<filter id="fx-sharpen" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">'
          '<feConvolveMatrix order="3" preserveAlpha="true" edgeMode="duplicate" kernelMatrix="0 -0.3 0 -0.3 2.2 -0.3 0 -0.3 0"/>'
          '</filter>'
          '<filter id="fx-hd" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">'
          '<feConvolveMatrix order="3" preserveAlpha="true" edgeMode="duplicate" kernelMatrix="0 -0.18 0 -0.18 2.42 -0.18 0 -0.18 0"/>'
          '</filter></svg>\n')
    return code.replace('<body>', '<body>\n' + fx + link, 1)

class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # keep-alive: the game's ~90 parallel fetches reuse 6 connections instead of opening a new one per request

    def setup(self):
        super().setup()
        self.connection.settimeout(30)
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def __init__(self, *args, **kwargs):
        self.byte_range = None
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_response(self, code, message=None):
        self._cache_control_sent = False
        super().send_response(code, message)

    def send_header(self, keyword, value):
        if keyword.lower() == 'cache-control':
            self._cache_control_sent = True
        super().send_header(keyword, value)

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Accept-Ranges', 'bytes')
        if not self._cache_control_sent:
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def send_head(self):
        self.byte_range = None
        if urlsplit(self.path).path in ('/', '/index.html') and (ROOT / 'index.html').is_file():
            body = improve_game_page((ROOT / 'index.html').read_text(encoding='utf-8')).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return io.BytesIO(body)
        support_files = {'/__support/': 'index.html', '/__support/check.js': 'check.js',
                         '/__support/settings.html': 'settings.html',
                         '/__support/userdata-inspect.html': 'userdata-inspect.html',
                         '/__support/userdata-dump.html': 'userdata-dump.html',
                         '/__support/userdata-fix.html': 'userdata-fix.html'}
        support_name = support_files.get(urlsplit(self.path).path)
        if support_name:
            path = SUPPORT / support_name
            if not path.is_file():
                self.send_error(404)
                return None
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(str(path)))
            self.send_header('Content-Length', str(path.stat().st_size))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return path.open('rb')
        if not self.headers.get('Range'):
            return super().send_head()
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return None
        size = path.stat().st_size
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', self.headers['Range'])
        if not match or not any(match.groups()):
            self.send_error(416)
            return None
        start = int(match[1]) if match[1] else max(0, size - int(match[2]))
        end = min(size - 1, int(match[2])) if match[1] and match[2] else size - 1
        if start >= size or end < start:
            self.send_response(416)
            self.send_header('Content-Range', 'bytes */%d' % size)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None
        self.byte_range = (start, end)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        source = path.open('rb')
        source.seek(start)
        return source

    def copyfile(self, source, outputfile):
        if self.byte_range is None:
            return super().copyfile(source, outputfile)
        remaining = self.byte_range[1] - self.byte_range[0] + 1
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path == '/log':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(min(max(length, 0), 1024 * 1024))
                log_path = Path(__file__).resolve().parent / 'game-log.txt'
                with log_path.open('ab') as out:
                    out.write(body + b'\n')
                self.send_response(204)
                self.send_header('Content-Length', '0')
                self.end_headers()
            except (OSError, ValueError):
                self.send_error(400)
            return
        if url.path != '/data/batch':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.send_error(400, 'Invalid Content-Length')
            return
        if not 0 <= length <= 1024 * 1024:
            self.send_error(413, 'Invalid batch size')
            return
        try:
            runs = json.loads(self.rfile.read(length))
            if not isinstance(runs, list) or len(runs) > 1000:
                raise ValueError('invalid batch')
            selected = []
            data_root = (ROOT / 'data').resolve()
            for name, start, end in runs:
                if not isinstance(name, str) or type(start) is not int or type(end) is not int:
                    raise ValueError('invalid file/range types')
                file = (data_root / name).resolve()
                if not file.is_relative_to(data_root) or start < 0 or end < start:
                    raise ValueError('invalid file/range')
                selected.append((file, start, max(0, min(end + 1, file.stat().st_size) - start)))
            total = sum(n for _, _, n in selected)
            if total > 64 * 1024 * 1024:
                raise ValueError('batch exceeds 64 MiB')
            output = io.BytesIO()
            for file, start, n in selected:
                with file.open('rb') as source:
                    source.seek(start)
                    output.write(source.read(n))
            body = output.getvalue()
            compressed = parse_qs(url.query).get('gz') == ['1']
            if compressed:
                body = gzip.compress(body, compresslevel=1)
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Run-Lengths', ','.join(str(n) for _, _, n in selected))
            if compressed:
                self.send_header('Content-Encoding', 'gzip')
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, TypeError, OSError) as exc:
            self.send_error(400, str(exc))

if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--port', type=int, default=8000)
    args.add_argument('--root', type=Path, help='existing game directory containing index.html, b/, and data/')
    args.add_argument('--open', action='store_true', help='open browser compatibility and launch page')
    args.add_argument('--lan', action='store_true', help='bind to all interfaces instead of 127.0.0.1')
    args.add_argument('--cert', type=Path, help='TLS certificate PEM')
    args.add_argument('--key', type=Path, help='TLS private key PEM')
    options = args.parse_args()
    if options.root:
        ROOT = options.root.resolve()
    if not (ROOT / 'index.html').is_file():
        args.error('Game files are missing. Run Download-Game.cmd (Windows) or Download-Game.command (Mac) first.')
    try:
        host = '0.0.0.0' if options.lan else '127.0.0.1'
        server = ThreadingHTTPServer((host, options.port), Handler)
        if options.cert and options.key:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(options.cert), str(options.key))
            server.socket = context.wrap_socket(server.socket, server_side=True)
    except OSError as error:
        args.error(f'Cannot start on port {options.port}: {error}. Close the previous game server with Ctrl+C, or choose --port 8001.')
    scheme = 'https' if options.cert else 'http'
    address = '%s://localhost:%d/' % (scheme, server.server_port)
    print('Local mirror: %s (Ctrl+C to stop)' % address, flush=True)
    if options.open:
        webbrowser.open(address + '__support/')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
