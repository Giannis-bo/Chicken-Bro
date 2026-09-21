'use strict';
// This module is deliberately independent of the application runtime and credentials.
const net = require('node:net');
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = '/opt/chickenbro-candidates/poe2-20260918';
const LIMITS = Object.freeze({timeout:60000, response:2*1024*1024, total:8*1024*1024, request:4096});
const REQUIRED = ['GetRoleInfo','GetEquipments','GetSkills','GetTalentTree','GetJewels'];
const PROFILE = '/api/v1/wegame.pallas.poe2.Profile/';
const BASE = '/api/v1/wegame.pallas.poe2.Poe2BaseInfo/BtGetBase';
const CODES = new Set(['SOURCE_UNAVAILABLE','AUTH_REQUIRED','RATE_LIMITED','INCOMPLETE']);
const error = code => new Error(code);

function canonicalURL(value) {
  return typeof value === 'string' && value.length <= 2048 && /^https:\/\/www\.wegame\.com\.cn\/helper\/poe2\/#\/share\/[A-Za-z0-9_-]+$/.test(value);
}
function allowedRequest(value, type) {
  try {
    const u = new URL(value);
    if (u.protocol !== 'https:' || u.username || u.password || (u.port && u.port !== '443')) return false;
    if(u.hostname === 'wegame.gtimg.com' && ['script','stylesheet'].includes(type)) {
      return /^\/g\.2002052-r\.4de9d\/helper\/poe2\/assets\/[A-Za-z0-9_.-]+\.(js|css)$/.test(u.pathname) || [
        '/g.55555-r.c4663/lib/vue/latest/dist/vue.runtime.esm-browser.prod.js',
        '/g.55555-r.c4663/lib/wegame-web-sdk/1.1.4/dist/index.mjs',
        '/g.55555-r.c4663/lib/wg-ui/0.2.12/theme-builtin/wg-ui.css',
      ].includes(u.pathname);
    }
    if (u.hostname !== 'www.wegame.com.cn') return false;
    if (u.pathname === '/helper/poe2/' && type === 'document') return true;
    if (/^\/helper\/poe2\/assets\/[A-Za-z0-9_.-]+\.(js|css)$/.test(u.pathname) && ['script','stylesheet'].includes(type)) return true;
    if (['fetch','xhr'].includes(type) && (REQUIRED.some(n=>u.pathname===PROFILE+n) || u.pathname===BASE)) return true;
    return false;
  } catch { return false; }
}

