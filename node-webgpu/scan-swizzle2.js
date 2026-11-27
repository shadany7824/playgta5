const fs=require('fs'),path=require('path');
const d='E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
const files=fs.readdirSync(d).filter(f=>f.endsWith('.wgsl'));
const isW=c=>c==='x'||c==='y'||c==='z'||c==='w';
const idx=c=>'xyzw'.indexOf(c);
let total=0, oob=0, lvalue=0, dupAfter=0; const oobEx=[],lvEx=[];
for(const f of files){
  const c=fs.readFileSync(path.join(d,f),'utf8');
  for(let i=0;i<c.length-3;i++){
    if(c[i]!=='.') continue;
    let j=i+1; while(j<c.length && isW(c[j])) j++;
    const a=c.slice(i+1,j); if(a.length<2||a.length>4) continue;
    if(c[j]!=='.') continue;
    let k=j+1; while(k<c.length && isW(c[k])) k++;
    const b=c.slice(j+1,k); if(b.length<1||b.length>4) continue;
    if(k<c.length && /[A-Za-z0-9_]/.test(c[k])) continue;
    total++;
    // compose: composed[t] = a[ idx(b[t]) ]
    let comp=''; let bad=false;
    for(const ch of b){ const p=idx(ch); if(p>=a.length){bad=true;break;} comp+=a[p]; }
    if(bad){ oob++; if(oobEx.length<10) oobEx.push(f+' '+a+'.'+b); }
    // duplicate components in composed => unsafe as lvalue
    if(new Set(comp).size!==comp.length) dupAfter++;
    // assignment target? next non-space char is '=' and not '=='
    let m=k; while(m<c.length && /\s/.test(c[m])) m++;
    if(c[m]==='=' && c[m+1]!=='='){ lvalue++; if(lvEx.length<10) lvEx.push(f+' '+a+'.'+b+' ='); }
  }
}
console.log('total:',total);
console.log('out-of-range compose (invalid WGSL anyway):',oob, oobEx);
console.log('composed has duplicate components:',dupAfter);
console.log('chained swizzle as ASSIGNMENT target:',lvalue, lvEx);
