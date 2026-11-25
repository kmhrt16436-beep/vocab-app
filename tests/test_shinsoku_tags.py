"""Explicitly tag remaining English cards, preserving official cards and reviews."""
from pathlib import Path
import copy,json,os,shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='https://shinsoku.test/';backend={};writes=[];errors=[]
def cloud(route):
 path=route.request.url.split('https://test.supabase.co',1)[1]
 if path.startswith('/rest/v1/word_progress'):route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend.update(revision=body['expected_revision']+1,payload=body['new_payload']);writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 def page():
  ctx=b.new_context(viewport={'width':390,'height':744});ctx.route(BASE+'**',lambda r:r.fulfill(content_type='text/html',body=(ROOT/'index.html').read_text()));ctx.route('https://test.supabase.co/**',cloud);p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));return p
 p=page();p.goto(BASE);assert not p.evaluate("state.cards.some(c=>c.tags.includes('神速リスニング'))")
 raw=p.evaluate("""()=>{state=initial();for(const c of state.cards){c.tags=['既存タグ'];c.stage=3;c.due=after(8);c.memory={lastReviewed:today(),stability:7,difficulty:.4,reviews:7,successes:6,lapses:1,streak:3,scheduledDays:7,estimated:false}}state.session.queue=[];state.session.done=4;state.session.doneByFolder={english:4};state.folders.push({id:'heat',name:'熱',kind:'general',deleted:false},{id:'other-english',name:'別の英語セット',kind:'vocabulary',deleted:false});const official=card(['book9','名）答え','','','','','']);official.tags=['公式問題集9','別のタグ'];official.due=after(8);state.cards.push(official);const removed=card(['edited official','名）答え','','','','','']);removed.tagPresets=[TOEIC9_PACK_ID];removed.due=after(8);state.cards.push(removed);const heat=card(['熱の問題','答え','','','','',''],'heat');heat.due=after(8);state.cards.push(heat);const other=card(['separate','答え','','','','',''],'other-english');other.due=after(8);state.cards.push(other);persist();return JSON.parse(JSON.stringify(state))}""")
 p.goto(BASE+'?organize=shinsoku-listening');p.wait_for_function("!shinsokuBusy&&!location.search.includes('organize=')")
 result=p.evaluate('state');expected=copy.deepcopy(raw)
 for c in expected['cards'][:5]:c['tags']=sorted(['既存タグ','神速リスニング'])
 assert result==expected
 assert p.locator('#tagSelect').input_value()=='神速リスニング' and '対象5枚' in p.locator('#shinsokuStatus').inner_text()
 p.locator('#shinsokuStudy').click();assert p.evaluate('selectedCards().length')==5
 p.goto(BASE+'?organize=shinsoku-listening');p.wait_for_function("!shinsokuBusy&&!location.search.includes('organize=')");assert p.evaluate('state')==expected
 p.reload();assert p.evaluate('state')==expected
 print('PASS: only non-official cards in English folder tagged; other tags, source text, photos, IDs, history, dates and session unchanged; official provenance and other subjects excluded; repeat/reload idempotent')
 backend.update(revision=3,payload=raw)
 p2=page();p2.add_init_script("""localStorage.setItem('daily-words-v1:cloud-config',JSON.stringify({url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'}));localStorage.setItem('daily-words-v1:cloud-auth',JSON.stringify({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}}));""")
 p2.goto(BASE+'?organize=shinsoku-listening');p2.wait_for_function("cloudReady&&!cloudBusy&&!shinsokuBusy&&!location.search.includes('organize=')")
 assert backend['payload']==expected
 count=len(writes)
 for _ in range(2):p2.evaluate('clearTimeout(cloudTimer);syncCloud()')
 assert len(writes)==count
 p3=page();p3.goto(BASE);assert not p3.evaluate("state.cards.some(c=>c.tags.includes('神速リスニング'))")
 assert not errors,errors;print('PASS: private account loaded before tagging, sync saves once, polling unchanged, other visitors untouched');b.close()
