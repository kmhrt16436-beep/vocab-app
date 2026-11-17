"""Exercise file/paste/touch crops, durable images, portable JSON and private sync."""
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import base64,copy,io,json,os,shutil,tempfile
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='https://photos.test/';source=(ROOT/'index.html').read_text();errors=[];backend={};writes=[];reads=[]
image=Image.new('RGB',(800,600));draw=ImageDraw.Draw(image);draw.rectangle((0,0,399,299),fill=(220,20,20));draw.rectangle((400,0,799,299),fill=(20,180,20));draw.rectangle((0,300,399,599),fill=(20,20,220));draw.rectangle((400,300,799,599),fill=(220,200,20));buffer=io.BytesIO();image.save(buffer,'PNG');png=buffer.getvalue();encoded=base64.b64encode(png).decode()
fixture={'name':'quadrants.png','mimeType':'image/png','buffer':png}
def cloud(route):
 req=route.request;path=urlsplit(req.url).path;uid=req.headers.get('authorization','Bearer user-a').split(' ')[-1]
 if path=='/auth/v1/logout':route.fulfill(json={});return
 if path=='/rest/v1/word_progress':
  select=parse_qs(urlsplit(req.url).query).get('select',[''])[0];reads.append(select);rows=[backend[uid]] if uid in backend else [];route.fulfill(json=[{'revision':r['revision']} for r in rows] if select=='revision' else rows);return
 if path=='/rest/v1/rpc/save_word_progress':
  body=req.post_data_json
  if body['expected_revision']!=backend.get(uid,{}).get('revision',0):route.fulfill(status=409,json={'code':'40001'});return
  backend[uid]={'revision':body['expected_revision']+1,'payload':body['new_payload']};writes.append(copy.deepcopy(backend[uid]));route.fulfill(json={'revision':backend[uid]['revision']});return
 raise AssertionError(path)
def login(p,uid='user-a'):
 p.evaluate("uid=>{cloudConfig={url:'https://test.supabase.co',key:'sb_publishable_test_public_key_12345'};return loginCloud({access_token:uid,refresh_token:uid+'-refresh',user:{id:uid,email:uid+'@example.com'}})}",uid);p.wait_for_function('cloudReady&&!cloudBusy')
def sync(p):p.evaluate('clearTimeout(cloudTimer);syncCloud()')
def crop_values(p,x,y,w,h):
 p.locator('#imageCropDialog').wait_for(state='visible')
 if not p.locator('#cropNumbers').evaluate('(e)=>e.open'):p.locator('#cropNumbers summary').click()
 for key,val in [('w',w),('h',h),('x',x),('y',y)]:p.locator('#crop-'+key).fill(str(val));p.locator('#crop-'+key).dispatch_event('change')
