"""Image-only migration must preserve studying, custom content and cloud account data."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import copy,json,os,shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='https://kmhrt16436-beep.github.io/vocab-app/'
data=json.loads((ROOT/'study/heat-air/complete/cards.json').read_text())
updates=json.loads((ROOT/'study/heat-air/complete/image-updates.json').read_text())['updates']
old_urls={front:old for front,old,new in updates}
old_fields=[[*c['fields'][:6],old_urls[c['fields'][0]]] for c in data['cards']]
sample=json.loads((ROOT/'study/heat-air/sample-01/cards.json').read_text())
if isinstance(sample,dict):sample=sample['cards']
old_fields += [[*(x['fields'] if isinstance(x,dict) else x)[:6],old_urls[(x['fields'] if isinstance(x,dict) else x)[0]]] for x in sample]
expected={front:new for front,old,new in updates}
errors=[];backend={};writes=[];offline=[False];held=[];hold=[False]

def files(route):
 path=unquote(urlsplit(route.request.url).path).removeprefix('/vocab-app/')
 if path=='study/heat-air/complete/image-updates.json':
  if offline[0]:route.abort();return
  if hold[0]:held.append(route);return
 p=ROOT/(path+'index.html' if path.endswith('/') else path)
 if not p.is_file():route.fulfill(status=404);return
 mime={'.html':'text/html','.json':'application/json','.png':'image/png','.js':'application/javascript','.csv':'text/csv'}.get(p.suffix,'text/plain')
 route.fulfill(status=200,content_type=mime,body=p.read_bytes())
def cloud(route):
 global backend
 path=urlsplit(route.request.url).path
 if path=='/rest/v1/word_progress':route.fulfill(json=[backend] if backend else []);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=route.request.post_data_json
  if body['expected_revision']!=backend.get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend={'revision':body['expected_revision']+1,'payload':body['new_payload']};writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
 raise AssertionError(path)
def fixture(page):
 return page.evaluate('''rows=>{
  const value=initial();value.folders.push({id:'heat-air',name:'熱・空気',kind:'general',deleted:false});
  value.cards=rows.map(fields=>{const c=card(fields,'heat-air');c.stage=3;c.due=shiftDate(today(),5);c.memory={lastReviewed:shiftDate(today(),-2),stability:7,difficulty:.4,reviews:5,successes:4,lapses:1,streak:2,scheduledDays:7,estimated:false};return c});
  const custom=card([...rows[0]],'heat-air');custom.due=shiftDate(today(),5);custom.fields[6]='https://example.com/custom.png';value.cards.push(custom);
  const edited=card([...rows[1]],'heat-air');edited.due=shiftDate(today(),5);edited.fields[0]+='（自分で編集）';value.cards.push(edited);
  const unknown=card(['独自の問題','独自の答え','','','','',rows[0][6]],'heat-air');unknown.due=shiftDate(today(),5);value.cards.push(unknown);
  value.session={date:today(),queue:[{id:value.cards[0].id,retry:true}],done:13,doneByFolder:{'heat-air':13}};
  state=validate(value);localStorage.setItem(KEY,JSON.stringify(state));return state;
 }''',old_fields)
def without_images(value):
 value=copy.deepcopy(value)
 for c in value['cards']:c['fields'][6]='<image>'
 return value
def wait_upgrade(page,count=303):
 page.wait_for_function('(n)=>state.cards.filter(c=>c.fields[6].includes("/slide-crops/")).length===n',arg=count)
 page.wait_for_function('studyIllustrationJob===null')
def assert_upgrade(before,after,count=303):
 assert len(after['cards'])==len(before['cards'])
 assert without_images(before)==without_images(after),'Non-image state changed'
 for i,c in enumerate(after['cards']):
  assert c['fields'][6]==(expected[c['fields'][0]] if i<count else before['cards'][i]['fields'][6])

with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':390,'height':744});ctx.route(BASE+'**',files);ctx.route('https://test.supabase.co/**',cloud)
 p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE+'index.html')
 before=fixture(p);p.reload();wait_upgrade(p);after=p.evaluate('state');assert_upgrade(before,after)
 assert json.loads(p.evaluate('localStorage.getItem(KEY)'))==after
 p.reload();p.wait_for_function('studyIllustrationJob===null');assert p.evaluate('state')==after
 print('PASS: 298 full-set + 5 sample images upgrade; IDs, text, folders, reviews, queue, counts, dates and custom images unchanged; reload is idempotent')
 previous_fields=copy.deepcopy(old_fields)
 original_urls={}
 for front,old,new in updates:
  if '/diagrams-v2/' not in old:original_urls[front]=old
 for row in old_fields:row[6]=original_urls[row[0]]
 before=fixture(p);p.reload();wait_upgrade(p);assert_upgrade(before,p.evaluate('state'))
 old_fields=previous_fields
 print('PASS: initial image URLs and previous-version image URLs both migrate')

 # Failed catalog fetch is harmless and retryable, including concurrent callers.
 before=fixture(p);offline[0]=True;p.reload();p.wait_for_function('studyIllustrationJob===null');p.evaluate('Promise.all([refreshStudyIllustrations(),refreshStudyIllustrations()])');assert p.evaluate('state')==before
 offline[0]=False;p.evaluate("window.dispatchEvent(new Event('online'))");wait_upgrade(p);assert_upgrade(before,p.evaluate('state'))
 print('PASS: offline catalog preserves data and images; reconnect retries without unhandled rejections')
 # During the request, edit a question/image/answer and complete a review.
 before=fixture(p);hold[0]=True;p.reload();p.wait_for_function('studyIllustrationJob!==null');p.wait_for_timeout(50);assert held
 p.evaluate('''()=>{state.cards[0].fields[0]+=' edited';state.cards[1].fields[6]='https://example.com/new.png';state.cards[2].fields[1]='編集した答え';state.cards[2].memory.reviews++;state.cards[2].memory.successes++;state.cards[2].memory.streak++;state.cards[2].due=shiftDate(today(),9);localStorage.setItem(KEY,JSON.stringify(state))}''')
 edited=p.evaluate('state');hold[0]=False
 for route in held:route.fulfill(json={'version':3,'updates':updates})
 held.clear();wait_upgrade(p,301);actual=p.evaluate('state');assert without_images(actual)==without_images(edited);assert actual['cards'][0]['fields'][6]==edited['cards'][0]['fields'][6];assert actual['cards'][1]['fields'][6]=='https://example.com/new.png'
 print('PASS: edits and review changes made during fetch survive; late custom images and questions are preserved')
 # Login after boot: cards downloaded from the user's cloud also upgrade and save automatically.
 before=fixture(p);backend={'revision':1,'payload':copy.deepcopy(before)}
 p.evaluate("localStorage.removeItem(KEY);state=initial();cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};void loginCloud({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}})")
 wait_upgrade(p);p.wait_for_function('!cloudBusy');p.evaluate('clearTimeout(cloudTimer);syncCloud()');p.wait_for_function('!cloudBusy')
 assert writes and sum('/slide-crops/' in c['fields'][6] for c in backend['payload']['cards'])==303
 for old,new in zip(before['cards'],backend['payload']['cards']):
  assert old['id']==new['id'] and old['memory']==new['memory'] and old['due']==new['due'] and old['fields'][:6]==new['fields'][:6]
 assert not errors,errors
 print('PASS: cloud-loaded cards migrate and automatically sync with all review history and custom content preserved; no JS errors')
 p.evaluate("activeFolder=state.cards[0].folderId;state.session.queue=[{id:state.cards[0].id,retry:false}];revealed=true;render()")
 expected_image=p.locator('.illustration').get_attribute('src')
 p.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0")
 p.locator('.illustration').click();assert p.locator('#imageViewer').evaluate('(e)=>e.open')
 assert p.locator('#imageViewerPicture').get_attribute('src')==expected_image;p.locator('#closeImageViewer').click()
 p.locator('.illustration').press('Enter');assert p.locator('#imageViewer').evaluate('(e)=>e.open')
 assert p.locator('#imageViewerPicture').get_attribute('src')==expected_image;p.keyboard.press('Escape')
 print('PASS: original image enlargement works by tap and keyboard without changing review state')
 p.goto(BASE+'study/heat-air/complete/diagrams.html');assert p.locator('article').count()==len(data['illustrations'])
 p.evaluate("document.querySelectorAll('img').forEach(x=>x.loading='eager')")
 p.wait_for_function("[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
 p.set_viewport_size({'width':360,'height':640});assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
 p.locator('#search').fill('噴流');assert 2<=p.locator('article:visible').count()<len(data['illustrations'])
 assert not errors,errors
 print('PASS: all original-crop gallery images load; Japanese filtering and narrow mobile layout work')
 browser.close()
