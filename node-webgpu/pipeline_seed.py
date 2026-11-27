import json, sys, re, collections

# jsonl -> dedup -> seed json array (format: JSON array of recipe objects, same as worker loader expects)
src, dst = sys.argv[1], sys.argv[2]
seen, out = set(), []
for line in open(src, encoding='utf-8', errors='replace'):
    line = line.strip()
    if not line:
        continue
    rc = json.loads(line)
    key = json.dumps(rc, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    out.append(rc)
json.dump(out, open(dst, 'w', encoding='utf-8'))
print(f'wrote {len(out)} unique recipes -> {dst}')
