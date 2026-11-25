"""An explicit-link import prioritizes the supplied senses, preserves history and syncs."""
from pathlib import Path
from urllib.parse import urlsplit
import copy,csv,io,json,os,shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='https://toeic9.test/'
pack=json.loads((ROOT/'study/english/toeic9-part7/cards.json').read_text())
rows=list(csv.reader(io.StringIO((ROOT/'study/english/toeic9-part7/cards.csv').read_text(encoding='utf-8-sig'))))
assert len(rows)==145 and len({r[0] for r in rows})==145 and all(len(r)==7 for r in rows)
assert rows==[c['fields'] for c in pack['cards']]
assert all(len(r[4].split())<=10 and r[3] and r[5] and r[6] for r in rows)
lookup={r[0]:r for r in rows}
assert lookup['drawing'][1]=='名）抽選、くじ引き'
assert lookup['quality'][1]=='形）上質の'
assert lookup['question'][1]=='動）～に異議を唱える、～を疑問視する'
assert lookup['article'][1]=='名）品物'
assert lookup['land'][1]=='動）仕事などを獲得する'
assert lookup['drop off'][1]=='荷物などを引き渡す'
backend={};writes=[];errors=[];fetches=[]
def app(route):
 path=urlsplit(route.request.url).path
 if path.endswith('cards.json'):fetches.append(path);route.fulfill(json=pack);return
 route.fulfill(content_type='text/html',body=(ROOT/'index.html').read_text())
def cloud(route):
 path=urlsplit(route.request.url).path
 if path=='/rest/v1/word_progress':route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend.update(revision=body['expected_revision']+1,payload=body['new_payload']);writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 def page():
  c=b.new_context(viewport={'width':390,'height':744});c.route(BASE+'**',app);c.route('https://test.supabase.co/**',cloud);p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));return p
 p=page();p.goto(BASE);assert p.evaluate('state.cards.length')==5 and not fetches
 before=p.evaluate("""async()=>{state=initial();state.cards=[];state.session.queue=[];const c=card(['quality','名）品質','名）質','自分の関連メモ','Old example.','元の説明','']);c.id='quality-old';c.tags=['既存の分類'];c.stage=4;c.due=after(11);c.memory={lastReviewed:today(),stability:14,difficulty:.4,reviews:9,successes:8,lapses:1,streak:3,scheduledDays:14,estimated:false};const canvas=document.createElement('canvas');canvas.width=16;canvas.height=16;c.fields[6]=await putCardImage(await new Promise(r=>canvas.toBlob(r)),imageOwner());state.cards.push(c);const own=card(['my own word','名）独自','','','','','']);own.due=after(8);own.tags=['自分のタグ'];state.cards.push(own);state.folders.push({id:'heat',name:'熱',kind:'general',deleted:false});const heat=card(['quality','自作の問題','','','','',''],'heat');heat.due=after(8);state.cards.push(heat);persist();return JSON.parse(JSON.stringify(state))}""")
 p.goto(BASE+'?pack=toeic9-part7');p.wait_for_function("!requestedPackBusy&&!location.search.includes('pack=')&&state.cards.length===147")
 result=p.evaluate('state');updated=next(c for c in result['cards'] if c['id']=='quality-old');old=before['cards'][0]
 assert updated['fields'][1]=='形）上質の' and '名）品質' in updated['fields'][2] and updated['fields'][6]==old['fields'][6]
 assert updated['memory']==old['memory'] and updated['due']==old['due'] and updated['stage']==old['stage']
 assert set(updated['tags'])=={'既存の分類','公式問題集9'}
 assert [c for c in result['cards'] if c['id'] in [before['cards'][1]['id'],before['cards'][2]['id']]]==before['cards'][1:]
 assert sum('公式問題集9' in c['tags'] for c in result['cards'])==145 and len(result['session']['queue'])==144
 assert p.locator('#tagSelect').input_value()=='公式問題集9' and '新規144枚' in p.locator('#toeic9PackStatus').inner_text()
 assert p.evaluate("JSON.parse(localStorage.getItem(activeStorageKey+':before-pack:'+TOEIC9_PACK_ID))")==before
 p.evaluate("state.cards.find(c=>c.id==='quality-old').fields[0]='my edited quality';state.cards.find(c=>c.id==='quality-old').fields[3]='自分の更新';persist()")
 snapshot=p.evaluate('syncString(state)');p.goto(BASE+'?pack=toeic9-part7');p.wait_for_function("!requestedPackBusy&&!location.search.includes('pack=')")
 assert p.evaluate('syncString(state)')==snapshot
 p.reload();assert p.evaluate('syncString(state)')==snapshot
 print('PASS: 145 unique seven-field cards, supplied meanings first, <=10-word examples; opt-in import; only target cards tagged; history/custom photos/other subjects preserved; backup and repeated-link idempotence')
 # Login must finish and merge remote data before installing into that private account.
 remote=copy.deepcopy(before);remote['cards'][0]['fields'][6]='📦 自分の画像メモ';backend.update(revision=3,payload=remote)
 p2=page();p2.add_init_script("""localStorage.setItem('daily-words-v1:cloud-config',JSON.stringify({url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'}));localStorage.setItem('daily-words-v1:cloud-auth',JSON.stringify({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}}));""")
 p2.goto(BASE+'?pack=toeic9-part7');p2.wait_for_function("cloudReady&&!cloudBusy&&!requestedPackBusy&&!location.search.includes('pack=')&&state.cards.length===147")
 assert sum('公式問題集9' in c['tags'] for c in backend['payload']['cards'])==145
 assert next(c for c in backend['payload']['cards'] if c['id']=='quality-old')['memory']==old['memory']
 count=len(writes)
 for _ in range(2):p2.evaluate('clearTimeout(cloudTimer);syncCloud()')
 assert len(writes)==count
 p3=page();p3.goto(BASE);assert p3.evaluate('state.cards.length')==5
 assert not p3.evaluate("state.cards.some(c=>c.tags.includes('公式問題集9'))")
 print('PASS: existing account downloaded before import, new cards auto-saved to cloud once, subsequent polling unchanged, other accounts/visitors never auto-enrolled')
 assert not errors,errors;b.close()
