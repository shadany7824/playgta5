"""Resumable public-asset snapshot. Python standard library only."""
import argparse, concurrent.futures, hashlib, json, os, re, shutil, threading, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'mirror' / 'playgta5.com'
STATE = ROOT / 'snapshot'
#ORIGIN = 'https://playgta5.com'
ORIGIN = 'https://gta.deloskiyt.pl' #currently working origin

BUILD = '/b/8b0b5899ed'
RATE = 24 * 1024 * 1024
WORKERS = 3
lock = threading.Lock()
rate_lock = threading.Lock()
rate_next = time.monotonic()
received = 0
completed = 0
started = time.monotonic()
records = {}
failures = []
STATE.mkdir(exist_ok=True)
SITE.mkdir(parents=True, exist_ok=True)

def emit(message):
    with lock:
        with (STATE / 'download.log').open('a', encoding='utf-8') as out:
            out.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + message + '\n')
    print(message, flush=True)

def throttle(n):
    global rate_next, received
    if RATE:
        with rate_lock:
            now = time.monotonic()
            rate_next = max(now, rate_next) + n / RATE
            delay = rate_next - now
        if delay > 0:
            time.sleep(delay)
    with lock:
        received += n

def download(task):
    global completed
    path, expected, query = task
    target = SITE / path.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    url = ORIGIN + quote(path, safe='/') + query
    previous = records.get(path)
    if target.exists() and previous and target.stat().st_size == previous['bytes']:
        with lock:
            completed += 1
        return
    partial = target.with_name(target.name + '.part')
    for attempt in range(4):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {'User-Agent': 'PersonalResearchSnapshot/1.0', 'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = 'bytes=%d-' % offset
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                status = response.status
                if status != 206:
                    offset = 0
                if status == 206 and not response.headers.get('Content-Range', '').startswith('bytes %d-' % offset):
                    raise ValueError('invalid resume Content-Range')
                length = response.headers.get('Content-Length')
                actual_expected = offset + int(length) if length is not None else None
                if status == 206 and actual_expected is None:
                    actual_expected = int(response.headers['Content-Range'].split('/')[-1])
                if 'text/html' in response.headers.get('Content-Type', '') and not path.endswith(('.html', '/')):
                    raise ValueError('HTML response for an asset')
                digest = hashlib.sha256()
                if offset:
                    with partial.open('rb') as old:
                        while chunk := old.read(1024 * 1024):
                            digest.update(chunk)
                with partial.open('ab' if offset else 'wb') as out:
                    while chunk := response.read(256 * 1024):
                        throttle(len(chunk))
                        out.write(chunk)
                        digest.update(chunk)
                size = partial.stat().st_size
                if actual_expected is not None and size != actual_expected:
                    raise ValueError('body length %d != %d' % (size, actual_expected))
                os.replace(partial, target)
                rec = {'path': path, 'url': url, 'bytes': size, 'sha256': digest.hexdigest(),
                       'manifest_bytes': expected, 'etag': response.headers.get('ETag'),
                       'last_modified': response.headers.get('Last-Modified')}
                with lock:
                    records[path] = rec
                    completed += 1
                    with (STATE / 'files.jsonl').open('a', encoding='utf-8') as out:
                        out.write(json.dumps(rec) + '\n')
                if expected is not None and size != expected:
                    emit('SIZE DISCREPANCY ' + path + ': manifest=%d server=%d' % (expected, size))
                return
        except Exception as exc:
            emit('RETRY %d %s: %s' % (attempt + 1, path, exc))
            if isinstance(exc, HTTPError) and exc.code == 416 and partial.exists():
                partial.unlink()
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
    with lock:
        failures.append({'path': path, 'url': url, 'error': str(exc) if 'exc' in locals() else 'see log'})

def add_existing(path, source):
    target = SITE / path.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / source, target)
    b = target.read_bytes()
    records[path] = {'path': path, 'url': ORIGIN + path, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(), 'manifest_bytes': None}

