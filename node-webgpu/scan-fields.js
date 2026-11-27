const fs=require('fs'),path=require('path');
const d='E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
const files=fs.readdirSync(d).filter(f=>f.endsWith('.wgsl'));
const isW=c=>'xyzw'.includes(c);
let bad=[];
for(const f of files){
  const c=fs.readFileSync(path.join(d,f),'utf8');
  // struct fields: lines like "  name : type,"
  const re=/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/gm;
  let m;
  while((m=re.exec(c))){
    const n=m[1];
    if(n.length>=1 && n.length<=4 && [...n].every(isW)) bad.push(f+': '+n);
  }
}
console.log('struct/field names that are pure xyzw (risky):',bad.length);
bad.slice(0,20).forEach(x=>console.log('  '+x));