class Budget {
  constructor(){ this.sizes=new Map(); this.total=0; }
  add(id, bytes, necessary){
    const next=(this.sizes.get(id)||0)+bytes;
    if (next>LIMITS.response || (necessary && this.total+bytes>LIMITS.total)) throw error('INCOMPLETE');
    this.sizes.set(id,next); if(necessary)this.total+=bytes;
  }
}
class Gate {
  constructor(enabled=true){this.enabled=enabled;this.active=new Set();}
  acquire(owner){
    if(!this.enabled)throw error('SOURCE_UNAVAILABLE');
    if(this.active.size>=2 || this.active.has(owner))throw error('RATE_LIMITED');
    this.active.add(owner); return ()=>this.active.delete(owner);
  }
}
const sensitiveKey = /openid|role_?id|account|share|token|cookie|authorization|request|raw|url|icon|image/i;
const ITEM_KEYS = new Set(('baseType descrText explicitMods implicitMods enchantMods craftedMods fracturedMods runeMods bondedMods scourgeMods crucibleMods utilityMods flavourText frameType frameTypeId identified ilvl inventoryId league name properties rarity requirements typeLine corrupted doubleCorrupted duplicated split mirrored quality sockets socketedItems socket support gemSkill gemSockets gemTabs secDescrText supportGemRequirements weaponRequirements group type displayMode values description pages stats text value values_formats des mod_descriptions display_name radius jewel grantedStrength grantedDexterity grantedIntelligence id level enabled crafted desecrated flags fractured mutated grantedSkills skillName suffix stackSize maxStackSize').split(' '));
const DISPLAY_KEYS = new Set(['h','w','x','y','verified','realm','iconTierText','gemBackground']);
function secretValues(value, output=new Set()) {
  if(Array.isArray(value))value.forEach(v=>secretValues(v,output));
  else if(value && typeof value==='object')for(const [k,v] of Object.entries(value)){
    if(sensitiveKey.test(k) && typeof v==='string' && v.length>=4)output.add(v);
    else secretValues(v,output);
  }
  return output;
}
function scrub(value, secrets, depth=0, gaps=new Set()) {
  if(depth>20)throw error('INCOMPLETE');
  if(typeof value==='string') {
    if(value.length>16384)throw error('INCOMPLETE');
    if(/(?:https?:\/\/|openid|sharetoken|share_code|authorization|cookie)/i.test(value) || [...secrets].some(s=>value.includes(s)))return '';
    return value;
  }
  if(value===null || typeof value==='boolean' || (typeof value==='number' && Number.isFinite(value)))return value;
  if(Array.isArray(value))return value.map(v=>scrub(v,secrets,depth+1,gaps));
  if(value && typeof value==='object'){
    for(const key of Object.keys(value))if(!ITEM_KEYS.has(key)&&!DISPLAY_KEYS.has(key)&&!sensitiveKey.test(key))gaps.add('unknown_item_fields');
    return Object.fromEntries(Object.entries(value).filter(([k])=>ITEM_KEYS.has(k)&&!sensitiveKey.test(k)).map(([k,v])=>[k,scrub(v,secrets,depth+1,gaps)]));
  }
  throw error('INCOMPLETE');
}
function normalizeCapture(capture, fetchedAt=new Date().toISOString(), privateValues=[]) {
  for(const name of REQUIRED) {
    const response=capture[name];
    if(!response || response.result?.error_code !== 0)throw error('INCOMPLETE');
  }
  const r=capture.GetRoleInfo.role, t=capture.GetTalentTree.talent_tree;
  if(!r || typeof r.name!=='string' || !Number.isInteger(r.level) || !t || !Array.isArray(t.hashes) || !t.hashes.every(Number.isInteger) || !Array.isArray(capture.GetEquipments.equipments) || !Array.isArray(capture.GetSkills.skills))throw error('INCOMPLETE');
  // Expand supported encoded structures before collecting any secret values;
  // those values can also occur in role/equipment strings outside the payload.
  let j=capture.GetJewels.jewel_data;
  if(typeof j==='string' && j.trim()) {try{j=JSON.parse(j);}catch{throw error('INCOMPLETE');}}
  const secrets=secretValues(capture); secretValues(j,secrets);
  privateValues.filter(Boolean).forEach(v=>secrets.add(v));
  const gaps=new Set(), sanitize=value=>scrub(value,secrets,0,gaps);
  const role={}; for(const k of ['name','level','class_id','class_name','league_id'])if(r[k]!==undefined)role[k]=sanitize(r[k]);
  const passives={hashes:t.hashes, jewel_slots:{},skill_overrides:{},specialisations:{},quest_stats:[]};
  for(const [key,v] of Object.entries(t.jewel_data||{}))if(/^\d+$/.test(key))passives.jewel_slots[key]=sanitize(v);
  for(const [key,v] of Object.entries(t.skill_overrides||{}))if(/^\d+$/.test(key))passives.skill_overrides[key]=sanitize(v);
  for(const k of ['set1','set2'])if(Array.isArray(t.specialisations?.[k])&&t.specialisations[k].every(Number.isInteger))passives.specialisations[k]=t.specialisations[k];
  if(Array.isArray(t.quest_stats))passives.quest_stats=sanitize(t.quest_stats);
  let jewels={status:'missing'};
  if(Array.isArray(j) && j.length && j.every(item=>item?.jewel && typeof item.jewel==='object'))jewels={status:'present',items:sanitize(j)};
  else if(Array.isArray(j) && j.length)gaps.add('unknown_jewel_structure');
  else if(j && !Array.isArray(j))throw error('INCOMPLETE');
  const snapshot={schema_version:1,role,equipment:sanitize(capture.GetEquipments.equipments),skills:{items:sanitize(capture.GetSkills.skills),base_info:[]},passives,jewels,source:{provider:'wegame',fetched_at:fetchedAt,source_updated_at:null}};
  if(capture.BtGetBase?.result?.error_code===0 && Array.isArray(capture.BtGetBase.base_list))snapshot.skills.base_info=sanitize(capture.BtGetBase.base_list);
  snapshot.source.schema_gaps=[...gaps].sort();
  snapshot.source.snapshot_hash=crypto.createHash('sha256').update(JSON.stringify({...snapshot,source:{provider:'wegame',schema_gaps:snapshot.source.schema_gaps}})).digest('hex');
  return snapshot;
}

