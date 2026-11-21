"""English-only reading pages and optional breaks, independent of review progress."""
from pathlib import Path
import csv,io,json,os,shutil,tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1];BASE='https://columns.test/'
source=(ROOT/'index.html').read_text()
catalog=json.loads((ROOT/'study/english/columns.json').read_text())['articles']
rows=list(csv.reader(io.StringIO((ROOT/'TOEIC_images.csv').read_text(encoding='utf-8-sig'))))
assert [w for a in catalog[:13] for w in a['words']]==[r[0] for r in rows]
assert all(len(a['words'])==10 for a in catalog[:12]) and len(catalog[12]['words'])==6
for a in catalog:
    assert len(a['sections'])==3 and len(a['table']['rows'])>=3
    assert len(a['intro'])+sum(len(s['text']) for s in a['sections'])>600
    assert all(s['example'] and s['translation'] for s in a['sections'])
    assert len(a['quiz']['choices'])==3 and 0<=a['quiz']['answer']<3 and a['quiz']['explanation']
errors=[]

with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    ctx=b.new_context(viewport={'width':390,'height':744})
    ctx.route(BASE+'**',lambda r:r.fulfill(content_type='text/html',body=source))
    # The app is self-contained: no fetching column data, libraries or AI APIs.
    ctx.route('https://kmhrt16436-beep.github.io/**',lambda r:r.abort())
    p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE)
    assert p.evaluate('ENGLISH_COLUMN_LIBRARY')==catalog
    assert p.locator('#columnsNav').is_visible()
    assert p.evaluate('englishColumnGroups()[0].article.id')=='business-basics'
    raw=p.evaluate("""rows=>{state=initial();state.cards=rows.map((r,i)=>{const c=card(r);c.id='word-'+i;return c});state.folders.push({id:'heat',name:'熱・空気',kind:'general',deleted:false});for(let i=0;i<20;i++){const c=card(['熱の問題'+i,'答え','','','','',''],'heat');c.id='heat-'+i;state.cards.push(c)}state.session={date:today(),queue:[],done:0,doneByFolder:{},reviewCounts:{}};addDue();orderStudyQueue();persist();selectFolder('english');return syncString(state)}""",rows)
    groups=p.evaluate('englishColumnGroups().map(g=>({words:g.cards.map(c=>c.fields[0]),article:g.article.id}))')
    assert len(groups)==13 and [w for g in groups for w in g['words']]==[r[0] for r in rows]
    assert [g['article'] for g in groups]==[a['id'] for a in catalog[:13]]
    p.locator('#columnsNav').click();assert p.locator('.column-tile').count()==13
    assert '126語 · 13ページ' in p.locator('#columnSummary').inner_text()
    snapshot=p.evaluate('syncString(state)')
    # Each source group gets a full, distinct, useful article and a working quiz.
    for i,a in enumerate(catalog[:13]):
        p.evaluate('i=>openColumnPage(englishColumnGroups()[i].key)',i)
        assert p.locator('#columnPageTitle').inner_text()==a['title']
        assert p.locator('.column-word').count()==len(a['words'])
        assert p.locator('.column-page h3').count()==5
        p.locator('.column-choices button').nth((a['quiz']['answer']+1)%3).click()
        assert '正解は' in p.locator('.column-feedback').inner_text()
        p.locator('.column-choices button').nth(a['quiz']['answer']).click()
        assert p.locator('.column-feedback').inner_text().startswith('正解です。')
    assert p.evaluate('syncString(state)')==snapshot==raw
    # Sync must not reset reading position, answer feedback or focus.
    scroll=p.locator('#workspace').evaluate('(e)=>e.scrollTop')
    p.evaluate('applySyncedState(normalizedSync(state))')
    assert p.locator('.column-feedback').inner_text().startswith('正解です。')
    assert p.locator('#workspace').evaluate('(e)=>e.scrollTop')==scroll
    for width,height in [(360,640),(390,744),(1366,768)]:
        p.set_viewport_size({'width':width,'height':height});p.evaluate('resetColumnScroll()')
        assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert p.locator('#workspace').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
        p.screenshot(path=str(Path(tempfile.gettempdir())/f'flash-cards-columns-{width}.png'))
    print('PASS: 126 source words → 13 complete tailored pages; comparisons/examples/quizzes; mobile/desktop layout; sync preserves reading; no card/schedule/queue changes')
    # Set and tag scope: general subjects have no menu or reading breaks.
    p.locator('#folderSelect').select_option('heat')
    assert not p.locator('#columnsNav').is_visible() and p.evaluate('activeTab')=='study'
    for _ in range(12):p.evaluate('revealed=true;grade(true)')
    assert not p.locator('#columnBreakDialog').evaluate('(e)=>e.open')
    p.locator('#folderSelect').select_option('*')
    assert sum(len(g['words']) for g in p.evaluate('englishColumnGroups().map(g=>({words:g.cards.map(c=>c.fields[0])}))'))==126
    p.evaluate("for(const c of state.cards.slice(0,21))c.tags=['絞り込み'];persist();render();selectTag('絞り込み')")
    assert p.evaluate('englishColumnGroups().map(g=>g.cards.length)')==[10,10,1]
    p.evaluate("selectTag('');selectFolder('english');tab('study');localStorage.removeItem(columnProgressKey());columnProgressMemory.clear()")
    p.evaluate("window.oldReminder=columnProgressKey().slice(0,-10)+shiftDate(today(),-1);window.otherReminder=KEY+':column-break:'+encodeURIComponent(KEY+':account:another-user')+':'+today();localStorage.setItem(oldReminder,'old');localStorage.setItem(otherReminder,'keep')")
    print('PASS: English-only scope, general-subject study excluded, all-folders view excludes other subjects, tags regroup into ten-word pages with a final partial page')
    # The optional break counts distinct real answers, not retries or repeated tags.
    for i in range(9):p.evaluate('ok=>{revealed=true;grade(ok)}',i!=0)
    assert not p.locator('#columnBreakDialog').evaluate('(e)=>e.open')
    p.locator('.front').click();p.locator('.grade .primary').click()
    assert p.locator('#columnBreakDialog').evaluate('(e)=>e.open')
    state10=p.evaluate('syncString(state)');progress=p.evaluate('readColumnProgress(columnProgressKey())')
    assert len(progress['ids'])==10 and len(progress['pages'])==1 and progress['batch']==[]
    assert p.evaluate("localStorage.getItem(oldReminder)===null && localStorage.getItem(otherReminder)==='keep'")
    p.locator('#skipColumnBreak').click();assert p.evaluate('syncString(state)')==state10
    p.evaluate("()=>{const progress=readColumnProgress(columnProgressKey());const c=state.cards.find(c=>c.id===progress.ids[0]);offerEnglishColumn(c,true);offerEnglishColumn(c,false)}")
    assert p.evaluate('readColumnProgress(columnProgressKey())')==progress
    p.reload();assert p.evaluate('readColumnProgress(columnProgressKey())')==progress
    for _ in range(10):p.evaluate('revealed=true;grade(true)')
    assert p.locator('#columnBreakDialog').evaluate('(e)=>e.open')
    state20=p.evaluate('syncString(state)');p.locator('#readColumnBreak').click()
    assert p.evaluate('activeTab')=='columns' and p.locator('#columnPageTitle').is_visible()
    assert p.evaluate('syncString(state)')==state20
    assert len(p.evaluate('readColumnProgress(columnProgressKey()).ids'))==20
    p.locator('#columnReader').get_by_role('button',name='学習に戻る',exact=True).first.click();assert p.locator('.front').is_visible()
    print('PASS: tenth distinct English answer offers reading/skip; both preserve next card and history; retries/repeats excluded; counts survive reload; twentieth answer offers the next page')
    # New user words still get one real editorial page per ten, without inventing word meanings.
    p.evaluate("state=initial();state.cards=Array.from({length:21},(_,i)=>card(['customword'+i,'意味','','','','','']));state.session.queue=[];persist();render()")
    assert p.evaluate('englishColumnGroups().map(g=>g.cards.length)')==[10,10,1]
    assert p.evaluate('englishColumnGroups().every(g=>g.article.words.length===0)')
    p.locator('#columnsNav').click();p.locator('.column-tile button').first.click()
    assert '共通の語法コラム' in p.locator('#columnReader').inner_text()
    # Reminder records are per account, and private word lists close on account switches.
    before=p.evaluate('columnProgressKey()')
    p.evaluate("activeStorageKey=KEY+':account:other-user';render()")
    assert p.evaluate('columnProgressKey()')!=before and not p.evaluate('readColumnProgress(columnProgressKey()).ids')
    assert p.evaluate("activeColumnKey==='' && columnOwner===null")
    print('PASS: unknown words receive shared grammar pages; reminder counters and reader state are isolated across accounts')
    assert not errors,errors;b.close()
