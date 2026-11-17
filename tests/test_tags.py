"""Shared tags, duplicate datasets and concurrent review/tag edits use one card."""
from pathlib import Path
from urllib.parse import urlsplit
import copy,json,os,shutil,tempfile
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'index.html';BASE='https://tags.test/';backend={};writes=[];errors=[]
def cloud(route):
 path=urlsplit(route.request.url).path
 if path=='/rest/v1/word_progress':route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend.update(revision=body['expected_revision']+1,payload=body['new_payload']);writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
def sync(page):page.evaluate('clearTimeout(cloudTimer);syncCloud()')
def login(page):
 page.evaluate("cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};loginCloud({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}})")
 page.wait_for_function('cloudReady&&!cloudBusy')
def fresh(page):
 page.evaluate("state=initial();state.cards=[];state.folders.push({id:'set-a',name:'データセットA',kind:'general',deleted:false},{id:'set-b',name:'データセットB',kind:'general',deleted:false});state.session.queue=[];activeFolder='*';activeTag='';persist();render()")
def import_csv(page,folder,tags,rows):
 page.locator('[data-tab=data]').click();page.locator('#csvFolder').select_option(folder);page.locator('#csvTags').fill(tags);page.locator('#csv').fill(rows);page.locator('#importCsv').click()
