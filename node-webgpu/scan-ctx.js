const fs=require('fs'),path=require('path');
const d='E:/gta/playgta5/mirror/playgta5.com/b/8b0b5899ed/shaders';
const files=fs.readdirSync(d).filter(f=>f.endsWith('.wgsl'));
const want=['.xy.xyxx','.xyxx.xy','.xyz.xyzx','.wwww.w'];
const shown={};
for(const f of files){
  const c=fs.readFileSync(path.join(d,f),'utf8');
  for(const w of want){
    if(shown[w]) continue;
    const i=c.indexOf(w);
    if(i>=0){ shown[w]=f+' :: '+JSON.stringify(c.slice(Math.max(0,i-70), i+w.length+30)); }
  }
  if(Object.keys(shown).length===want.length) break;
}
for(const w of want) console.log(w+'\n  '+(shown[w]||'not found')+'\n');
