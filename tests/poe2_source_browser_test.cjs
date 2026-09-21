const test = require('node:test');
const assert = require('node:assert/strict');
const { allowedRequest, canonicalURL, normalizeCapture, Budget, Gate, LIMITS, runIsolatedJob, startServer, finishCapture } = require('../server/poe2_source_browser.cjs');
const net = require('node:net');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const api = 'https://www.wegame.com.cn/api/v1/wegame.pallas.poe2.Profile/';
function fixture() { return {
  GetRoleInfo: {result:{error_code:0}, role:{name:'Example',level:94,class_id:1,class_name:'Warrior',league_id:'league',openid:'SECRET_OPENID',role_id:'SECRET_ROLE',account_name:'SECRET_ACCOUNT'},share_code:'SECRET_SHARE'},
  GetEquipments:{result:{error_code:0},equipments:[{baseType:'Sword',inventoryId:'Weapon',properties:[],openid:'SECRET_OPENID'}]},
  GetSkills:{result:{error_code:0},skills:[{baseType:'Attack',socketedItems:[]}]},
  GetTalentTree:{result:{error_code:0},talent_tree:{hashes:[12],jewel_data:{'12':{type:'Jewel'}},skill_overrides:{},specialisations:{set1:[],set2:[]}}},
  GetJewels:{result:{error_code:0},jewel_data:''},
}; }
test('canonical URL and every redirect reject private and unrelated URLs',()=>{
  assert(canonicalURL('https://www.wegame.com.cn/helper/poe2/#/share/abc'));
  for(const u of ['http://127.0.0.1/a','https://169.254.169.254/a','https://10.0.0.1/a','https://[::ffff:127.0.0.1]/a','https://www.wegame.com.cn.evil/a','https://u:p@www.wegame.com.cn/helper/poe2/']) assert(!allowedRequest(u,'document'));
  assert(allowedRequest(api+'GetRoleInfo','fetch'));
  assert(!allowedRequest(api+'GetSeasonCurrencySummary','fetch'));
  assert(!allowedRequest('https://receiver.tdm.qq.com/tdm/v1/kv','fetch'));
  assert(!allowedRequest('https://www.wegame.com.cn/helper/poe2/assets/../../other.js','script'));
});
test('missing jewels remain missing and all public values are sanitized',()=>{
  const f=fixture(); f.GetEquipments.equipments[0].name='SECRET_OPENID';
  const s=normalizeCapture(f,'2026-09-20T00:00:00.000Z');
  assert.equal(s.jewels.status,'missing'); assert(!('items' in s.jewels));
  assert(!('openid' in s.role)); assert(!JSON.stringify(s).includes('SECRET_'));
  assert.equal(s.passives.hashes[0],12);
});
test('R1 secrets inside encoded jewels are redacted across all snapshot fields',()=>{
  const f=fixture(), secret='PRIVATE_VALUE_123';
  f.GetJewels.jewel_data=JSON.stringify([{jewel:{openid:secret,name:secret}}]);
  f.GetRoleInfo.role.name=secret;f.GetEquipments.equipments[0].name=secret;
  assert(!JSON.stringify(normalizeCapture(f)).includes(secret));
});
test('R3 late completion-window failure is returned after handlers settle',async()=>{
  let failed=null,accepting=true;
  const pending=new Set();
  const late=new Promise(resolve=>setTimeout(()=>{failed='RATE_LIMITED';resolve();},30));
  pending.add(late);late.finally(()=>pending.delete(late));
  await assert.rejects(()=>finishCapture({pending,stop:()=>{accepting=false;},failure:()=>failed,delay:5}),/RATE_LIMITED/);
  assert.equal(accepting,false);
});
test('R2 crashed worker detached child is reaped without disrupting another job',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'poe2-crash-'));
  const worker=path.join(dir,'crash.cjs'),record=path.join(dir,'pid'),sibling=path.join(dir,'sibling.cjs');
  fs.writeFileSync(worker,`const {spawn}=require('node:child_process');const fs=require('node:fs');const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{detached:true,stdio:'ignore'});fs.writeFileSync(${JSON.stringify(record)},String(child.pid));process.exit(1);`);
  fs.writeFileSync(sibling,`setTimeout(()=>{process.stdout.write(JSON.stringify({ok:true,snapshot:{sibling:true}})+'\\n');},800);`);
  try{
    const other=runIsolatedJob({canonical_url:'unused'},2500,sibling);
    const result=await runIsolatedJob({canonical_url:'unused'},2000,worker);
    assert.equal(result.ok,false);
    const pid=Number(fs.readFileSync(record,'utf8'));
    assert.equal(fs.existsSync('/proc/'+pid),false);
    assert.equal((await other).snapshot.sibling,true);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('missing or failed mandatory responses and malformed structures fail closed',()=>{
  for (const key of ['GetRoleInfo','GetEquipments','GetSkills','GetTalentTree','GetJewels']) {
    const f=fixture(); delete f[key]; assert.throws(()=>normalizeCapture(f),/INCOMPLETE/);
  }
  const f=fixture(); f.GetSkills.skills={}; assert.throws(()=>normalizeCapture(f),/INCOMPLETE/);
});
test('unknown gameplay fields and jewel structures retain explicit schema gaps',()=>{
  const f=fixture();f.GetEquipments.equipments[0].futureMechanic={damage:3};f.GetJewels.jewel_data=JSON.stringify([{unexpected:'value'}]);
  const s=normalizeCapture(f);assert.equal(s.jewels.status,'missing');
  assert.deepEqual(s.source.schema_gaps,['unknown_item_fields','unknown_jewel_structure']);
});
test('response budget enforces 2MiB individual and 8MiB aggregate',()=>{
  assert.equal(LIMITS.timeout,60000);
  const b=new Budget(); assert.throws(()=>b.add('a',2*1024*1024+1,true),/INCOMPLETE/);
  const c=new Budget(); for(let i=0;i<4;i++)c.add(String(i),2*1024*1024,true);
  assert.throws(()=>c.add('f',1,true),/INCOMPLETE/);
});
test('global two, per-owner one, release, and disable switch',()=>{
  const g=new Gate(); const release=g.acquire('a');
  assert.throws(()=>g.acquire('a'),/RATE_LIMITED/); const releaseB=g.acquire('b');
  assert.throws(()=>g.acquire('c'),/RATE_LIMITED/); release(); const releaseC=g.acquire('c');
  releaseB(); releaseC(); assert.equal(g.active.size,0);
  assert.throws(()=>new Gate(false).acquire('a'),/SOURCE_UNAVAILABLE/);
});
test('actual IPC limits concurrent requests and rejects arbitrary options',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'poe2-ipc-')), sock=path.join(dir,'ipc.sock');
  const pending=[];
  const server=startServer({path:sock,enabled:true,runner:()=>new Promise(resolve=>pending.push(resolve))});
  await new Promise(r=>server.on('listening',r));
  const call=(owner,extra={})=>new Promise((resolve,reject)=>{
    const connection=net.connect(sock,()=>connection.write(JSON.stringify({version:1,canonical_url:'https://www.wegame.com.cn/helper/poe2/#/share/test',owner_key:owner.repeat(64),...extra})+'\n'));
    let body='';connection.on('data',c=>body+=c);connection.on('error',reject);connection.on('end',()=>resolve(JSON.parse(body)));
  });
  try {
    const first=call('a');while(pending.length<1)await new Promise(r=>setTimeout(r,5));
    assert.equal((await call('a')).code,'RATE_LIMITED');
    const second=call('b');while(pending.length<2)await new Promise(r=>setTimeout(r,5));
    assert.equal((await call('c')).code,'RATE_LIMITED');
    assert.equal((await call('d',{headers:{Cookie:'injected'}})).code,'SOURCE_UNAVAILABLE');
    pending.splice(0).forEach(done=>done({ok:true,snapshot:{}}));
    assert((await first).ok);assert((await second).ok);
  }finally{await new Promise(r=>server.close(r));fs.rmSync(dir,{recursive:true,force:true});}
});
test('deadline kills a detached descendant process, not just node worker',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'poe2-deadline-'));
  const worker=path.join(dir,'hang.cjs'), record=path.join(dir,'pid');
  fs.writeFileSync(worker,`const {spawn}=require('node:child_process');const fs=require('node:fs');const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{detached:true,stdio:'ignore'});fs.writeFileSync(${JSON.stringify(record)},String(child.pid));setInterval(()=>{},1000);`);
  try{
    const started=Date.now();
    const result=await runIsolatedJob({canonical_url:'unused'},500,worker);
    assert.equal(result.retryable,true);assert(Date.now()-started<2000);
    const pid=Number(fs.readFileSync(record,'utf8'));await new Promise(r=>setTimeout(r,50));
    let alive=false;try{alive=!/^State:\s+Z/m.test(fs.readFileSync('/proc/'+pid+'/status','utf8'));}catch{}
    assert.equal(alive,false);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