def reviewed(page,ok):page.evaluate('ok=>{revealed=true;grade(ok);clearTimeout(cloudTimer)}',ok)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 def new_page(width=390,height=744):
  ctx=browser.new_context(viewport={'width':width,'height':height},accept_downloads=True)
  ctx.route(BASE+'**',lambda r:r.fulfill(status=200,content_type='text/html',body=SOURCE.read_text()));ctx.route('https://test.supabase.co/**',cloud)
  page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'index.html');return page
 p=new_page()
 # Old duplicate copies: preserve the original raw backup and recent review, not the unreviewed copy's queue.
 raw=p.evaluate("""(()=>{const x=initial();x.version=3;x.folders.push({id:'set-a',name:'データセットA',kind:'general',deleted:false},{id:'set-b',name:'データセットB',kind:'general',deleted:false});const a=card(['共通問題','答え','','関連','説明','出典','📘 同じ図'],'set-a'),b=card([...a.fields],'set-b');a.id='copy-a';b.id='copy-b';updateMemory(a,true,false);a.memory.reviews=4;a.memory.successes=4;a.memory.streak=4;a.due=after(7);a.memory.stability=7;a.memory.scheduledDays=7;delete a.tags;delete a.sharedFolderIds;delete a.mergedIds;delete b.tags;delete b.sharedFolderIds;delete b.mergedIds;x.cards=[a,b];x.session.queue=[{id:b.id,retry:false}];delete x.session.reviewCounts;localStorage.setItem(KEY,JSON.stringify(x));return x})()""")
 p.reload();assert p.evaluate('state.version')==4;assert p.evaluate('state.cards.length')==1;assert json.loads(p.evaluate("localStorage.getItem(KEY+':before-tags')"))==raw
 c=p.evaluate('state.cards[0]');assert c['id']=='copy-a' and c['memory']==raw['cards'][0]['memory'];assert c['mergedIds']==['copy-b'];assert set(c['tags'])=={'データセットA','データセットB'};assert p.evaluate('state.session.queue')==[]
 for folder in ['set-a','set-b']:
  p.locator('#folderSelect').select_option(folder);assert p.evaluate('selectedCards().length')==1 and p.evaluate('studyItem()') is None
 print('PASS: v3 duplicates merge once, preserve latest history and both datasets, suppress already-answered copy, save pre-migration JSON')
 # Real seven-column CSV UI: shared across folders, new tags union, one due queue.
 fresh(p);row='共有する問題,答え,,関連,説明,出典,📘 同じ図'
 import_csv(p,'set-a','2020年過去問, 重点復習',row)
 import_csv(p,'set-b','2021年過去問、重点復習',row+'\n'+row)
 assert p.evaluate('state.cards.length')==1;assert p.evaluate('state.session.queue.length')==1;assert '新規0枚' in p.locator('#csvStatus').inner_text();assert '共有2枚' in p.locator('#csvStatus').inner_text()
 assert {'2020年過去問','2021年過去問','重点復習'}.issubset(set(p.evaluate('state.cards[0].tags')))
 p.locator('#folderSelect').select_option('set-a');p.locator('#tagSelect').select_option('2020年過去問');p.locator('[data-tab=study]').click();p.locator('.front').click();p.locator('.grade .primary').click()
 p.locator('#folderSelect').select_option('set-b');p.locator('#tagSelect').select_option('2021年過去問');assert p.evaluate('studyItem()') is None;assert '残り0枚／全1枚' in p.locator('#todayCount').inner_text();assert p.evaluate('state.cards[0].memory.reviews')==1
 # Reimport after reviewing must not create a fresh queue or reset its due date.
 before=p.evaluate('state.cards[0].memory');due=p.evaluate('state.cards[0].due');import_csv(p,'set-a','追加タグ',row);assert p.evaluate('state.cards.length')==1;assert p.evaluate('state.session.queue')==[];assert p.evaluate('state.cards[0].memory')==before and p.evaluate('state.cards[0].due')==due
 # Same term with a different answer, notes, or a custom illustration remains distinct.
 for changed in ['共有する問題,別の答え,,関連,説明,出典,📘 同じ図','共有する問題,答え,,異なる補足,説明,出典,📘 同じ図','共有する問題,答え,,関連,説明,出典,https://example.com/custom.png']:
  import_csv(p,'set-a','差分',changed)
 assert p.evaluate('state.cards.length')==4
 print('PASS: duplicate CSV rows and repeated datasets share one card/queue; multi-tag review and due dates persist; different answers, notes and custom images remain separate')
 # One retry shared across tags, rather than a retry per tag.
 fresh(p);import_csv(p,'set-a','甲,乙','再出題テスト,答え,,,,,📘 例')
 p.locator('#folderSelect').select_option('set-a');p.locator('#tagSelect').select_option('甲');p.locator('[data-tab=study]').click();p.locator('.front').click();p.locator('.grade .negative').click();p.locator('#tagSelect').select_option('乙');assert p.evaluate('studyItem().retry');assert p.evaluate('state.session.queue.length')==1
 p.locator('.front').click();p.locator('.grade .primary').click();p.locator('#tagSelect').select_option('甲');assert p.evaluate('studyItem()') is None;assert p.evaluate('state.session.done')==2
 # Editor tag add/remove and multi-tag input preserve review history.
 p.locator('[data-tab=cards]').click();p.locator('[aria-label="再出題テストを編集"]').click();p.locator('#cardTags').fill('甲, 重点復習');p.locator('#cardForm [type=submit]').click();assert p.evaluate('state.cards[0].tags')==['甲','重点復習'];assert p.evaluate('state.cards[0].memory.reviews')==2
 p.locator('#tagSelect').select_option('');p.locator('#bulkTags').evaluate('(e)=>e.open=true');p.locator('#search').fill('再出題');p.locator('#bulkTagInput').fill('試験前');p.locator('#applyBulkTags').click();assert '試験前' in p.evaluate('state.cards[0].tags')
 p.locator('#manageTags').click();p.once('dialog',lambda d:d.accept('試験直前'));p.locator('#tagList .tag-row').filter(has=p.get_by_text('#試験前',exact=True)).get_by_role('button',name='名前変更').click();assert '試験直前' in p.evaluate('state.cards[0].tags')
 p.locator('#tagList .tag-row').filter(has=p.get_by_text('#試験直前',exact=True)).get_by_role('button',name='外す',exact=True).click();assert '試験直前' not in p.evaluate('state.cards[0].tags');assert p.evaluate('state.cards[0].memory.reviews')==2
 snapshot=p.evaluate('JSON.stringify(state)');p.locator('#jsonText').fill(snapshot);p.once('dialog',lambda d:d.accept());p.locator('#importJson').click();assert p.evaluate('JSON.stringify(state)')==snapshot
 p.locator('#folderSelect').select_option('*');p.locator('#tagSelect').select_option('重点復習');p.reload();assert p.locator('#tagSelect').input_value()=='重点復習'
 print('PASS: single shared retry; tag edit/bulk-add/rename/remove; JSON round trip and local filter; all preserve review history')
 # A cloud-only old collection also upgrades the server and stores a separate raw backup.
 backend.update(revision=1,payload=raw);migration=new_page();fresh(migration);login(migration)
 assert backend['payload']['version']==4 and len(backend['payload']['cards'])==1
 assert json.loads(migration.evaluate("localStorage.getItem(cloudLocalKey('user-a')+':before-tags')"))==raw
 migration.close();backend.clear();writes.clear()
 print('PASS: cloud-only v3 data migrate to the server and retain an account-specific raw backup')
 # Three-way sync: simultaneous identical imports, then PC tags vs mobile review and tag removal.
 pc=new_page(1366,768);phone=new_page();fresh(pc);fresh(phone);login(pc);login(phone)
 import_csv(pc,'set-a','PC, 共通','同期する問題,答え,,,,,📗 同じ図');import_csv(phone,'set-b','スマホ, 共通','同期する問題,答え,,,,,📗 同じ図');sync(pc);sync(phone);sync(pc);sync(phone)
 assert len(backend['payload']['cards'])==1
 cid=backend['payload']['cards'][0]['id'];assert {'PC','スマホ','共通'}.issubset(set(backend['payload']['cards'][0]['tags']))
 pc.evaluate("state.cards[0].tags.push('PCで追加');state.cards[0].fields[3]='PCの関連';persist();clearTimeout(cloudTimer)");phone.evaluate("state.cards[0].tags=state.cards[0].tags.filter(t=>t!=='共通');selectTag('スマホ');persist();clearTimeout(cloudTimer)");reviewed(phone,True);sync(phone);sync(pc);sync(phone)
 c=backend['payload']['cards'][0];assert c['id']==cid and c['memory']['reviews']==1 and c['fields'][3]=='PCの関連';assert backend['payload']['session']['done']==1;assert backend['payload']['session']['doneByFolder']['set-a']==backend['payload']['session']['doneByFolder']['set-b']==1;assert 'PCで追加' in c['tags'] and '共通' not in c['tags'];assert phone.evaluate('state.session.queue')==[]
 # Further concurrent tag additions converge after the two IDs have been unified.
 pc.evaluate("state.cards[0].tags.push('さらに追加');persist();clearTimeout(cloudTimer)");phone.evaluate("state.cards[0].tags.push('端末の追加');persist();clearTimeout(cloudTimer)");sync(pc);sync(phone);sync(pc)
 assert len(backend['payload']['cards'])==1;assert {'さらに追加','端末の追加'}.issubset(set(backend['payload']['cards'][0]['tags']))
 count=len(writes)
 for _ in range(3):sync(pc);sync(phone)
 assert len(writes)==count,'Unchanged tags should not cause repeated cloud writes'
 # A merged shared card is deleted once across all datasets, rather than resurrected by aliases.
 pc.evaluate("state.cards=[];state.session.queue=[];persist();clearTimeout(cloudTimer)");sync(pc);sync(phone);assert backend['payload']['cards']==[] and phone.evaluate('state.cards')==[]
 print('PASS: concurrent duplicate imports converge; PC tag additions + mobile review/removal survive; aliases do not resurrect cards; unchanged sync does not rewrite')
 # Compact learning layout with tags at phone and desktop sizes.
 fresh(p);import_csv(p,'set-a','甲,乙','画面サイズを確認する問題,答え,,関連,説明,出典,📘 図')
 for width,height in [(390,744),(360,640),(1366,768)]:
  p.set_viewport_size({'width':width,'height':height});p.locator('[data-tab=study]').click();p.evaluate("selectTag('甲');revealed=true;renderStudy()")
  assert p.locator('.grade .primary').is_visible();assert p.evaluate("(()=>{const r=document.querySelector('.grade').getBoundingClientRect(),n=document.querySelector('nav').getBoundingClientRect();return r.bottom<=(innerWidth<900?n.top:innerHeight)+1&&document.documentElement.scrollWidth<=innerWidth})()")
 p.screenshot(path=str(Path(tempfile.gettempdir())/'vocab-tags-desktop.png'))
 p.set_viewport_size({'width':390,'height':744});p.screenshot(path=str(Path(tempfile.gettempdir())/'vocab-tags-mobile.png'))
 assert not errors,errors
 print('PASS: grading controls fit at 390×744, 360×640 and 1366×768; no JS errors')
 browser.close()