async function finishCapture({pending,stop,failure,delay=500}) {
  await new Promise(resolve=>setTimeout(resolve,delay));
  stop();
  await Promise.allSettled([...pending]);
  if(failure())throw error(failure());
}

async function capturePage(url) {
  if(!canonicalURL(url))throw error('SOURCE_UNAVAILABLE');
  const {chromium}=require(ROOT+'/runtime/browser/node_modules/playwright');
  const browser=await chromium.launch({executablePath:ROOT+'/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',headless:true,args:['--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--disable-quic','--disable-features=WebRtcHideLocalIpsWithMdns'],env:{PATH:'/usr/bin:/bin',HOME:'/tmp',LD_LIBRARY_PATH:ROOT+'/runtime/browser/root/usr/lib/x86_64-linux-gnu'}});
  try {
    const context=await browser.newContext({serviceWorkers:'block',acceptDownloads:false});
    const page=await context.newPage();
    await context.addInitScript(() => {
      Object.defineProperty(window,'open',{value:()=>null,writable:false,configurable:false});
      for(const key of ['Worker','SharedWorker'])Object.defineProperty(window,key,{value:class {constructor(){throw new Error('disabled');}},writable:false,configurable:false});
    });
    page.on('popup',p=>p.close());
    await page.routeWebSocket('**/*',ws=>ws.close());
    const cdp=await context.newCDPSession(page), budget=new Budget(), captured={};
    let failed=null,accepting=true;
    const pending=new Set();
    await cdp.send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'},{urlPattern:'*',requestStage:'Response'}]});
    const handle=async event=>{
      const {requestId,request,responseStatusCode,responseHeaders=[]}=event;
      if(!allowedRequest(request.url,event.resourceType.toLowerCase())) {
        await cdp.send('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'}).catch(()=>{});
        return;
      }
      if(!responseStatusCode && !event.responseErrorReason) {
        await cdp.send('Fetch.continueRequest',{requestId}).catch(()=>{});
        return;
      }
      try {
        const pathname=new URL(request.url).pathname;
        const name=pathname.startsWith(PROFILE)?pathname.slice(PROFILE.length):pathname===BASE?'BtGetBase':null;
        if(responseStatusCode===401 || responseStatusCode===403)throw error('AUTH_REQUIRED');
        if(responseStatusCode===429)throw error('RATE_LIMITED');
        if(responseStatusCode>=300 && responseStatusCode<400){await cdp.send('Fetch.continueResponse',{requestId});return;}
        if(!responseStatusCode || responseStatusCode>=400)throw error(name?'INCOMPLETE':'SOURCE_UNAVAILABLE');
        const headerSize=Number(responseHeaders.find(h=>h.name.toLowerCase()==='content-length')?.value||0);
        if(headerSize>LIMITS.response)throw error('INCOMPLETE');
        const {stream}=await cdp.send('Fetch.takeResponseBodyAsStream',{requestId});
        const chunks=[];
        try {while(true){const part=await cdp.send('IO.read',{handle:stream,size:65536});const buffer=Buffer.from(part.data,part.base64Encoded?'base64':'utf8');budget.add(requestId,buffer.length,!!name);chunks.push(buffer);if(part.eof)break;}}
        finally{await cdp.send('IO.close',{handle:stream}).catch(()=>{});}
        const body=Buffer.concat(chunks);
        if(name){try{captured[name]=JSON.parse(body.toString('utf8'));}catch{throw error('INCOMPLETE');}}
        await cdp.send('Fetch.fulfillRequest',{requestId,responseCode:responseStatusCode,responseHeaders:responseHeaders.filter(h=>!['content-encoding','content-length','transfer-encoding','set-cookie'].includes(h.name.toLowerCase())),body:body.toString('base64')});
      } catch(e){failed=CODES.has(e.message)?e.message:'INCOMPLETE';await cdp.send('Fetch.failRequest',{requestId,errorReason:'Aborted'}).catch(()=>{});}
    };
    cdp.on('Fetch.requestPaused',event=>{
      if(!accepting){cdp.send('Fetch.failRequest',{requestId:event.requestId,errorReason:'Aborted'}).catch(()=>{});return;}
      const work=handle(event).catch(()=>{failed=failed||'INCOMPLETE';});
      pending.add(work);work.finally(()=>pending.delete(work));
    });
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
    const start=Date.now();
    while(!REQUIRED.every(n=>captured[n]) && !failed && Date.now()-start<45000)await new Promise(r=>setTimeout(r,100));
    if(failed)throw error(failed);
    // BtGetBase is optional; allow already-started natural requests to finish.
    await finishCapture({pending,stop:()=>{accepting=false;},failure:()=>failed});
    return normalizeCapture(captured,new Date().toISOString(),[url,url.split('/').at(-1)]);
  } finally {await browser.close();}
}

