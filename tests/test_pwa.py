"""Exercise the actual service worker on a trusted local origin; no live user data."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
import os,shutil,json
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
 def do_GET(self):
  if self.path.startswith('/vocab-app/rest/'):
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"private":"not-cacheable"}');return
  if self.path.startswith('/vocab-app/'):
   self.path=self.path[len('/vocab-app'):] or '/';super().do_GET();return
  self.send_error(404)
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/vocab-app/';errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);context=browser.new_context(viewport={'width':390,'height':744});p=context.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(base+'index.html');p.wait_for_function("navigator.serviceWorker.controller!==null");p.evaluate('navigator.serviceWorker.ready');assert p.evaluate('isSecureContext')
  manifest=p.evaluate("async()=>await(await fetch('./manifest.webmanifest')).json()");assert manifest['display']=='standalone' and manifest['scope']=='./' and manifest['start_url']=='./index.html';assert {x['sizes'] for x in manifest['icons']}=={'192x192','512x512'}
  session=context.new_cdp_session(p);report=session.send('Page.getAppManifest');assert not [e for e in report.get('errors',[]) if e.get('critical')],report
  # App data remain in localStorage; the service worker only caches static resources.
  p.evaluate("(()=>{const folder={id:'history',name:'世界史',kind:'general',deleted:false};state.folders.push(folder);const c=card(['フランス革命が始まった年は？','1789年','','','','',new URL('toeic-033.png',location.href).href],folder.id);state.cards.push(c);enqueue(c.id);selectFolder(folder.id);persist();})()");p.locator('.front').click();p.locator('.grade .negative').click();before=p.evaluate('JSON.stringify(state)');assert p.evaluate('studyItem().retry')
  p.evaluate("async()=>{for(let n=1;n<=33;n++){const r=await fetch('./toeic-'+String(n).padStart(3,'0')+'.png');if(!r.ok)throw Error('missing image');await r.arrayBuffer()}await fetch('./rest/v1/private')}")
  cache=p.evaluate("async()=>{const names=await caches.keys(),result={};for(const name of names)result[name]=(await(await caches.open(name)).keys()).map(r=>r.url);return result}")
  images=next(v for k,v in cache.items() if k.endswith('images-v1'));assert len(images)==32 and not any('toeic-001.png' in u for u in images);assert all('/rest/' not in u for values in cache.values() for u in values)
  assert p.evaluate("async()=>!(await navigator.serviceWorker.getRegistration(new URL('/outside/',location.href)))")
  context.set_offline(True);p.reload();p.wait_for_selector('.front');assert p.evaluate('JSON.stringify(state)')==before;assert p.locator('#folderSelect').input_value()=='history';p.locator('.front').click();p.wait_for_function("document.querySelector('.illustration')?.naturalWidth===512");assert p.locator('.grade').is_visible();p.locator('.grade .primary').click();assert p.evaluate("state.cards.find(c=>c.folderId==='history').memory.reviews")==2
  p.reload();assert p.evaluate("state.cards.find(c=>c.folderId==='history').memory.reviews")==2;context.set_offline(False)
  # Locally uploaded images remain available offline without any public image URL.
  p.evaluate("async()=>{const canvas=document.createElement('canvas');canvas.width=64;canvas.height=48;canvas.getContext('2d').fillRect(0,0,64,48);const blob=await new Promise(r=>canvas.toBlob(r,'image/png')),ref=await putCardImage(blob,imageOwner()),c=state.cards.find(c=>c.folderId==='history');c.fields[6]=ref;state.session.queue=[{id:c.id,retry:true}];revealed=false;persist();render()}")
  context.set_offline(True);p.reload();p.locator('.front').click();p.wait_for_function("document.querySelector('.illustration')?.naturalWidth===64");assert p.locator('.grade .primary').is_visible();assert p.evaluate("state.cards.find(c=>c.folderId==='history').memory.reviews")==2;context.set_offline(False)
  # Browser install prompt wiring, cancellation and installed-state display.
  p.locator('[data-tab=data]').click();p.evaluate("(()=>{const e=new Event('beforeinstallprompt',{cancelable:true});e.prompt=async()=>{window.promptCalls=(window.promptCalls||0)+1};e.userChoice=Promise.resolve({outcome:'dismissed'});window.dispatchEvent(e)})()");assert p.locator('#installApp').is_visible();p.locator('#installApp').click();assert p.evaluate('window.promptCalls')==1;assert not p.locator('#installApp').is_visible()
  p.evaluate("Object.defineProperty(navigator,'standalone',{value:true,configurable:true});renderInstall()");assert '起動しています' in p.locator('#pwaStatus').inner_text();assert not p.locator('#pwaInstallGuide').is_visible()
  # Updating is opt-in: a waiting worker does not reload an active study session.
  p.evaluate("window.updateMessages=[];pwaRegistration={waiting:{postMessage:m=>updateMessages.push(m)}};renderInstall()");assert p.locator('#updateApp').is_visible();assert p.evaluate('pwaReloadRequested') is False;p.locator('#updateApp').click();assert p.evaluate('updateMessages')==[{'type':'SKIP_WAITING'}];assert p.evaluate('pwaReloadRequested') is True
  assert not errors,errors;print('PASS: manifest and icons, actual service worker, scoped static caches, bounded 32-image cache, private requests uncached, offline reload with folders/history/images, offline grades persist, install flow and opt-in update.');browser.close()
finally:server.shutdown();server.server_close()