def apply(p):p.locator('#applyImageCrop').click();p.wait_for_function("!document.getElementById('imageCropDialog').open")
def pixels(data):
 im=Image.open(io.BytesIO(base64.b64decode(data.split(',',1)[1]))).convert('RGB');return im,im.getpixel((im.width//2,im.height//2))
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 def page(width=390,height=744):
  ctx=b.new_context(viewport={'width':width,'height':height},has_touch=True,accept_downloads=True);ctx.route(BASE+'**',lambda r:r.fulfill(status=200,content_type='text/html',body=source));ctx.route('https://test.supabase.co/**',cloud);p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE+'index.html');return p
 p=page();p.locator('[data-tab=cards]').click();p.locator('#addCard').click();p.locator('#f0').fill('photo-word');p.locator('#f1').fill('画像の意味');p.locator('#cardTags').fill('写真テスト');p.locator('#cardImageFile').set_input_files(fixture);p.locator('#imageCropDialog').wait_for(state='visible');p.wait_for_function('document.getElementById("cropSurface").clientWidth>0')
 # Drag actual handles to select only the upper-right green quadrant.
 rect=p.locator('#cropSurface').bounding_box();corner=p.locator('[data-corner=nw]').bounding_box();sx=corner['x']+14;sy=corner['y']+14;p.mouse.move(sx,sy);p.mouse.down();p.mouse.move(sx+rect['width']*.5,sy,steps=8);p.mouse.up();corner=p.locator('[data-corner=se]').bounding_box();sx=corner['x']+14;sy=corner['y']+14;p.mouse.move(sx,sy);p.mouse.down();p.mouse.move(sx,sy-rect['height']*.5,steps=8);p.mouse.up()
 selected=p.evaluate('imageCrop.rect');assert abs(selected['x']-.5)<.02 and abs(selected['h']-.5)<.02,selected
 p.screenshot(path=str(Path(tempfile.gettempdir())/'flash-cards-crop-mobile.png'));apply(p);uri=p.locator('#f6').input_value();im,pixel=pixels(uri);assert 390<=im.width<=410 and 290<=im.height<=310 and pixel[1]>140 and pixel[0]<50 and pixel[2]<50,(im.size,pixel);assert not p.locator('#f6').is_visible();assert p.locator('#cardImagePreview').is_visible()
 # Cancelling another crop never changes the draft, and cancelling the form never changes the saved card.
 p.locator('#recropCardImage').click();p.locator('#resetImageCrop').click();p.locator('#cancelImageCrop').click();assert p.locator('#f6').input_value()==uri
 p.locator('#recropCardImage').click();p.locator('#rotateImageCrop').click();p.locator('#cancelImageCrop').click();p.locator('#recropCardImage').click();assert p.evaluate('[imageCrop.bitmap.width,imageCrop.bitmap.height]')==[800,600];p.locator('#cancelImageCrop').click()
 p.locator('#cardImageFile').set_input_files(fixture);p.locator('#imageCropDialog').wait_for(state='visible');p.locator('#cancelImageCrop').click();assert p.locator('#f6').input_value()==uri;p.locator('#recropCardImage').click();assert p.evaluate('[imageCrop.bitmap.width,imageCrop.bitmap.height]')==[800,600];p.locator('#cancelImageCrop').click()
 p.locator('#saveCardButton').click();p.wait_for_function("document.getElementById('editor').hidden");c=p.evaluate("state.cards.find(c=>c.fields[0]==='photo-word')");ref=c['fields'][6];assert ref.startswith('card-image:');assert 'data:image' not in p.evaluate('localStorage.getItem(KEY)')
 p.evaluate("selectTag('写真テスト');tab('study')");p.locator('.front').click();p.wait_for_function("document.querySelector('.illustration')?.src.startsWith('blob:')&&document.querySelector('.illustration').naturalWidth>0");assert p.locator('.grade .primary').is_visible();p.reload();p.locator('.front').click();p.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0");assert p.evaluate("state.cards.find(c=>c.fields[0]==='photo-word').fields[6]")==ref
 print('PASS: file selection and handle crop produce the exact green quadrant; image persists in IndexedDB and survives reload; localStorage stores references; grading fits mobile')
 # Export carries actual pixels; a fresh isolated browser can restore it with no old image database.
 p.locator('[data-tab=data]').click()
 with p.expect_download() as info:p.locator('#exportJson').click()
 exported=json.load(open(info.value.path()));uploaded=next(c for c in exported['cards'] if c['fields'][0]=='photo-word');assert uploaded['fields'][6].startswith('data:image/');assert pixels(uploaded['fields'][6])[1][1]>140
 restored=page();restored.locator('[data-tab=data]').click();restored.locator('#jsonText').fill(json.dumps(exported,ensure_ascii=False));restored.once('dialog',lambda d:d.accept());restored.locator('#importJson').click();restored.wait_for_function("document.getElementById('jsonStatus').textContent.includes('復元しました')");restored.evaluate("selectTag('写真テスト');tab('study')");restored.locator('.front').click();restored.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0");assert restored.evaluate("state.cards.find(c=>c.fields[0]==='photo-word').fields[6]")==ref
 print('PASS: image-inclusive JSON restores the actual image in a fresh browser without the source device database')
 # Re-crop a saved image, then cancel the card edit: existing photo and memory are preserved.
 p.evaluate("tab('cards');edit(state.cards.find(c=>c.fields[0]==='photo-word').id)");before=p.evaluate("state.cards.find(c=>c.fields[0]==='photo-word')");p.locator('#recropCardImage').click();crop_values(p,0,0,50,100);apply(p);p.locator('#cancelEdit').click();assert p.evaluate("state.cards.find(c=>c.fields[0]==='photo-word')")==before
 # Paste events accept copied screenshots. Touch movement and rotation are real UI actions.
 p.locator('#addCard').click();p.locator('#f0').fill('pasted');p.locator('#f1').fill('貼り付け')
 p.evaluate("s=>{const a=Uint8Array.from(atob(s),c=>c.charCodeAt(0)),dt=new DataTransfer();dt.items.add(new File([a],'clipboard.png',{type:'image/png'}));document.getElementById('f1').dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))}",encoded);p.locator('#imageCropDialog').wait_for(state='visible');crop_values(p,20,20,60,60)
 r=p.locator('#cropSelection').bounding_box();start={'x':r['x']+r['width']/2,'y':r['y']+r['height']/2};old=p.evaluate('imageCrop.rect');cdp=p.context.new_cdp_session(p);cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[start]});cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start['x']+10,'y':start['y']+10}]});cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});assert p.evaluate('imageCrop.rect.x')>old['x']
 p.locator('#rotateImageCrop').click();assert p.evaluate('[imageCrop.bitmap.width,imageCrop.bitmap.height]')==[600,800];apply(p);p.locator('#saveCardButton').click();p.wait_for_function("document.getElementById('editor').hidden");assert p.evaluate("state.cards.some(c=>c.fields[0]==='pasted'&&CARD_IMAGE_REF.test(c.fields[6]))")
 # Dropped files and the paste button open the same crop flow without saving accidentally.
 p.locator('#addCard').click();n=p.evaluate('state.cards.length')
 p.evaluate("s=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(s),c=>c.charCodeAt(0))],'drop.png',{type:'image/png'}));document.getElementById('cardImageTools').dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}))}",encoded);p.locator('#imageCropDialog').wait_for(state='visible');p.set_viewport_size({'width':360,'height':640});assert p.locator('#applyImageCrop').bounding_box()['y']+p.locator('#applyImageCrop').bounding_box()['height']<=640;p.screenshot(path=str(Path(tempfile.gettempdir())/'flash-cards-crop-small.png'));p.locator('#cancelImageCrop').click();p.set_viewport_size({'width':390,'height':744})
 p.evaluate("s=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{read:async()=>[{types:['image/png'],getType:async()=>inlineImageBlob('data:image/png;base64,'+s)}]}})",encoded);p.locator('#pasteCardImage').click();p.locator('#imageCropDialog').wait_for(state='visible');p.locator('#cancelImageCrop').click();p.evaluate('delete navigator.clipboard');p.locator('#cancelEdit').click();assert p.evaluate('state.cards.length')==n
 # Camera orientation is honored, and re-encoding removes the original photo metadata.
 camera=Image.new('RGB',(80,40),(220,20,20));ImageDraw.Draw(camera).rectangle((40,0,79,39),fill=(20,180,20));exif=Image.Exif();exif[274]=6;out=io.BytesIO();camera.save(out,'JPEG',quality=95,exif=exif);camera_uri='data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
 oriented=p.evaluate("async data=>{const bitmap=await decodeCropImage(inlineImageBlob(data)),blob=await encodeImageCrop({bitmap,rect:{x:0,y:0,w:1,h:1}});bitmap.close?.();return blobDataURL(blob)}",camera_uri);oriented_img,_=pixels(oriented);assert oriented_img.size==(40,80);assert oriented_img.getpixel((20,10))[0]>150 and oriented_img.getpixel((20,70))[1]>130;assert not Image.open(io.BytesIO(base64.b64decode(oriented.split(',',1)[1]))).getexif()
 print('PASS: drop and paste-button flows; camera EXIF orientation; exported crop excludes original EXIF metadata')
 # Invalid files keep the existing photo and text intact; removing a photo preserves learning data.
 p.evaluate("edit(state.cards.find(c=>c.fields[0]==='photo-word').id)");old=p.locator('#f6').input_value();p.locator('#cardImageFile').set_input_files({'name':'bad.png','mimeType':'image/png','buffer':b'not an image'});p.wait_for_function("document.getElementById('cardImageStatus').textContent!==''&&!document.getElementById('cardImageStatus').textContent.includes('開いています')");assert p.locator('#f6').input_value()==old;p.locator('#removeCardImage').click();p.locator('#saveCardButton').click();p.wait_for_function("document.getElementById('editor').hidden");after=p.evaluate("state.cards.find(c=>c.fields[0]==='photo-word')");assert after['fields'][6]=='' and after['memory']==before['memory'] and after['id']==before['id']
 print('PASS: paste, touch movement, rotation, re-crop cancel, invalid-file handling and photo removal all preserve card text/history')
 # A storage failure leaves the draft open and the saved collection untouched.
 p.locator('#addCard').click();p.locator('#f0').fill('保存失敗テスト');p.locator('#f1').fill('答え');prior=p.evaluate('JSON.stringify(state)')
 p.evaluate("()=>{window.realSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key===activeStorageKey)throw new DOMException('quota','QuotaExceededError');return realSetItem.call(this,key,value)}}");p.locator('#saveCardButton').click();p.wait_for_function("document.getElementById('cardImageStatus').textContent.includes('保存できません')");assert p.evaluate('JSON.stringify(state)')==prior;assert p.locator('#editor').is_visible();p.evaluate('()=>{Storage.prototype.setItem=realSetItem}');p.locator('#cancelEdit').click()
 # Cancelling while image decoding is pending cannot reopen a crop or attach a late photo.
 p.locator('#addCard').click();p.evaluate("()=>{window.realDecode=decodeCropImage;window.cancelDecodeDone=false;decodeCropImage=async blob=>{await new Promise(r=>window.releaseDecode=r);const image=await realDecode(blob);window.cancelDecodeDone=true;return image}}");p.locator('#cardImageFile').set_input_files(fixture);p.wait_for_function('typeof releaseDecode===\"function\"');p.locator('#cancelEdit').click();p.evaluate('releaseDecode()');p.wait_for_function('cancelDecodeDone');p.evaluate('()=>{decodeCropImage=realDecode}');assert not p.locator('#imageCropDialog').is_visible();assert p.evaluate('JSON.stringify(state)')==prior
 print('PASS: save failure and late image decoding cannot overwrite data or resurrect a cancelled editor')
 # Upload on PC before login, then share through the existing private cloud payload.
 pc=page(1366,768);phone=page();data=uploaded['fields'][6]
 pc.evaluate("async data=>{const ref=await putCardImage(inlineImageBlob(data),imageOwner());state=initial();state.cards=[card(['共有画像','答え','','','','',ref])];state.session.queue=[{id:state.cards[0].id,retry:false}];persist();render()}",data);login(pc);cloud_photo=backend['user-a']['payload']['cards'][0];assert cloud_photo['fields'][6].startswith('data:image/');assert pc.evaluate("state.cards[0].fields[6].startsWith('card-image:')");assert pc.evaluate("async()=>!!await imageRecord(cloudLocalKey('user-a'),state.cards[0].fields[6])")
 login(phone);cid=phone.evaluate('state.cards[0].id');assert phone.evaluate('state.cards[0].fields[6]')==ref;phone.locator('.front').click();phone.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0");count=len(writes);full_reads=reads.count('revision,payload')
 for _ in range(3):sync(pc);sync(phone)
 assert reads.count('revision,payload')==full_reads,'Unchanged polling should request only revision metadata'
 assert len(writes)==count,'Image serialization must not cause repeated cloud writes'
 phone.locator('.grade .primary').click();sync(phone);pc.evaluate("state.cards[0].tags=['PCの分類'];persist();clearTimeout(cloudTimer)");sync(pc);sync(phone);assert backend['user-a']['payload']['cards'][0]['memory']['reviews']==1;assert backend['user-a']['payload']['cards'][0]['fields'][6]==data
 assert all('data:image' not in v for k,v in phone.evaluate('Object.entries(localStorage)') if ':before-' not in k),'Local metadata should not duplicate cloud image bytes'
 print('PASS: guest images transfer at login; another device restores pixels; image bytes sync privately; tag/review concurrency survives; unchanged sync does not rewrite')
 # Explicit sync can restore a missing local image even when the server revision is unchanged.
 phone.evaluate("async ref=>{clearImageURLs();const db=await imageDatabase();await new Promise((resolve,reject)=>{const tx=db.transaction('images','readwrite');tx.objectStore('images').delete(imageOwner()+'\\0'+ref);tx.oncomplete=resolve;tx.onerror=reject})}",ref)
 assert phone.evaluate('async ref=>!(await imageRecord(imageOwner(),ref))',ref)
 phone.locator('[data-tab=data]').click();phone.locator('#cloudSync').click();phone.wait_for_function('!cloudBusy');assert phone.evaluate('async ref=>!!(await imageRecord(imageOwner(),ref))',ref)
 print('PASS: unchanged polls fetch only revision; explicit sync repairs missing local images')
 # Same browser, different account: knowing the old reference cannot read its image record.
 phone.locator('[data-tab=data]').click();phone.once('dialog',lambda d:d.accept());phone.locator('#cloudLogout').click();phone.wait_for_function('!cloudRequestBusy');login(phone,'user-b');assert phone.evaluate("async ref=>!!await imageRecord(cloudLocalKey('user-a'),ref)",ref);assert phone.evaluate("async ref=>!(await imageRecord(cloudLocalKey('user-b'),ref))",ref);assert not phone.evaluate("state.cards.some(c=>c.fields[0]==='共有画像')")
 assert not errors,errors;print('PASS: uploaded images remain account-isolated in the same browser; no JS errors');b.close()
