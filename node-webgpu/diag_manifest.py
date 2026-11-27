g = r'E:\gta\playgta5\node-webgpu\game-node.js'
s = open(g, encoding='utf-8', errors='replace').read()
old = 'function wasm_httpfs_manifest_js(buf,cap){if(typeof XMLHttpRequest==="undefined")return-1;let bytes=globalThis.__httpfsManifest;if(bytes===undefined){bytes=null;try{const x=new XMLHttpRequest;x.open("GET",self.location.origin+"/data/manifest.json",false);x.send();if(x.status===200)bytes=(new TextEncoder).encode(x.responseText)}catch(e){console.error("httpfs: manifest failed: "+e)}globalThis.__httpfsManifest=bytes}if(bytes===null)return-1;if(cap>bytes.length){(growMemViews(),HEAPU8).set(bytes,Number(buf));(growMemViews(),HEAPU8)[Number(buf)+bytes.length]=0;globalThis.__httpfsManifest=undefined}return bytes.length}'
new = ('function wasm_httpfs_manifest_js(buf,cap){globalThis.__diag&&globalThis.__diag("MANIFEST called buf="+buf+" cap="+cap);'
       'if(typeof XMLHttpRequest==="undefined"){globalThis.__diag&&globalThis.__diag("MANIFEST no XHR");return-1;}'
       'let bytes=globalThis.__httpfsManifest;if(bytes===undefined){bytes=null;try{const x=new XMLHttpRequest;x.open("GET",self.location.origin+"/data/manifest.json",false);x.send();globalThis.__diag&&globalThis.__diag("MANIFEST xhr status="+x.status+" len="+(x.responseText||"").length);if(x.status===200)bytes=(new TextEncoder).encode(x.responseText)}catch(e){console.error("httpfs: manifest failed: "+e);globalThis.__diag&&globalThis.__diag("MANIFEST err "+e.message)}globalThis.__httpfsManifest=bytes}'
       'globalThis.__diag&&globalThis.__diag("MANIFEST bytes="+(bytes?bytes.length:"null"));'
       'if(bytes===null)return-1;if(cap>bytes.length){(growMemViews(),HEAPU8).set(bytes,Number(buf));(growMemViews(),HEAPU8)[Number(buf)+bytes.length]=0;globalThis.__httpfsManifest=undefined}return bytes.length}')
print('found:', old in s)
s = s.replace(old, new, 1)
open(g, 'w', encoding='utf-8', newline='').write(s)
print('ADDED manifest diag')
