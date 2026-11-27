lines = open(r'E:\Malik\game\game.dcmp', encoding='utf-8', errors='replace').readlines()
start = 1601500
end = None
for i in range(start, min(start + 20000, len(lines))):
    if lines[i].startswith('function ') and i > 1601600:
        end = i
        break
print('function range', start + 1, 'to', end + 1)
import re
pat = re.compile(r'AtomicLoad|AtomicStore|AtomicAdd|sysIpc|wasm_wait|Displayf|CallFunc|Sleep|Thread|fiDevice|Open\(|LoadBank|Mount|15938|15939|195667')
count = 0
for i in range(start, end + 1):
    line = lines[i].rstrip()
    if pat.search(line):
        print(i + 1, line[:170])
        count += 1
        if count > 400:
            print('...truncated')
            break
