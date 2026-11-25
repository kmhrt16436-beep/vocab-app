'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const {createService, createAuthenticator, createLegacyReader} = require('../src/service');
const {createStore} = require('../src/store');
const A = '11111111-1111-4111-8111-111111111111', B = '22222222-2222-4222-8222-222222222222';
const ORIGIN = 'https://kmhrt16436-beep.github.io';
function payload(word = 'word') { return {version: 4, folders: [{id:'english',name:'英語',kind:'english',deleted:false}], cards: [{id: 'one',fields:[word,'名）意味','','例文','訳','',''],tags:['公式問題集9'],memory:{reviews:3}}], session: {date:'2026-11-26',queue:[]}}; }
function fakes() {
  const records = new Map(), files = new Map(); let sequence = 0, failCommit = false, race = false, time = Date.now();
  const fail = code => { throw Object.assign(new Error('storage failure'), {code}); };
  const container = {
    item: (_id, userId) => ({
      read: async () => ({resource: structuredClone(records.get(userId))}),
      replace: async (record, options) => {
        if (race) { race = false; records.get(userId)._etag = 'raced'; }
        if (options.accessCondition.condition !== records.get(userId)?._etag) fail(412);
        records.set(userId, {...record,_etag:String(++sequence)});
        if (failCommit) { failCommit = false; fail(503); }
      }
    }),
    items: {create: async record => { if (records.has(record.userId)) fail(409); records.set(record.userId, {...record,_etag:String(++sequence)}); }}
  };
  const blobs = {
    getBlockBlobClient: name => ({
      uploadData: async (bytes, options) => { if (files.has(name) && options.conditions.ifNoneMatch === '*') fail(412); files.set(name,{bytes:Buffer.from(bytes),time:new Date(time)}); },
      downloadToBuffer: async () => files.get(name)?.bytes || fail(404),
      deleteIfExists: async () => { files.delete(name); }
    }),
    listBlobsFlat: async function* () { for (const [name,file] of files) yield {name,properties:{lastModified:file.time}}; }
  };
  return {container,blobs,records,files,now:()=>time,advance:ms=>{time+=ms},setRace:()=>{race=true},failCommit:()=>{failCommit=true}};
}
function service(store, extra = {}) { return createService({store,authenticate:async token => {if(token==='a')return A;if(token==='b')return B;throw Object.assign(Error('expired'),{status:401})},origins:[ORIGIN],...extra}); }
function req(method='GET', data, token='a', query='', origin=ORIGIN) {
  const headers = {Authorization:'Bearer '+token};if(origin)headers.Origin=origin;
  return new Request('https://test.azurewebsites.net/api/state'+query,{method,headers,body:data===undefined?undefined:JSON.stringify(data)});
}
const body = reply => JSON.parse(reply.body);
test('private account separation, CAS conflict and metadata-only polling', async () => {
  const fake=fakes(),store=createStore(fake),run=service(store);
  assert.equal(body(await run(req())),null);
  assert.equal((await run(req('PUT',{expected_revision:0,new_payload:payload()}))).status,200);
  assert.equal(body(await run(req('GET',undefined,'b'))),null);
  assert.deepEqual(body(await run(req('GET',undefined,'a','?metadata=1'))),{revision:1});
  assert.equal(body(await run(req('GET',undefined,'a','?userId='+B))).revision,1);
  const result=body(await run(req()));assert.equal(result.payload.cards[0].tags[0],'公式問題集9');assert.equal(result.revision,1);
  const conflict=await run(req('PUT',{expected_revision:0,new_payload:payload('lost')}));assert.equal(conflict.status,409);assert.equal(body(conflict).code,'40001');
  assert.equal(body(await run(req())).payload.cards[0].fields[0],'word');
  assert.equal((await run(req('GET',undefined,'expired'))).status,401);
  assert.equal((await run(req('GET',undefined,'a','', 'https://evil.example'))).status,403);
  assert.equal((await run(req('OPTIONS'))).status,204);
  assert.equal((await run(req())).headers['Cache-Control'],'no-store');
});
test('photos >2MB round-trip byte-for-byte; image bytes are stored once across revisions', async () => {
  const fake=fakes(),store=createStore(fake),data=payload();
  data.cards[0].fields[6]='data:image/png;base64,'+Buffer.alloc(3*1024*1024,19).toString('base64');
  await store.save(A,0,data);assert.deepEqual((await store.read(A)).payload,data);
  const first=fake.records.get(A).blobName;
  data.cards[0].memory.reviews++;await store.save(A,1,data);
  assert.equal([...fake.files.keys()].filter(n=>n.includes('/images/')).length,1);
  assert.ok(Buffer.byteLength(JSON.stringify(fake.records.get(A)))<2048);
  fake.advance(2*86400000);await store.cleanup();assert.ok(!fake.files.has(first));assert.deepEqual((await store.read(A)).payload,data);
});
test('concurrent CAS leaves committed data intact; uncertain commit never deletes its blob', async () => {
  const fake=fakes(),store=createStore(fake);await store.save(A,0,payload());
  fake.setRace();await assert.rejects(store.save(A,1,payload('raced')),e=>e.conflict);
  assert.equal((await store.read(A)).payload.cards[0].fields[0],'word');
  fake.failCommit();await assert.rejects(store.save(A,1,payload('committed')));
  assert.equal((await store.read(A)).revision,2);assert.equal((await store.read(A)).payload.cards[0].fields[0],'committed');
});
test('parallel first-time imports commit only once and later Azure data always wins', async () => {
  const fake=fakes(),store=createStore(fake);let reads=0;
  const run=service(store,{fetchLegacy:async()=>{reads++;return payload('legacy')}});
  const results=await Promise.all([run(req()),run(req())]);assert.ok(results.every(r=>r.status===200));
  assert.equal((await store.read(A)).revision,1);
  await store.save(A,1,payload('Azure edited'));const count=reads;
  assert.equal(body(await run(req())).payload.cards[0].fields[0],'Azure edited');assert.equal(reads,count);
});
test('legacy import failure cannot be mistaken for an empty account', async () => {
  const fake=fakes(),run=service(createStore(fake),{fetchLegacy:async()=>{throw Error('offline')}});
  assert.equal((await run(req())).status,503);assert.equal(fake.records.size,0);
});
test('invalid JSON schema, internal references, invalid revisions, oversized bodies are rejected', async () => {
  const fake=fakes(),run=service(createStore(fake),{maxBytes:10000});
  for(const expected_revision of [-1,1.2,Number.MAX_SAFE_INTEGER])assert.equal((await run(req('PUT',{expected_revision,new_payload:payload()}))).status,400);
  const invalid=payload();invalid.cards[0].fields[6]='azure-image:v1:fake';
  assert.equal((await run(req('PUT',{expected_revision:0,new_payload:invalid}))).status,400);
  const large=payload('a'.repeat(11000));assert.equal((await run(req('PUT',{expected_revision:0,new_payload:large}))).status,413);
  assert.equal(fake.records.size,0);
});
test('token cache is bounded in time, expiry shortens it, revoked tokens fail refresh', async () => {
  let time=100000,requests=0,valid=true;const token='a.'+Buffer.from(JSON.stringify({exp:105})).toString('base64url')+'.signature';
  const auth=createAuthenticator({url:'https://test.supabase.co',key:'public',now:()=>time,fetchImpl:async()=>{requests++;return new Response(JSON.stringify(valid?{id:A}:{}),{status:valid?200:401})}});
  assert.equal(await auth(token),A);await auth(token);assert.equal(requests,1);
  time=106000;valid=false;await assert.rejects(auth(token),e=>e.status===401);assert.equal(requests,2);
});
test('legacy lookup forwards the user bearer, filters server-side user ID, never uses service role', async () => {
  let seen;const read=createLegacyReader({url:'https://test.supabase.co',key:'public',fetchImpl:async(url,options)=>{seen={url,options};return new Response(JSON.stringify([{payload:payload()}]))}});
  await read('user-token',A);assert.ok(seen.url.endsWith('user_id=eq.'+A));assert.equal(seen.options.headers.Authorization,'Bearer user-token');assert.equal(seen.options.headers.apikey,'public');
});

test('corrupted committed snapshots fail closed rather than returning partial data', async () => {
  const fake=fakes(),store=createStore(fake);await store.save(A,0,payload());
  fake.records.get(A).sha256='0'.repeat(64);
  await assert.rejects(store.read(A),/checksum mismatch/);
});
