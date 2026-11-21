"""Backfill reviewed related-word senses without losing cards, images or progress."""
from pathlib import Path
import copy,csv,io,json,os,re,shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='https://related-pos.test/'
source=(ROOT/'index.html').read_text()
rows=list(csv.reader(io.StringIO((ROOT/'TOEIC_images.csv').read_text(encoding='utf-8-sig'))))
assert len(rows)==126 and all(len(r)==7 for r in rows)
old_rows=copy.deepcopy(rows)
for r in old_rows:r[3]=re.sub(r'(?:名|動|形|副|前|接|代)）(?=[A-Za-z])','',r[3])
assert sum(a[3]!=b[3] for a,b in zip(rows,old_rows))==83
backend={};writes=[];errors=[]

def cloud(route):
    path=route.request.url.split('https://test.supabase.co',1)[1]
    if path.startswith('/rest/v1/word_progress'):
        route.fulfill(json=[backend] if backend else []);return
    if path=='/rest/v1/rpc/save_word_progress':
        body=route.request.post_data_json
        if body['expected_revision']!=backend.get('revision',0):
            route.fulfill(status=409,json={'code':'40001'});return
        backend.update(revision=body['expected_revision']+1,payload=body['new_payload'])
        writes.append(copy.deepcopy(backend));route.fulfill(json={'revision':backend['revision']});return
    raise AssertionError(path)

with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    ctx=b.new_context(viewport={'width':390,'height':744})
    ctx.route(BASE+'**',lambda r:r.fulfill(content_type='text/html',body=source))
    ctx.route('https://test.supabase.co/**',cloud)
    p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE)
    assert '派）名）submission：提出、服従' in p.evaluate('initial().cards[0].fields[3]')
    assert p.evaluate('s=>annotateRelatedWords(s)',' 派）restoration：修復 ／類）hand in：提出する\r\n類）形）obtainable：入手可能な')== ' 派）名）restoration：修復 ／類）hand in：提出する\r\n類）形）obtainable：入手可能な'
    # Distinguish nouns, verbs, adjectives, adverbs and prepositions by the actual sense.
    for old,new in [
        ('派）restoration：修復','派）名）restoration：修復'),
        ('関連）fine：罰金','関連）名）fine：罰金'),
        ('対）reward：褒賞を与える','対）動）reward：褒賞を与える'),
        ('派）short：短い','派）形）short：短い'),
        ('関連）neatly：きちんと','関連）副）neatly：きちんと'),
        ('類）regarding：～に関して','類）前）regarding：～に関して'),
        ('派）名）customization：自分で追加した説明','派）名）customization：自分で追加した説明'),
        ('類）novelword：未知の用語','類）novelword：未知の用語'),
        ('関連）might：～かもしれない','関連）might：～かもしれない'),
    ]:assert p.evaluate('s=>annotateRelatedWords(s)',old)==new
    raw=p.evaluate("""rows=>{const x=initial();x.cards=rows.map((fields,i)=>{const c=card(fields);c.id='registered-'+i;c.tags=['自分のタグ'];c.stage=3;c.due=after(5);c.memory={lastReviewed:shiftDate(today(),-2),stability:7,difficulty:.4,reviews:5,successes:4,lapses:1,streak:2,scheduledDays:7,estimated:false};return c});x.cards[28].fields[6]='https://example.test/my-picture.png';x.folders.push({id:'science',name:'他の教科',kind:'general',deleted:false});const general=card(['理科の用語','答え','','派）restoration：修復','','',''],'science');general.due=after(5);x.cards.push(general);x.session={date:today(),queue:[],done:13,doneByFolder:{english:13},reviewCounts:{}};localStorage.setItem(KEY,JSON.stringify(x));return x}""",old_rows)
    assert p.evaluate('x=>relatedWordPosPending(x)',raw)
    p.reload();updated=p.evaluate('state')
    for i,(before,after) in enumerate(zip(raw['cards'],updated['cards'])):
        expected=copy.deepcopy(before)
        if i<126:expected['fields'][3]=rows[i][3]
        assert after==expected,(i,before,after)
    assert updated['session']==raw['session'] and len(updated['cards'])==127
    assert not p.evaluate('x=>relatedWordPosPending(x)',updated)
    p.reload();assert p.evaluate('state')==updated
    print('PASS: 126 registered cards updated by sense; IDs/images/tags/meanings/examples/history/session unchanged; phrases, explicit labels, unknown words and other subjects preserved; reload idempotent')
    # Old CSV and updated CSV must resolve to the same cards, not duplicate reviews.
    p.evaluate("state=initial();state.cards=[];state.session.queue=[];persist();render()")
    p.locator('[data-tab=data]').click()
    for batch in [old_rows,rows]:
        stream=io.StringIO();csv.writer(stream).writerows(batch)
        p.locator('#csv').fill(stream.getvalue());p.locator('#importCsv').click()
        assert p.evaluate('state.cards.length')==126
    p.locator('[data-tab=cards]').click();p.evaluate("edit(state.cards.find(c=>c.fields[0]==='restore').id)")
    assert p.locator('#relatedPosHelp').is_visible()
    assert p.locator('#f3').input_value()=='派）名）restoration：修復／関連）動）repair：修理する'
    p.locator('#f3').fill('派）名）restoration：修復／関連）動）repair：修理する\n自分のメモ')
    p.locator('#saveCardButton').click();p.wait_for_function('!imageEditorSaving')
    assert p.evaluate("state.cards.find(c=>c.fields[0]==='restore').fields[3].endsWith('自分のメモ')")
    p.evaluate("edit();document.getElementById('cardFolder').value='english';updateEditorLabels()")
    assert '派）名）' in p.locator('#f3').get_attribute('placeholder')
    print('PASS: old/new CSV imports share cards; editor shows POS guidance and retains manual edits')
    # An old v4 cloud payload must actually be saved with the backfill exactly once.
    backend.update(revision=7,payload=raw)
    p.evaluate("state=initial();state.cards=[];state.session.queue=[];cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};loginCloud({access_token:'user-a',refresh_token:'refresh-a',user:{id:'user-a',email:'test@example.com'}})")
    p.wait_for_function('cloudReady&&!cloudBusy')
    assert len(writes)==1 and backend['payload']==updated
    for _ in range(3):p.evaluate('clearTimeout(cloudTimer);syncCloud()')
    assert len(writes)==1
    p.evaluate("x=>loginCloud(x)",{'access_token':'user-a','refresh_token':'refresh-a','user':{'id':'user-a','email':'test@example.com'}})
    p.wait_for_function('cloudReady&&!cloudBusy');assert len(writes)==1
    print('PASS: existing cloud v4 text saved once; repeated sync and reconnect do not rewrite or duplicate cards')
    assert not errors,errors;b.close()
