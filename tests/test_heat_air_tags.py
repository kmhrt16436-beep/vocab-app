"""Preset classification updates registered cards once without changing study data."""
from pathlib import Path
import copy,json,os,shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];pack=json.loads((ROOT/'study/heat-air/complete/cards.json').read_text());source=(ROOT/'index.html').read_text();errors=[];backend={};writes=[]
BASE='https://heat-air-tags.test/'
def cloud(route):
 path=route.request.url.split('https://test.supabase.co',1)[1]
 if path.startswith('/rest/v1/word_progress'):route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend.update(revision=body['expected_revision']+1,payload=body['new_payload']);writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
def strip_tags(value):
 value=copy.deepcopy(value)
 for c in value['cards']:c.pop('tags',None);c.pop('tagPresets',None)
 return value
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':390,'height':744});ctx.route(BASE+'**',lambda r:r.fulfill(status=200,content_type='text/html',body=source));ctx.route('https://test.supabase.co/**',cloud)
 p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE+'index.html')
 raw=p.evaluate("""cards=>{const x=initial();x.folders.push({id:'heat-air',name:'熱・空気 全件',kind:'general',deleted:false});x.cards=cards.map((row,i)=>{const c=card(row.fields,'heat-air');c.tags=['既存の分類'];delete c.tagPresets;c.stage=3;c.due=after(5);c.memory={lastReviewed:shiftDate(today(),-2),stability:7,difficulty:.4,reviews:5,successes:4,lapses:1,streak:2,scheduledDays:7,estimated:false};return c});const extra=card(['自分の別教科','答え','','','','',''],'english');delete extra.tagPresets;extra.due=after(5);x.cards.push(extra);x.session={date:today(),queue:[{id:x.cards[0].id,retry:true}],done:13,doneByFolder:{'heat-air':13},reviewCounts:{}};localStorage.setItem(KEY,JSON.stringify(x));return x}""",pack['cards'])
 p.reload();state=p.evaluate('state');assert strip_tags(state)==strip_tags(raw)
 counts=p.evaluate("Object.fromEntries(['熱分野','空気分野','テスト用'].map(t=>[t,state.cards.filter(c=>c.tags.includes(t)).length]))");assert counts=={'熱分野':142,'空気分野':156,'テスト用':218}
 assert all('既存の分類' in c['tags'] for c in state['cards'][:-1]);assert state['cards'][-1]['tags']==[];assert all(c['tagPresets']==['heat-air-subject-priority-v1'] for c in state['cards'][:-1]);assert not state['cards'][-1]['tagPresets']
 p.locator('#folderSelect').select_option('heat-air')
 for tag,count in counts.items():p.locator('#tagSelect').select_option(tag);assert p.evaluate('selectedCards().length')==count
 p.reload();assert p.evaluate('state')==state
 print('PASS: 298 existing cards classified into heat 142, air 156, test 218; custom tags and every field/ID/history/due/queue unchanged; no reload changes')
 # An explicit tag removal stays removed on reload, JSON round trip and a repeated CSV import.
 p.evaluate("for(const c of state.cards)c.tags=c.tags.filter(t=>t!=='テスト用');persist()");removed=p.evaluate('state');p.reload();assert p.evaluate('state')==removed
 p.evaluate("state=validate(JSON.parse(JSON.stringify(state)));persist()");assert p.evaluate('state')==removed
 p.evaluate("row=>{const c=card([...row.fields],'heat-air');state.cards.push(c);state=validate(state);persist();render()}",pack['cards'][0]);assert p.evaluate("state.cards.every(c=>!c.tags.includes('テスト用'))");assert p.evaluate('state.cards.length')==299
 print('PASS: removed preset tags stay removed after reload/import and duplicate reimport; no extra cards')
 # Cards imported later receive the preset without requiring a separate operation.
 p.evaluate("state=initial();state.folders.push({id:'heat-air',name:'熱空気',kind:'general',deleted:false});state.cards=[];state.session.queue=[];persist();render()")
 p.locator('[data-tab=data]').click();p.locator('#csvFolder').select_option('heat-air');p.locator('#csv').fill((ROOT/'study/heat-air/complete/all.csv').read_text(encoding='utf-8-sig'));p.locator('#importCsv').click()
 assert p.evaluate('state.cards.length')==298;assert p.evaluate("state.cards.filter(c=>c.tags.includes('テスト用')).length")==218
 print('PASS: seven-column CSV imports get all three preset classifications automatically')
 # An old v4 cloud payload without the preset must actually be rewritten once, not just rendered locally.
 backend.update(revision=1,payload=raw)
 p.evaluate("state=initial();state.cards=[];state.session.queue=[];cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};loginCloud({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}})")
 p.wait_for_function('cloudReady&&!cloudBusy');assert writes and sum('テスト用' in c['tags'] for c in backend['payload']['cards'])==218;assert strip_tags(backend['payload'])==strip_tags(raw)
 count=len(writes)
 for _ in range(3):p.evaluate('clearTimeout(cloudTimer);syncCloud()')
 assert len(writes)==count
 p.evaluate("for(const c of state.cards)c.tags=c.tags.filter(t=>t!=='テスト用');persist();clearTimeout(cloudTimer);syncCloud()")
 assert not any('テスト用' in c['tags'] for c in backend['payload']['cards'])
 print('PASS: cloud v4 is backfilled and saved once; subsequent sync preserves removals and does not repeat writes')
 assert not errors,errors;b.close()
