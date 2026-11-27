const fs=require('fs'),path=require('path');
const d='E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
const files=fs.readdirSync(d).filter(f=>f.endsWith('.wgsl'));
const isW=c=>c==='x'||c==='y'||c==='z'||c==='w';
let total=0; const pat={}; const samples=[]; const byFile={};
for(const f of files){
  const c=fs.readFileSync(path.join(d,f),'utf8');
  for(let i=0;i<c.length-3;i++){
    if(c[i]!=='.') continue;
    let j=i+1; while(j<c.length && isW(c[j])) j++;
    const n1=j-(i+1); if(n1<2||n1>4) continue;
    if(c[j]!=='.') continue;
    let k=j+1; while(k<c.length && isW(c[k])) k++;
    const n2=k-(j+1); if(n2<1||n2>4) continue;
    // must be followed by non-ident char
    if(k<c.length && /[A-Za-z0-9_]/.test(c[k])) continue;
    const s=c.slice(i,k);
    total++; pat[s]=(pat[s]||0)+1;
    byFile[f]=(byFile[f]||0)+1;
    if(samples.length<20) samples.push(f+': '+s);
  }
}
console.log('total chained swizzle:',total);
console.log('distinct patterns:',Object.keys(pat).length);
console.log('top patterns:');
Object.entries(pat).sort((a,b)=>b[1]-a[1]).slice(0,30).forEach(([k,v])=>console.log('  '+v+'\t'+k));
console.log('files affected:',Object.keys(byFile).length,'of',files.length);
console.log('samples:'); samples.forEach(s=>console.log('  '+s));