def main():
    global records
    if (STATE / 'files.jsonl').exists():
        for line in (STATE / 'files.jsonl').read_text(encoding='utf-8').splitlines():
            try:
                rec = json.loads(line)
                records[rec['path']] = rec
            except ValueError:
                pass
    for path, source in [('/index.html', 'homepage.html'), (BUILD + '/loader.js', 'loader.js'),
                         (BUILD + '/game.js', 'game.js'), (BUILD + '/io_worker.js', 'io_worker.js'),
                         (BUILD + '/wgpu_worker.js', 'wgpu_worker.js'), ('/data/manifest.json', 'data-manifest.json'),
                         (BUILD + '/shaders/index.json', 'shader-index.json')]:
        add_existing(path, source)
    manifest = json.loads((ROOT / 'data-manifest.json').read_text())
    shaders = json.loads((ROOT / 'shader-index.json').read_text())
    version = manifest['version']
    tasks = [(BUILD + '/game.wasm', 63201802, ''), (BUILD + '/audio-worklet.js', None, ''),
             ('/data/bootset.json', None, ''), ('/data/bootset_low.json', None, ''),
             (BUILD + '/shaders/pipelines.json', None, ''), (BUILD + '/shaders/pipelines_low.json', None, '')]
    tasks += [(BUILD + '/shaders/' + p['file'], p['bytes'], '') for p in shaders['_packs']]
    art = ['beach_bg', 'beach_fg'] + ['ls%d_background' % i for i in range(17)]
    art += ['ls%d_foreground' % i for i in range(17) if i != 12]
    art += ['ls1_foreground_franklin', 'ls2_foreground_chop', 'ls12_foreground_michael']
    tasks += [(BUILD + '/title/art/' + name + '.webp', None, '') for name in art]
    tasks += [(BUILD + '/title/' + name, None, '') for name in ['logo.png', 'spinner.png', 'chalet.woff']]
    for key, rec in shaders.items():
        if isinstance(rec, dict) and rec.get('ok') and not rec.get('p'):
            tasks.append((BUILD + '/shaders/' + key + '.wgsl', None, ''))
            if rec.get('consts'):
                tasks.append((BUILD + '/shaders/' + key + '.consts.json', None, ''))
    tasks += [('/data/' + f[0], f[1], '?v=' + quote(version)) for f in manifest['files']]
    # Guard against traversal and Windows case collisions before writing assets.
    names = set()
    for path, _, _ in tasks:
        if '..' in Path(path).parts or ':' in path or '\\' in path:
            raise ValueError('unsafe path ' + path)
        folded = path.casefold()
        if folded in names:
            raise ValueError('case collision ' + path)
        names.add(folded)
    (STATE / 'download-plan.json').write_text(json.dumps({'origin': ORIGIN, 'build': BUILD, 'version': version,
        'workers': WORKERS, 'bandwidth_cap_bytes_s': RATE, 'tasks': tasks}, indent=2), encoding='utf-8')
    emit('START pid=%d files=%d data_bytes=%d cap=%d' % (os.getpid(), len(tasks), sum(f[1] for f in manifest['files']), RATE))
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(download, task) for task in tasks]
        while any(not f.done() for f in futures):
            time.sleep(10)
            elapsed = time.monotonic() - started
            summary = {'pid': os.getpid(), 'completed': completed, 'total': len(tasks), 'received_bytes_this_run': received,
                       'elapsed_seconds': round(elapsed), 'average_MiB_s': round(received / max(1, elapsed) / 2**20, 2), 'failures': len(failures)}
            (STATE / 'status.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            emit('PROGRESS ' + json.dumps(summary))
        for f in futures:
            f.result()
    # Expand shader packs without thousands of redundant HTTP requests.
    expanded = 0
    for key, rec in shaders.items():
        if not isinstance(rec, dict) or not rec.get('ok') or not rec.get('p'):
            continue
        k, off, wl, cl = rec['p']
        pack_path = BUILD + '/shaders/' + shaders['_packs'][k]['file']
        pack = SITE / pack_path.lstrip('/')
        if not pack.exists():
            continue
        with pack.open('rb') as src:
            src.seek(off)
            b = src.read(wl + cl)
        if len(b) != wl + cl:
            raise ValueError('short shader pack ' + key)
        for suffix, content in [('.wgsl', b[:wl])] + ([('.consts.json', b[wl:])] if cl else []):
            path = BUILD + '/shaders/' + key + suffix
            (SITE / path.lstrip('/')).write_bytes(content)
            records[path] = {'path': path, 'url': ORIGIN + path, 'bytes': len(content),
                'sha256': hashlib.sha256(content).hexdigest(), 'derived_from': pack_path, 'offset': off if suffix == '.wgsl' else off + wl}
            expanded += 1
    (STATE / 'manifest-sha256.json').write_text(json.dumps(list(records.values()), indent=2), encoding='utf-8')
    (STATE / 'failures.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
    emit('FINISHED downloaded=%d failures=%d expanded_shader_files=%d' % (completed, len(failures), expanded))
    return 1 if failures else 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--rate-mib', type=float, default=24, help='aggregate MiB/s, 0 for unlimited')
    args = parser.parse_args()
    WORKERS = args.workers
    RATE = int(args.rate_mib * 1024 * 1024)
    if WORKERS < 1 or RATE < 0:
        parser.error('workers must be positive and rate nonnegative')
    raise SystemExit(main())
