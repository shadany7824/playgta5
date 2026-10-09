"""Check an extracted mirror folder against snapshot/manifest-sha256.json before running it.

Usage (standard library only, so the bundled runtime works):
    runtime\\python.exe check_mirror.py            # full SHA-256 check (about 21 GB to read)
    runtime\\python.exe check_mirror.py --quick    # sizes only

Exit code 0 when every listed file matches and nothing unexpected is present, 1 otherwise.
CHANGED and EXTRA files mean the pack is not the published snapshot; do not run it.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
RISKY = {'.exe', '.dll', '.scr', '.com', '.bat', '.cmd', '.ps1', '.psm1', '.vbs', '.vbe', '.js', '.jse', '.wsf',
         '.hta', '.lnk', '.msi', '.msp', '.jar', '.py', '.pyw', '.pyc', '.reg', '.sys', '.cpl', '.url', '.html', '.htm'}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--mirror', default=str(BASE / 'mirror'), help='folder that contains playgta5.com/')
    parser.add_argument('--quick', action='store_true', help='compare sizes only, skip hashing')
    options = parser.parse_args(argv)
    mirror = Path(options.mirror)
    root = mirror / 'playgta5.com'
    if not root.is_dir():
        print('Not found: %s\nExtract mirror.rar so that %s\\index.html exists.' % (root, root))
        return 1
    records = json.loads((BASE / 'snapshot' / 'manifest-sha256.json').read_text(encoding='utf-8'))
    expected = {(root / r['path'].lstrip('/')).resolve(): r for r in records}
    missing, changed = [], []
    total = sum(r['bytes'] for r in records)
    done, start, last = 0, time.monotonic(), 0.0
    for path, rec in expected.items():
        if not path.is_file():
            missing.append(rec['path'])
            continue
        if path.stat().st_size != rec['bytes']:
            changed.append((rec['path'], 'size %d, expected %d' % (path.stat().st_size, rec['bytes'])))
        elif not options.quick and sha256(path) != rec['sha256']:
            changed.append((rec['path'], 'SHA-256 differs'))
        done += rec['bytes']
        if time.monotonic() - last > 10:
            last = time.monotonic()
            print('  checked %.1f of %.1f GB' % (done / 1e9, total / 1e9), flush=True)
    extra = sorted(str(p.relative_to(mirror)) for p in mirror.rglob('*')
                   if p.is_file() and p.resolve() not in expected)
    risky = [p for p in extra if Path(p).suffix.lower() in RISKY]

    print('\nFiles listed: %d   missing: %d   changed: %d   extra: %d (risky types: %d)   %.0f s'
          % (len(records), len(missing), len(changed), len(extra), len(risky), time.monotonic() - start))
    for path, why in changed[:50]:
        print('CHANGED  %s  (%s)' % (path, why))
    for path in risky[:50]:
        print('EXTRA!   %s' % path)
    for path in [p for p in extra if p not in risky][:50]:
        print('extra    %s' % path)
    for path in missing[:20]:
        print('missing  %s' % path)
    if changed or extra:
        print('\nRESULT: the mirror differs from the published snapshot. Do not run it.')
        return 1
    if missing:
        print('\nRESULT: nothing was altered, but %d files are missing (the game may not load).' % len(missing))
        return 0
    print('\nRESULT: OK. Every file matches the snapshot%s.' % (' (sizes only)' if options.quick else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
