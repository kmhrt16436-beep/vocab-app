"""Randomize eligible cards without corrupting sync; keep pictures large and answers accessible."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,os,shutil,tempfile
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='https://random.test/';PUBLIC='https://kmhrt16436-beep.github.io/vocab-app/';errors=[]
def routes(route):
 path=unquote(urlsplit(route.request.url).path).removeprefix('/vocab-app/')
 if route.request.url.startswith(BASE):path='index.html'
 file=ROOT/path
 if not file.is_file():route.fulfill(status=404);return
 route.fulfill(body=file.read_bytes(),content_type='image/png' if file.suffix=='.png' else 'text/html' if file.suffix=='.html' else 'application/json')
def fixture(p):
 return p.evaluate("""()=>{state=initial();state.cards=Array.from({length:80},(_,i)=>{const c=card(['word-'+i,'名）意味'+i,'','','','','']);c.id='c'+String(i).padStart(3,'0');if(i<40){c.stage=3;c.memory={lastReviewed:shiftDate(today(),-i-1),stability:7,difficulty:.4,reviews:2,successes:2,lapses:0,streak:2,scheduledDays:7,estimated:false}}return c});for(let i=0;i<2;i++){const c=card(['retry-'+i,'答え','','','','','']);c.id='r'+i;updateMemory(c,false,false);state.cards.push(c)}const future=card(['future','答え','','','','','']);future.id='future';future.due=after(7);state.cards.push(future);state.session={date:today(),queue:state.cards.filter(c=>c.id!=='future').map(c=>({id:c.id,retry:c.id.startsWith('r')})),done:0,doneByFolder:{},reviewCounts:{}};activeFolder='*';activeTag='';revealed=false;window.originalRandom=Math.random;let seed=7;Math.random=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);queueRandomWeights.clear();orderStudyQueue();render();persist();return JSON.parse(JSON.stringify(state))}""")
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':390,'height':744});ctx.route(BASE+'**',routes);ctx.route(PUBLIC+'**',routes);p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE+'index.html')
 initial=fixture(p);q=initial['session']['queue'];assert len(q)==len({x['id'] for x in q})==82;assert all(not x['retry'] for x in q[:80]) and all(x['retry'] for x in q[80:]);assert 12<=sum(int(x['id'][1:])>=40 for x in q[:40])<=28;assert 'future' not in [x['id'] for x in q]
 canonical=p.evaluate('syncString(state)');p.evaluate('orderStudyQueue()');assert p.evaluate('state.session.queue')==q
 front=p.evaluate('studyItem().id');p.evaluate('applySyncedState(normalizedSync(state))');assert p.evaluate('studyItem().id')==front and not p.evaluate('revealed');assert p.evaluate('state.session.queue')==q;assert p.evaluate('syncString(state)')==canonical
 p.locator('.front').click();p.evaluate("(()=>{const next=normalizedSync(state);next.cards.find(c=>c.id===studyItem().id).tags.push('同期の分類');applySyncedState(next)})()");assert p.evaluate('studyItem().id')==front and p.evaluate('revealed')
 print('PASS: new/review cards are mixed, each pending card appears once, future cards stay excluded, retries are last, polling preserves front/back and ordering; sync serialization stays deterministic')
 # Explicit shuffle changes only local presentation; old JSON gains the default without changing the schedule.
 before=p.evaluate('JSON.stringify(state.cards)');wire=p.evaluate('syncString(state)');p.evaluate('reshuffleStudy()');assert p.evaluate('state.session.queue')!=q;assert p.evaluate('JSON.stringify(state.cards)')==before;assert p.evaluate('syncString(state)')==wire
 assert p.evaluate("(()=>{const x=initial();delete x.settings.order;return validate(x).settings.order})()")=='random'
 p.locator('[data-tab=data]').click();p.locator('#reviewSettings').evaluate('(e)=>e.open=true');p.locator('#studyOrder').select_option('memory');assert p.evaluate('state.session.queue[0].id')=='c039';p.locator('#shuffleStudy').click();assert p.evaluate('state.settings.order')=='random';assert p.evaluate('JSON.stringify(state.cards)')==before
 p.evaluate('()=>{Math.random=originalRandom}');saved=p.evaluate('state');p.reload();assert p.evaluate('syncString(state)')==p.evaluate('x=>syncString(x)',saved);assert p.evaluate('state.session.queue')!=saved['session']['queue']
 print('PASS: manual shuffle and random/memory controls preserve card schedules/history; old data defaults to random; a new page reshuffles without changing the canonical synced data')
 # A failed card waits for the regular round, then has only one retry.
 p.evaluate("activeTab='study';tab('study');revealed=true;window.failedID=studyItem().id;grade(false)");assert p.evaluate('state.session.queue.filter(q=>q.id===failedID).length')==1;assert p.evaluate('state.session.queue.find(q=>q.id===failedID).retry');assert not p.evaluate('studyItem().retry')
 p.evaluate("()=>{while(studyItem()&&!studyItem().retry){revealed=true;grade(true)}}");assert p.evaluate('state.session.queue.length')==3
 p.evaluate("()=>{while(studyItem()){revealed=true;grade(false)}}");assert p.evaluate('state.session.queue.length')==0;assert p.evaluate("state.cards.find(c=>c.id===failedID).due===after(1)")
 print('PASS: failures return once at the end and stay scheduled for tomorrow; no duplicate retry loops')
 # A card with an actual image: meanings stay visible, extra details can expand, and the image gets space.
 p.evaluate("""()=>{state=initial();const c=card(['submit','動）提出する','動）従う、服従する','類）hand in：提出する','Please submit your report by Friday.','金曜日までに報告書を提出してください。','https://kmhrt16436-beep.github.io/vocab-app/toeic-001.png']);state.cards=[c];state.session.queue=[{id:c.id,retry:false}];activeFolder='*';activeTag='';revealed=true;tab('study')}""")
 for width,height in [(390,744),(360,640),(1366,768),(844,390)]:
  p.set_viewport_size({'width':width,'height':height});p.evaluate('revealed=true;renderStudy(true)');p.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0")
  box=p.evaluate("""()=>{const image=document.querySelector('.illustration'),r=image.getBoundingClientRect(),g=document.querySelector('.grade').getBoundingClientRect(),nav=document.querySelector('nav').getBoundingClientRect(),a=document.querySelector('.answer-layout').getBoundingClientRect();return {paint:Math.min(r.width/image.naturalWidth,r.height/image.naturalHeight)*image.naturalHeight,areaHeight:a.height,grade:g.bottom,limit:innerWidth<900?nav.top:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth}}""")
  assert not box['overflow'] and box['grade']<=box['limit']+1,box
  if width==390:assert box['paint']>=260,box
  if width==360:assert box['paint']>=185,box
  if width==1366:assert box['paint']>=460,box
  p.screenshot(path=str(Path(tempfile.gettempdir())/f'flash-cards-large-{width}.png'))
  assert p.get_by_text('動）提出する',exact=True).is_visible() and p.get_by_text('動）従う、服従する',exact=True).is_visible()
  if width<900:
   assert not p.locator('.answer-extra').evaluate('(e)=>e.open');assert not p.get_by_text('Please submit your report by Friday.',exact=True).is_visible();p.locator('.answer-extra summary').click();assert p.get_by_text('Please submit your report by Friday.',exact=True).is_visible();p.evaluate('applySyncedState(normalizedSync(state))');assert p.locator('.answer-extra').evaluate('(e)=>e.open')
  important=p.locator('.important').evaluate('(e)=>({size:parseFloat(getComputedStyle(e).fontSize),color:getComputedStyle(e).color})');normal=p.locator('.answer-text>.field .value:not(.important)').first.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)');assert abs(important['size']/normal-1.5)<.05 and important['color']=='rgb(189, 41, 41)'
 print('PASS: larger pictures at mobile/desktop sizes, meanings stay visible, details expand and stay open through sync, grading controls fit, important meaning remains red and 1.5×')
 assert not errors,errors;b.close()
