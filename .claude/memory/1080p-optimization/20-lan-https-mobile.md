# 20 — LAN HTTPS server for mobile (2026-11-21)

## What was changed
- `serve_local.py` (backup `serve_local.py.bak-lan-20261121`): added `--lan` (bind `0.0.0.0`), `--cert`, `--key` (TLS), `ssl` import.
- Self-signed cert generated with Git's OpenSSL: `lan-cert/cert.pem`, `lan-cert/key.pem` (CN/SAN = 192.168.1.35, localhost, 365 days).
- Server restarted detached: `python serve_local.py --lan --cert ... --key ... --port 8000`, PID 10392, listening on `0.0.0.0:8000`.

## Verified
- `curl -k -I https://192.168.1.35:8000/__support/` → 200 with COOP same-origin / COEP require-corp / CORP same-origin.
- `curl -k -I https://192.168.1.35:8000/b/8b0b5899ed/game.wasm` → 200, 63,201,802 bytes, correct headers.
- Touch overlay added separately (note 19).

## Phone URL
`https://192.168.1.35:8000/?touch=1&low=1&res=800x450&fps=30&slots=5`

Phone must be on same Wi-Fi, Chrome Android 133+ (WebGPU + Memory64). Self-signed cert will show a warning — proceed/install cert. iPhone Safari: no Memory64, likely won't run.

## Blocker
Windows Firewall has all profiles enabled; adding inbound rule for TCP 8000 failed with "Access denied" (needs admin). If phone can't connect, run as admin:
`New-NetFirewallRule -DisplayName 'GTA5 LAN 8000' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private`
