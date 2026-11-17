from playwright.sync_api import sync_playwright
from pathlib import Path
import os,shutil,tempfile
from urllib.parse import urlsplit
import json,copy
backend={};writes=[];dialogs=[];errors=[];offline=set();held=[];hold_next=[False];expire_next=[False];refreshes=[];race_card=[None]
source=(Path(__file__).resolve().parents[1]/'index.html')
def handle(route):
 r=route.request;path=urlsplit(r.url).path;body=r.post_data_json if r.post_data else {};uid=r.headers.get('authorization','Bearer user-a').split(' ')[-1].replace('-fresh','')
 if uid in offline:route.abort();return
 if path=='/auth/v1/otp':data={}
 elif path=='/auth/v1/user':data={'id':uid,'email':uid+'@example.com'}
 elif path=='/auth/v1/token':
  uid=body['refresh_token'].replace('-refresh','');refreshes.append(uid);data={'access_token':uid+'-fresh','refresh_token':uid+'-refresh','user':{'id':uid,'email':uid+'@example.com'}}
 elif path=='/rest/v1/word_progress':
  if expire_next[0]:expire_next[0]=False;route.fulfill(status=401,json={'message':'JWT expired'});return
  data=[backend[uid]] if uid in backend else []
 elif path=='/rest/v1/rpc/save_word_progress':
  if race_card[0] is not None:
   current=backend[uid];current['payload']['cards'].append(race_card[0]);current['payload']['session']['queue'].append({'id':race_card[0]['id'],'retry':False});current['revision']+=1;race_card[0]=None
  if body['expected_revision']!=backend.get(uid,{'revision':0})['revision']:route.fulfill(status=409,json={'code':'40001','message':'changed'});return
  data={'revision':body['expected_revision']+1,'payload':body['new_payload']};backend[uid]=copy.deepcopy(data);writes.append(copy.deepcopy(data))
  if hold_next[0]:hold_next[0]=False;held.append((route,data));return
 elif path=='/auth/v1/logout':data={}
 else:raise Exception(path)
 route.fulfill(status=200,json=data)
