"""Enlargement stays inside the app and outside taps return to the same card."""
from pathlib import Path
import os,shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1];BASE='https://image-viewer.test/'
source=(ROOT/'index.html').read_text();errors=[]
def picture(route):
    portrait='portrait' in route.request.url
    w,h=(600,1200) if portrait else (1200,600)
    route.fulfill(content_type='image/svg+xml',body=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#a8c9a1"/></svg>')

with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    for touch,viewport in [(True,{'width':360,'height':640}),(True,{'width':390,'height':744}),(True,{'width':844,'height':390}),(False,{'width':1366,'height':768})]:
        ctx=b.new_context(viewport=viewport,has_touch=touch)
        ctx.route(BASE+'**',lambda r:r.fulfill(content_type='text/html',body=source));ctx.route('https://images.test/**',picture)
        p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE)
        for shape in ['landscape','portrait']:
            p.evaluate("""url=>{state=initial();const c=card(['sample','名）例','','','This is an example.','これは例です。',url]);c.id='sample';state.cards=[c];state.session.queue=[{id:c.id,retry:false}];activeFolder='english';activeTab='study';revealed=false;render()}""",'https://images.test/'+shape+'.svg')
            p.locator('.front').click();p.wait_for_function("document.querySelector('.illustration')?.naturalWidth>0")
            before=p.evaluate('syncString(state)')
            p.locator('.illustration').tap() if touch else p.locator('.illustration').click()
            p.wait_for_function("document.getElementById('imageViewerPicture').naturalWidth>0")
            assert p.locator('#imageViewer').evaluate('(e)=>e.open') and len(ctx.pages)==1
            box=p.locator('#imageViewerPicture').bounding_box();close=p.locator('#closeImageViewer').bounding_box()
            assert 0<=box['x'] and box['x']+box['width']<=viewport['width']+1,box
            assert box['y']>=close['y']+close['height']-1 and box['y']+box['height']<=viewport['height']-20,box
            assert abs(box['width']/box['height']-(.5 if shape=='portrait' else 2))<.01,box
            p.locator('#imageViewerPicture').tap() if touch else p.locator('#imageViewerPicture').click()
            assert p.locator('#imageViewer').evaluate('(e)=>e.open'),'Tapping the image must not dismiss it'
            p.touchscreen.tap(4,viewport['height']/2) if touch else p.mouse.click(4,viewport['height']/2)
            assert not p.locator('#imageViewer').evaluate('(e)=>e.open')
            assert p.locator('.back-word').inner_text()=='sample' and p.locator('.grade').is_visible() and p.evaluate('revealed')
            assert p.evaluate('syncString(state)')==before and p.locator('#imageViewerPicture').get_attribute('src') is None
            assert p.locator('.illustration').evaluate('(e)=>document.activeElement===e')
            for key in ['Enter',' ']:
                p.locator('.illustration').press(key);assert p.locator('#imageViewer').evaluate('(e)=>e.open')
                p.locator('#closeImageViewer').click();assert not p.locator('#imageViewer').evaluate('(e)=>e.open')
            p.locator('.illustration').click();p.keyboard.press('Escape');assert not p.locator('#imageViewer').evaluate('(e)=>e.open')
            assert p.evaluate('syncString(state)')==before
        # Stored photos use the existing private blob URL; no new tab or public upload.
        p.evaluate("""async()=>{const canvas=document.createElement('canvas');canvas.width=800;canvas.height=600;const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));const c=state.cards[0];c.fields[6]=await putCardImage(blob,imageOwner());persist();renderStudy()}""")
        p.wait_for_function("document.querySelector('.illustration')?.src.startsWith('blob:')&&document.querySelector('.illustration').naturalWidth>0")
        before=p.evaluate('syncString(state)');p.locator('.illustration').click();p.wait_for_function("document.getElementById('imageViewerPicture').naturalWidth===800")
        assert p.locator('#imageViewerPicture').get_attribute('src').startswith('blob:') and len(ctx.pages)==1
        # Unchanged polling keeps the enlargement open; closing restores the replaced thumbnail.
        p.evaluate('applySyncedState(normalizedSync(state))');assert p.locator('#imageViewer').evaluate('(e)=>e.open')
        p.locator('#closeImageViewer').click();assert p.locator('.illustration').evaluate('(e)=>document.activeElement===e')
        assert p.evaluate('syncString(state)')==before
        # Changing the current card/account closes and clears the private preview.
        p.locator('.illustration').click();p.evaluate("activeStorageKey=KEY+':account:other-user';renderStudy()")
        assert not p.locator('#imageViewer').evaluate('(e)=>e.open') and p.locator('#imageViewerPicture').get_attribute('src') is None
        ctx.close()
    assert not errors,errors;b.close()
print('PASS: touch/desktop, portrait/landscape, outside tap, image tap, close button, Enter/Space/Escape, URL/private photos, sync and account switch; same card/history preserved and no new windows')
