"""Azure cutover keeps account isolation, merge baselines, images and offline durability."""
from pathlib import Path
from urllib.parse import urlsplit
import copy, os, shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
API='https://flashcards-api-test.azurewebsites.net/api'
AUTH='https://test.supabase.co'
backend={};events=[];errors=[];mode={'file':'enabled','offline':False,'expire':False};refreshes=[]
def route_app(route):
    import json
    source=(ROOT/'index.html').read_text()
    config={'enabled':mode['file']=='enabled','authUrl':AUTH,'dataUrl':API}
    source=source.replace("const AZURE_STORAGE_CONFIG={enabled:false,authUrl:'https://glpnosfxkewlqzpqnsep.supabase.co',dataUrl:''};",'const AZURE_STORAGE_CONFIG='+json.dumps(config)+';')
    route.fulfill(content_type='text/html',body=source)
def route_auth(route):
    path=urlsplit(route.request.url).path
    if path=='/auth/v1/token':
        refreshes.append(1);route.fulfill(json={'access_token':'a-fresh','refresh_token':'refresh-a','user':{'id':'a','email':'a@example.com'}});return
    raise AssertionError('Unexpected Supabase data request after cutover: '+path)
def route_api(route):
    r=route.request;uid=r.headers.get('authorization','').split(' ')[-1].replace('-fresh','');events.append((r.method,urlsplit(r.url).query,uid))
    if mode['offline']:route.abort();return
    if mode['expire']:mode['expire']=False;route.fulfill(status=401,json={'message':'expired'});return
    if r.method=='GET':
        value=backend.get(uid)
        if value and urlsplit(r.url).query=='metadata=1':value={'revision':value['revision']}
        route.fulfill(json=value);return
    data=r.post_data_json;current=backend.get(uid,{'revision':0})
    if data['expected_revision']!=current['revision']:route.fulfill(status=409,json={'code':'40001'});return
    backend[uid]={'revision':current['revision']+1,'payload':copy.deepcopy(data['new_payload'])};route.fulfill(json={'revision':backend[uid]['revision']})
def settled(p):p.wait_for_function('cloudReady&&!cloudBusy')
def sync(p):p.evaluate('syncCloud(true)');settled(p)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    ctx=browser.new_context();ctx.route('https://azure.test/**',route_app);ctx.route(AUTH+'/**',route_auth);ctx.route(API+'/**',route_api)
    p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto('https://azure.test/')
    base=p.evaluate('normalizedSync(initial())');remote=copy.deepcopy(base);deleted=remote['cards'].pop(0)['id'];remote['session']['queue']=[q for q in remote['session']['queue'] if q['id']!=deleted]
    remote['cards'][0]['tags']=['公式問題集9'];remote['cards'][0]['fields'][6]='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg=='
    backend['a']={'revision':1,'payload':remote}
    p.evaluate('''([auth,base])=>{
      localStorage.setItem(CONFIG_KEY,JSON.stringify({url:auth,key:'sb_publishable_test_public_key_12345'}));
      localStorage.setItem(AUTH_KEY,JSON.stringify({access_token:'a',refresh_token:'refresh-a',user:{id:'a',email:'a@example.com'}}));
      localStorage.setItem(KEY+':account:a',JSON.stringify(base));
      localStorage.setItem(KEY+':autosync:'+auth+':a',JSON.stringify({revision:42,base}));
    }''',[AUTH,base]);mode['offline']=True;p.reload();settled(p)
    assert p.evaluate('cloudRevision')==0 and p.evaluate('!!cloudBase'),'failed first migration must retain the old deletion baseline'
    mode['offline']=False;p.reload();settled(p)
    assert p.evaluate('cloudDataUrl')==API
    assert not p.evaluate('(id)=>state.cards.some(c=>c.id===id)',deleted),'legacy merge baseline must preserve Azure deletion'
    assert p.evaluate('cloudRevision')==backend['a']['revision'] and p.evaluate('cloudRevision')<42,'Supabase revision 42 must not be reused for Azure'
    assert p.evaluate("state.cards.some(c=>c.tags.includes('公式問題集9'))")
    assert p.evaluate("state.cards.some(c=>/^card-image:/.test(c.fields[6]))")
    assert 'Azure' in p.locator('#cloudIdentity').text_content()
    count=len(events);p.evaluate('syncCloud()');settled(p);assert events[-1][1]=='metadata=1';assert len(events)==count+1
    p.evaluate("state.cards[0].fields[2]='PC Azure edit';persist();clearTimeout(cloudTimer)");sync(p)
    assert backend['a']['payload']['cards'][0]['fields'][2]=='PC Azure edit'
    assert backend['a']['payload']['cards'][0]['fields'][6].startswith('data:image/png;base64,')
    mode['expire']=True;sync(p);assert len(refreshes)==1
    mode['offline']=True;p.evaluate("state.cards[0].fields[2]='offline saved';persist();clearTimeout(cloudTimer)");sync(p)
    assert p.evaluate("JSON.parse(localStorage.getItem(activeStorageKey)).cards[0].fields[2]")=='offline saved'
    assert '未同期' in p.locator('#cloudStatus').text_content()
    mode['offline']=False;mode['file']='offline';p.reload();settled(p);assert p.evaluate('cloudDataUrl')==API
    assert backend['a']['payload']['cards'][0]['fields'][2]=='offline saved'
    mode['file']='disabled';p.reload();settled(p);assert p.evaluate('cloudDataUrl')==API,'disabled deployment file must not silently roll an existing Azure device back'
    p.evaluate("loginCloud({access_token:'b',refresh_token:'refresh-b',user:{id:'b',email:'b@example.com'}})");settled(p)
    assert not p.evaluate("state.cards.some(c=>c.fields[2]==='offline saved')")
    assert 'b' in backend
    assert not errors,errors
    print('PASS: automatic Azure cutover, legacy deletion baseline, separate revisions, private images, tags, metadata polling, token refresh, offline save/reload, sticky endpoint and account isolation')
    browser.close()
