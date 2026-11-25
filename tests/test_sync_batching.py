"""Bound cloud writes during continuous activity; preserve immediate local durability."""
from pathlib import Path
import os,shutil,copy
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];backend={};writes=[];reads=[];errors=[]
def cloud(route):
 path=route.request.url.split('https://test.supabase.co',1)[1]
 if path.startswith('/rest/v1/word_progress'):
  reads.append(path);route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend.update(revision=body['expected_revision']+1,payload=body['new_payload']);writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);ctx=b.new_context();ctx.route('https://batch.test/**',lambda r:r.fulfill(content_type='text/html',body=(ROOT/'index.html').read_text()));ctx.route('https://test.supabase.co/**',cloud);p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.clock.install();p.goto('https://batch.test/')
 p.evaluate("cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};loginCloud({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}})");p.wait_for_function('cloudReady&&!cloudBusy')
 count=len(writes)
 for i in range(5):
  p.evaluate("i=>{state.cards[0].fields[2]='change '+i;persist()}",i)
  assert p.evaluate("JSON.parse(localStorage.getItem(activeStorageKey)).cards[0].fields[2]")=='change '+str(i)
  p.clock.fast_forward(1990)
  assert len(writes)==count
 p.clock.fast_forward(50);p.wait_for_function('!cloudBusy');assert len(writes)==count+1 and backend['payload']['cards'][0]['fields'][2]=='change 4'
 print('PASS: five continuous changes are durable locally immediately and produce one complete cloud write within ten seconds')
 count=len(writes);before=len(reads)
 p.evaluate('persist();persist();persist()');p.clock.fast_forward(49000);assert len(writes)==count and len(reads)==before
 p.clock.fast_forward(2000);p.wait_for_function('!cloudBusy');assert len(reads)==before+1 and 'select=revision&' in reads[-1] and len(writes)==count
 print('PASS: unchanged local saves make no extra requests; polling uses revision only at the sixty-second interval')
 p.evaluate("state.cards[0].fields[2]='leave now';persist();Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))");p.wait_for_function('!cloudBusy');assert backend['payload']['cards'][0]['fields'][2]=='leave now'
 before=len(reads);p.clock.fast_forward(120000);assert len(reads)==before
 assert not errors,errors;print('PASS: leaving the page attempts to flush pending changes; hidden pages stop polling');b.close()
