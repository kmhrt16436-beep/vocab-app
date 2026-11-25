"""Migration inspection must not overwrite cards or opt a device in before its button is pressed."""
from pathlib import Path
import base64, copy, hashlib, json, os, shutil
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
APP='https://kmhrt16436-beep.github.io/vocab-app/'
AUTH='https://glpnosfxkewlqzpqnsep.supabase.co'
API='https://flashcards-api-97c87b4b3a.azurewebsites.net/api'
KEY='daily-words-v1';UID='11111111-1111-4111-8111-111111111111'
photo='data:image/png;base64,'+base64.b64encode(b'pixel-bytes-test').decode()
payload={'version':4,'cards':[{'id':'one','fields':['word','名）意味','','related','An example.','例文です。',photo],'folderId':'english','tags':['公式問題集9'],'stage':3,'due':'2026-12-01','memory':{'reviews':7,'lapses':1}}],'folders':[{'id':'english','name':'英語','kind':'vocabulary','deleted':False}],'settings':{},'session':{'date':'2026-11-26','queue':[]}}
local=copy.deepcopy(payload);local['cards'][0]['fields'][6]='card-image:'+hashlib.sha256(b'pixel-bytes-test').hexdigest()
errors=[];events=[];mode={'api_error':False,'refresh':False,'wrong_user':False,'local_edit':False,'auth_403':False,'api_403':False,'legacy_403':False}
def backend(route):
    url=route.request.url;path=urlsplit(url).path;events.append((route.request.method,path))
    if url.startswith(API):
        if mode['api_403']:route.fulfill(status=403,json={'code':'sync_error'});return
        if mode['refresh']:mode['refresh']=False;route.fulfill(status=401,json={'message':'expired'});return
        if mode['api_error']:route.fulfill(status=503,json={'message':'offline'});return
        route.fulfill(json={'revision':1,'payload':payload});return
    if path=='/auth/v1/user' and mode['auth_403']:
        mode['auth_403']=False;route.fulfill(status=403,json={'error_code':'session_not_found'});return
    if path=='/auth/v1/user':route.fulfill(json={'id':'other-user' if mode['wrong_user'] else UID,'email':'a@example.com'});return
    if path=='/auth/v1/token':route.fulfill(json={'access_token':'fresh-token','refresh_token':'new-refresh','user':{'id':UID,'email':'a@example.com'}});return
    if path=='/rest/v1/word_progress' and mode['legacy_403']:route.fulfill(status=403,json={'code':'42501'});return
    if path=='/rest/v1/word_progress':route.fulfill(json=[{'payload':payload}]);return
    raise AssertionError('Unexpected request '+path)
def fresh(browser,data=local,login=True):
    context=browser.new_context(viewport={'width':390,'height':844});context.route(AUTH+'/**',backend);context.route(API+'/**',backend)
    context.route(APP+'azure-migration.html',lambda r:r.fulfill(content_type='text/html',body=(ROOT/'azure-migration.html').read_text()))
    context.route(APP+'index.html',lambda r:r.fulfill(content_type='text/html',body='<p>単語帳</p>'))
    p=context.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(APP+'azure-migration.html')
    p.evaluate('''([key,auth,uid,data,login])=>{
      if(login){localStorage.setItem(key+':cloud-config',JSON.stringify({url:auth,key:'sb_publishable_public_key_test_12345'}));localStorage.setItem(key+':cloud-auth',JSON.stringify({access_token:'token',refresh_token:'refresh',user:{id:uid,email:'a@example.com'}}));}
      localStorage.setItem(key+':account:'+uid,JSON.stringify(data));
    }''',[KEY,AUTH,UID,data,login]);return context,p
def checked(p):p.locator('#check').click();p.wait_for_function("!document.getElementById('check').disabled")
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    ctx,p=fresh(b);before=p.evaluate('(key)=>localStorage.getItem(key)',KEY+':account:'+UID)
    checked(p);assert p.locator('#switch').is_enabled();assert '一致しました' in p.locator('#comparison').text_content()
    assert p.evaluate('(key)=>localStorage.getItem(key)',KEY+':account:'+UID)==before
    assert p.evaluate('(key)=>localStorage.getItem(key)',KEY+':azure-storage:'+AUTH) is None
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.locator('#switch').click();p.wait_for_url(APP+'index.html');assert p.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',KEY+':azure-storage:'+AUTH)==API;ctx.close()
    ctx,p=fresh(b);mode['api_error']=True;checked(p);assert p.locator('#switch').is_disabled();assert 'HTTP 503' in p.locator('#status').text_content();assert p.evaluate('(key)=>localStorage.getItem(key)',KEY+':azure-storage:'+AUTH) is None;ctx.close();mode['api_error']=False
    unsynced=copy.deepcopy(local);unsynced['cards'][0]['memory']['reviews']=8;ctx,p=fresh(b,unsynced);checked(p);assert p.locator('#switch').is_disabled();assert '未同期' in p.locator('#localStatus').text_content();ctx.close()
    ctx,p=fresh(b);mode['refresh']=True;checked(p);assert p.locator('#switch').is_enabled();assert p.evaluate('(key)=>JSON.parse(localStorage.getItem(key)).access_token',KEY+':cloud-auth')=='fresh-token';ctx.close()
    ctx,p=fresh(b);mode['auth_403']=True;checked(p);assert p.locator('#switch').is_enabled();assert p.evaluate('(key)=>JSON.parse(localStorage.getItem(key)).access_token',KEY+':cloud-auth')=='fresh-token';ctx.close()
    for key,label,code in [('api_403','Azureへの接続','sync_error'),('legacy_403','旧保存先（Supabase）の読み込み','42501')]:
        ctx,p=fresh(b);mode[key]=True;checked(p);assert p.locator('#switch').is_disabled();text=p.locator('#status').text_content();assert label in text and 'HTTP 403' in text and code in text,text;assert 'fresh-token' not in text and 'sb_publishable_' not in text;assert p.evaluate('(key)=>localStorage.getItem(key)',KEY+':azure-storage:'+AUTH) is None;ctx.close();mode[key]=False
    ctx,p=fresh(b);mode['wrong_user']=True;checked(p);assert p.locator('#switch').is_disabled();assert '本人確認が一致しません' in p.locator('#status').text_content();ctx.close();mode['wrong_user']=False
    ctx,p=fresh(b);checked(p);p.evaluate('(key)=>localStorage.setItem(key,"changed by another tab")',KEY+':account:'+UID);p.locator('#switch').click();assert p.locator('#switch').is_disabled();assert p.evaluate('(key)=>localStorage.getItem(key)',KEY+':azure-storage:'+AUTH) is None;ctx.close()
    count=len(events);ctx,p=fresh(b,login=False);checked(p);assert len(events)==count;assert '先にログイン' in p.locator('#status').text_content();ctx.close()
    assert not errors,errors;assert not any(method=='PUT' for method,path in events)
    print('PASS: image-byte comparison, progress/tag counts, explicit per-device opt-in, no card overwrite, offline rejection, unsynced changes, token refresh, identity changes, cross-tab edits, missing login and mobile layout')
    b.close()