def sync(p):p.evaluate('clearTimeout(cloudTimer);syncCloud()')
def add(p,word):p.evaluate("w=>{const c=card([w,'名）追加','','','','','']);state.cards.push(c);enqueue(c.id);persist();clearTimeout(cloudTimer);render()}",word)
def review(p,ok):p.evaluate("ok=>{revealed=true;grade(ok);clearTimeout(cloudTimer)}",ok)
def names(p):return p.evaluate('state.cards.map(c=>c.fields[0])')
def login(p,uid='user-a'):
 p.locator('[data-tab="data"]').click();p.locator('#cloudSettings').evaluate('(e)=>e.open=true');p.locator('#cloudUrl').fill('https://test.supabase.co');p.locator('#cloudKey').fill('sb_publishable_test_public_key_12345');p.locator('#saveCloudConfig').click();p.wait_for_function('!cloudRequestBusy')
 p.goto('https://word-app.test/index.html#access_token='+uid+'&refresh_token='+uid+'-refresh');p.wait_for_function('cloudReady&&!cloudBusy');p.wait_for_function("document.getElementById('cloudStatus').textContent.startsWith('同期済み')")
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);contexts=[];pages=[]
 for _ in range(3):
  ctx=b.new_context(viewport={'width':390,'height':844});ctx.route('https://test.supabase.co/**',handle);ctx.route('https://word-app.test/**',lambda r:r.fulfill(status=200,content_type='text/html',body=source.read_text()));p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.on('dialog',lambda d:(dialogs.append(d.message),d.accept()));p.goto('https://word-app.test/index.html');contexts.append(ctx);pages.append(p)
 pc,phone,other=pages
 # New login uploads automatically, without selection/confirmation.
 login(pc);assert len(backend['user-a']['payload']['cards'])==5;login(phone);assert len(names(phone))==5;assert dialogs==[]
 assert not pc.locator('#useDevice').is_visible() and not phone.locator('#useCloud').is_visible()
 # PC can add while mobile reviews. Mobile progress must survive the subsequent PC write.
 first=phone.evaluate('state.session.queue[0].id');review(phone,True);sync(phone);before=copy.deepcopy(backend['user-a']['payload']);add(pc,'new-pc-word');assert '未同期' in pc.locator('#syncSummary').inner_text();sync(pc);saved=backend['user-a']['payload'];assert next(c for c in saved['cards'] if c['id']==first)['memory']==next(c for c in before['cards'] if c['id']==first)['memory'];sync(phone);assert 'new-pc-word' in names(phone)
 # Opening a page again resumes automatically and does not rewrite unchanged data.
 count=len(writes);pc.reload();pc.wait_for_function('cloudReady&&!cloudBusy');assert 'new-pc-word' in names(pc);assert dialogs==[]
 for _ in range(3):sync(pc);sync(phone)
 assert len(writes)==count,(len(writes),count)
 # Concurrent additions from a common baseline are combined without duplicate words/loss.
 add(pc,'pc-concurrent');add(phone,'phone-concurrent');sync(pc);sync(phone);sync(pc);assert {'pc-concurrent','phone-concurrent'}.issubset(set(names(pc)))
 # Two different cards reviewed while offline from each other's updates: preserve both.
 sync(phone);pc_id=pc.evaluate('state.session.queue[0].id');phone.evaluate("id=>{state.session.queue=state.session.queue.filter(q=>q.id!==id);}",pc_id);ph_id=phone.evaluate('state.session.queue[0].id');review(pc,True);review(phone,True);sync(pc);sync(phone);sync(pc)
 for cid in [pc_id,ph_id]:assert next(c for c in backend['user-a']['payload']['cards'] if c['id']==cid)['memory']['reviews']>=1
 # Same-day retry completed on one device must not be resurrected by the other.
 sync(phone);retry_id=phone.evaluate('state.session.queue[0].id');review(phone,False);sync(phone);sync(pc);phone.evaluate("id=>{const i=state.session.queue.findIndex(q=>q.id===id);state.session.queue=[state.session.queue[i],...state.session.queue.filter(q=>q.id!==id)];}",retry_id);review(phone,True);sync(phone);sync(pc);assert not pc.evaluate('(id)=>state.session.queue.some(q=>q.id===id)',retry_id)
 # Unsynced edits survive a reload during offline use, then merge after reconnect.
 offline.add('user-a');add(pc,'offline-word');sync(pc);pc.reload();pc.wait_for_function('cloudReady&&!cloudBusy');assert 'offline-word' in names(pc);assert '未同期' in pc.locator('#cloudStatus').inner_text();offline.remove('user-a');sync(pc);sync(phone);assert 'offline-word' in names(phone)
 # Mutation during a pending save is retained and sent in the following sync.
 add(pc,'during-save-1');hold_next[0]=True;pc.evaluate('void syncCloud()');pc.wait_for_timeout(80);assert held
 add(pc,'during-save-2');route,data=held.pop();route.fulfill(status=200,json=data);pc.wait_for_function('!cloudBusy');sync(pc);assert {'during-save-1','during-save-2'}.issubset(set(c['fields'][0] for c in backend['user-a']['payload']['cards']))
 # A remote write between GET and POST triggers CAS retry and merges instead of prompting.
 race_card[0]=pc.evaluate("card(['raced-remote','名）競合','','','','',''])");add(pc,'raced-local');sync(pc);assert {'raced-local','raced-remote'}.issubset(set(c['fields'][0] for c in backend['user-a']['payload']['cards']));assert not held
 # Token refresh is transparent.
 expire_next[0]=True;sync(pc);assert refreshes==['user-a']
 # Deletion is propagated and not undone by the other device's old cache.
 sync(phone);deleted=pc.evaluate('state.cards[0].id');pc.evaluate("id=>{state.cards=state.cards.filter(c=>c.id!==id);state.session.queue=state.session.queue.filter(q=>q.id!==id);persist();clearTimeout(cloudTimer)}",deleted);sync(pc);sync(phone);assert not phone.evaluate('(id)=>state.cards.some(c=>c.id===id)',deleted)
 # Folders sync, while selected folder stays local to each device.
 def make_folder(page,name):
  return page.evaluate("name=>{const f={id:uid(),name,kind:'general',deleted:false};state.folders.push(f);persist();clearTimeout(cloudTimer);return f.id}",name)
 def add_to(page,fid,word):
  return page.evaluate("([folderId,word])=>{const c=card([word,'答え','','','','',''],folderId);state.cards.push(c);enqueue(c.id);persist();clearTimeout(cloudTimer);return c.id}",[fid,word])
 history=make_folder(pc,'世界史');hist_card=add_to(pc,history,'革命');sync(pc);sync(phone);assert phone.evaluate('(id)=>state.folders.some(f=>f.id===id&&!f.deleted)',history);assert phone.evaluate('activeFolder')=='english'
 phone.evaluate('id=>selectFolder(id)',history);review(phone,False);sync(phone);sync(pc);assert next(c for c in backend['user-a']['payload']['cards'] if c['id']==hist_card)['memory']['lapses']==1
 # Concurrent additions of different folders and cards survive.
 math=make_folder(pc,'数学');bio=make_folder(phone,'生物');math_card=add_to(pc,math,'共通の用語');bio_card=add_to(phone,bio,'共通の用語');phone.evaluate("id=>{state.cards.find(c=>c.id===id).fields[1]='生物の答え';persist();clearTimeout(cloudTimer)}",bio_card);sync(pc);sync(phone);sync(pc);assert len([c for c in backend['user-a']['payload']['cards'] if c['fields'][0]=='共通の用語'])==2
 assert all(pc.evaluate('(id)=>state.folders.some(f=>f.id===id)',f) for f in [history,math,bio])
 # Rename one folder while the other device reviews a card in it.
 sync(phone);pc.evaluate("id=>{state.folders.find(f=>f.id===id).name='歴史';persist();clearTimeout(cloudTimer)}",history);phone.evaluate('id=>selectFolder(id)',history);review(phone,True);sync(phone);sync(pc);sync(phone);assert phone.evaluate('(id)=>folderInfo(id).name',history)=='歴史';assert next(c for c in backend['user-a']['payload']['cards'] if c['id']==hist_card)['memory']['reviews']==2
 # Move and edit on PC while smartphone reviews: preserve all three independent changes.
 sync(phone);pc.evaluate("([cid,fid])=>{const c=state.cards.find(c=>c.id===cid);c.folderId=fid;c.fields[2]='PCの補足';persist();clearTimeout(cloudTimer)}",[math_card,bio]);phone.evaluate('id=>selectFolder(id)',math);review(phone,True);sync(phone);sync(pc);sync(phone);merged=next(c for c in backend['user-a']['payload']['cards'] if c['id']==math_card);assert merged['folderId']==bio and merged['fields'][2]=='PCの補足' and merged['memory']['reviews']==1
 # Folder deletion vs. offline new card: deletion stays deleted, cards are rehomed without losing memory.
 sync(phone);pc.evaluate("id=>{state.folders.find(f=>f.id===id).deleted=true;state.cards.filter(c=>c.folderId===id).forEach(c=>c.folderId=DEFAULT_FOLDER);persist();clearTimeout(cloudTimer)}",bio);late=add_to(phone,bio,'削除中に追加');sync(pc);sync(phone);sync(pc);assert pc.evaluate('(id)=>state.folders.find(f=>f.id===id).deleted',bio)
 for cid in [bio_card,math_card,late]:assert next(c for c in backend['user-a']['payload']['cards'] if c['id']==cid)['folderId']=='english'
 assert next(c for c in backend['user-a']['payload']['cards'] if c['id']==math_card)['memory']['reviews']==1
 # Two independent same-day reviews in a folder add exactly two to that folder's completed count.
 sync(phone);a=add_to(pc,history,'歴史A');bb=add_to(pc,history,'歴史B');sync(pc);sync(phone);baseline=backend['user-a']['payload']['session']['doneByFolder'].get(history,0)
 for page,cid in [(pc,a),(phone,bb)]:
  page.evaluate("([fid,cid])=>{selectFolder(fid);const q=state.session.queue.find(q=>q.id===cid);state.session.queue=[q,...state.session.queue.filter(q=>q.id!==cid)];}",[history,cid]);review(page,True)
 sync(pc);sync(phone);sync(pc);assert backend['user-a']['payload']['session']['doneByFolder'][history]==baseline+2,(baseline,backend['user-a']['payload']['session'])
 count=len(writes)
 for _ in range(3):sync(pc);sync(phone)
 assert len(writes)==count,'unchanged folder data should not cause repeat writes'
 # Initial no-baseline merge only deduplicates within a folder, not across subjects.
 assert pc.evaluate("(()=>{const x=initial(),y=initial(),f={id:'other-subject',name:'他教科',kind:'general',deleted:false};x.cards=[card(['same','A','','','','',''])];y.folders.push(f);y.cards=[card(['same','B','','','','',''],f.id)];x.session.queue=[];y.session.queue=[];return mergeStudyData(x,y).cards.length})()") ==2
 print('PASS: folder creation/rename sync; concurrent folder additions; same word in different subjects; card move + independent review; deleted folder vs offline addition; per-folder progress concurrency; no repeated writes.')
 # Another account stays separate.
 login(other,'user-b');assert 'new-pc-word' not in names(other);assert len(backend['user-b']['payload']['cards'])==5
 # The live learning view exposes sync state and retains adaptive memory fields.
 phone.locator('[data-tab="study"]').click();assert phone.locator('#syncSummary').text_content();assert phone.evaluate('document.documentElement.scrollWidth<=innerWidth');phone.screenshot(path=str(Path(tempfile.gettempdir())/'vocab-sync-mobile.png'),full_page=True)
 assert not errors,errors;assert dialogs==[],dialogs
 print('PASS: automatic first login and resume, no cloud-selection dialogs, PC additions + mobile progress, unchanged polling, concurrent additions/reviews, retry completion, offline reload/reconnect, edits during save, automatic CAS retry, token refresh, deletion, account isolation and mobile layout.')
 b.close()
