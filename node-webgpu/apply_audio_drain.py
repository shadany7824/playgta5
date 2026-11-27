# STEP-1b: implement the browser's AudioWorklet consumer in Node.
# wasm_audio_publish_js(ring,capacity) early-returns on Node, so the engine's audio ring is never drained.
# Browser worklet: hdr Int32Array(buffer,ring,8) = [write,read,capacity,heartbeat,peak,...]; PCM interleaved LR at ring+64.
import shutil
g = r'E:\gta\playgta5\node-webgpu\game-node.js'
shutil.copyfile(g, g + '.bak-step1-audio')
s = open(g, encoding='utf-8', errors='replace').read()
old = ('function wasm_audio_publish_js(ring,capacity){if(typeof process!=="undefined"&&process.versions&&process.versions.node)return;'
       'postMessage({audio:{memory:wasmMemory,ring:Number(ring),capacity}})}')
new = ('function wasm_audio_publish_js(ring,capacity){'
       'if(typeof process!=="undefined"&&process.versions&&process.versions.node){'
       'try{const r=Number(ring),c=Number(capacity);'
       'globalThis.__audioRing=r;globalThis.__audioCap=c;'
       'const hdr=new Int32Array(wasmMemory.buffer,r,8);'
       'if(globalThis.__audioTimer)clearInterval(globalThis.__audioTimer);'
       'globalThis.__audioTimer=setInterval(()=>{try{'
       'const read=Atomics.load(hdr,1),write=Atomics.load(hdr,0);'
       'const avail=(write-read)>>>0;if(!avail)return;'
       'Atomics.store(hdr,1,(read+avail)|0);Atomics.add(hdr,3,1);'
       '}catch(e){}},10);'
       'globalThis.__diag&&globalThis.__diag("AUDIO ring="+r+" cap="+c);'
       '}catch(e){globalThis.__diag&&globalThis.__diag("AUDIO err "+e.message);}'
       'return;}'
       'postMessage({audio:{memory:wasmMemory,ring:Number(ring),capacity}})}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('APPLIED audio drain fix')