function runIsolatedJob(request, timeout=LIMITS.timeout, workerFile=__filename) {
  return new Promise(resolve=>{
    const supervisor=spawn('/usr/bin/python3',[__dirname+'/poe2_source_supervisor.py',String(timeout),process.execPath,workerFile],{stdio:['pipe','pipe','ignore'],env:{PATH:'/usr/bin:/bin',HOME:'/tmp',LANG:'C.UTF-8'}});
    let output=Buffer.alloc(0),done=false;
    const fail={ok:false,code:'SOURCE_UNAVAILABLE',retryable:true};
    const finish=result=>{if(done)return;done=true;clearTimeout(timer);resolve(result);};
    // The subreaper owns cleanup. Gate release waits for its exit, never just
    // for the Node worker's exit or a successful result message.
    const timer=setTimeout(()=>supervisor.kill('SIGTERM'),timeout);
    supervisor.stdout.on('data',chunk=>{output=Buffer.concat([output,chunk]);if(output.length>LIMITS.total){output=Buffer.alloc(0);supervisor.kill('SIGTERM');}});
    supervisor.on('error',()=>finish(fail));
    supervisor.on('close',()=>{try{finish(JSON.parse(output.toString('utf8')));}catch{finish(fail);}});
    supervisor.stdin.on('error',()=>{});
    supervisor.stdin.end(JSON.stringify({canonical_url:request.canonical_url})+'\n');
  });
}

function startServer({fd=3,path,enabled=process.env.POE2_SOURCE_ENABLED==='1',runner=runIsolatedJob}={}) {
  const gate=new Gate(enabled);
  const server=net.createServer(connection=>{
    let input=Buffer.alloc(0),started=false;
    connection.setTimeout(3000,()=>connection.destroy());
    connection.on('error',()=>{});
    connection.on('data',async chunk=>{
      if(started){connection.destroy();return;}
      input=Buffer.concat([input,chunk]);
      if(input.length>LIMITS.request){connection.destroy();return;}
      if(!input.includes(10))return;
      started=true;connection.setTimeout(63000,()=>connection.destroy());
      let release;
      try {
        const request=JSON.parse(input.toString('utf8'));
        if(Object.keys(request).sort().join(',')!=='canonical_url,owner_key,version'||request.version!==1||!canonicalURL(request.canonical_url)||!/^[a-f0-9]{64}$/.test(request.owner_key))throw error('SOURCE_UNAVAILABLE');
        release=gate.acquire(request.owner_key);
        const result=await runner(request);
        connection.end(JSON.stringify(result)+'\n');
      }catch(e){connection.end(JSON.stringify({ok:false,code:CODES.has(e.message)?e.message:'SOURCE_UNAVAILABLE'})+'\n');}
      finally{if(release)release();}
    });
  });
  server.maxConnections=16;
  server.listen(path?{path}:{fd});
  return server;
}
if(require.main===module) {
  if(process.argv[2]==='--capture-stdio') {
    let input='';process.stdin.on('data',chunk=>input+=chunk);
    process.stdin.on('end',async()=>{
      try{const request=JSON.parse(input);process.stdout.write(JSON.stringify({ok:true,snapshot:await capturePage(request.canonical_url)})+'\n');}
      catch(e){process.stdout.write(JSON.stringify({ok:false,code:CODES.has(e.message)?e.message:'SOURCE_UNAVAILABLE'})+'\n');}
    });
  }
  else if(process.env.LISTEN_PID===String(process.pid)&&process.env.LISTEN_FDS==='1')startServer();
  else process.exitCode=1;
}
module.exports={allowedRequest,canonicalURL,normalizeCapture,Budget,Gate,LIMITS,capturePage,runIsolatedJob,startServer,finishCapture};
