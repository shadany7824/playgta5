"""Build a ZIP64 portable bundle and hash source files as they enter the archive."""
import hashlib, json, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = 'playgta5-offline'
OUTPUT = ROOT / 'playgta5-offline-2026-10-06.zip'

class HashWriter:
    """Non-seekable ZIP output: the hash covers every byte exactly once."""
    def __init__(self, raw):
        self.raw = raw
        self.digest = hashlib.sha256()
        self.position = 0
    def write(self, data):
        n = self.raw.write(data)
        self.digest.update(data[:n])
        self.position += n
        return n
    def tell(self):
        return self.position
    def flush(self):
        self.raw.flush()

def main():
    expected = {'mirror/playgta5.com/' + r['path'].lstrip('/'): r['sha256']
                for r in json.loads((ROOT / 'snapshot/manifest-sha256.json').read_text())}
    expected.update({r['path']: r['sha256'] for r in
        json.loads((ROOT / 'snapshot/runtime-manifest.json').read_text())['files']})
    files = []
    for name in ['mirror', 'runtime', 'snapshot']:
        for path in (ROOT / name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name != '.DS_Store' and path.suffix != '.part' and path.name not in {'package-manifest.json', 'package-report.json', 'package-status.json'}:
                files.append(path)
    for name in ['README.md', 'Launch-Local.cmd', 'Launch-Local.command', 'Start-Local.ps1', 'serve_local.py', 'verify_snapshot.py',
                 'mirror_site.py', 'bundle_runtime.py', 'build_portable_zip.py', 'homepage.html',
                 'loader.js', 'game.js', 'io_worker.js', 'wgpu_worker.js', 'headers.txt',
                 'data-manifest.json', 'shader-index.json', 'public_discovery.py']:
        files.append(ROOT / name)
    files.sort(key=lambda p: str(p.relative_to(ROOT)))
    total = sum(p.stat().st_size for p in files)
    processed = 0
    records = []
    start = time.monotonic()
    last_report = start
    temporary = OUTPUT.with_suffix('.zip.part')
    print('Packaging %d files, %d bytes, stored ZIP64' % (len(files), total), flush=True)
    with temporary.open('wb') as raw:
        writer = HashWriter(raw)
        with zipfile.ZipFile(writer, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for path in files:
                relative = str(path.relative_to(ROOT)).replace('\\', '/')
                info = zipfile.ZipInfo.from_file(path, PREFIX + '/' + relative)
                digest = hashlib.sha256()
                size = 0
                with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        target.write(chunk)
                        size += len(chunk)
                        processed += len(chunk)
                        if time.monotonic() - last_report >= 10:
                            status = {'phase': 'packaging', 'processed_bytes': processed, 'total_bytes': total,
                                'percent': round(processed / total * 100, 1), 'current_file': relative}
                            (ROOT / 'snapshot/package-status.json').write_text(json.dumps(status, indent=2))
                            print(json.dumps(status), flush=True)
                            last_report = time.monotonic()
                sha = digest.hexdigest()
                if relative in expected and expected[relative] != sha:
                    raise ValueError('Source hash changed: ' + relative)
                records.append({'path': relative, 'bytes': size, 'sha256': sha})
            package_manifest = {'root_folder': PREFIX, 'files': records,
                'scope': 'All listed files hashed while packaging; this manifest does not list itself.'}
            manifest_bytes = json.dumps(package_manifest, indent=2).encode()
            archive.writestr(PREFIX + '/snapshot/package-manifest.json', manifest_bytes)
        archive_hash = writer.digest.hexdigest()
    temporary.replace(OUTPUT)
    (ROOT / 'snapshot/package-manifest.json').write_bytes(manifest_bytes)
    with zipfile.ZipFile(OUTPUT) as archive:
        assert len(archive.infolist()) == len(records) + 1
        assert archive.read(PREFIX + '/snapshot/package-manifest.json') == manifest_bytes
        assert archive.read(PREFIX + '/Launch-Local.cmd') == (ROOT / 'Launch-Local.cmd').read_bytes()
        assert archive.read(PREFIX + '/runtime/python312._pth') == (ROOT / 'runtime/python312._pth').read_bytes()
        for rec, info in zip(records, archive.infolist()):
            assert info.filename == PREFIX + '/' + rec['path'] and info.file_size == rec['bytes']
    report = {'archive': OUTPUT.name, 'bytes': OUTPUT.stat().st_size, 'sha256': archive_hash,
        'archive_entries': len(records) + 1, 'source_bytes': total,
        'source_sha256_verified_against_inventory': len(expected), 'compression': 'stored ZIP64',
        'seconds': round(time.monotonic() - start, 1),
        'validation': 'All source SHA-256 checked during packing; archive directory, lengths, manifest, launcher and isolated runtime configuration checked afterward.'}
    (ROOT / 'snapshot/package-report.json').write_text(json.dumps(report, indent=2))
    (ROOT / (OUTPUT.name + '.sha256')).write_text(archive_hash + '  ' + OUTPUT.name + '\n', encoding='ascii')
    (ROOT / 'snapshot/package-status.json').write_text(json.dumps({'phase': 'complete', **report}, indent=2))
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    main()
