from pathlib import Path
import os,shutil,tempfile
from playwright.sync_api import sync_playwright
import json
source=(Path(__file__).resolve().parents[1]/'index.html');errors=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':390,'height':744});p.route('https://folder.test/**',lambda r:r.fulfill(status=200,content_type='text/html',body=source.read_text()));p.on('pageerror',lambda e:errors.append(str(e)));p.on('dialog',lambda d:d.accept('世界史・歴史' if d.type=='prompt' else None));p.goto('https://folder.test/index.html')
 # Migrate a v2 collection with existing reviews/queue intact.
 original=p.evaluate("(()=>{const x=JSON.parse(JSON.stringify(state));x.version=2;delete x.folders;delete x.session.doneByFolder;x.cards.forEach(c=>delete c.folderId);x.cards[0].memory.reviews=4;x.cards[0].memory.successes=4;x.cards[0].memory.lastReviewed=today();x.cards[0].memory.stability=7;x.session.done=4;localStorage.setItem(KEY,JSON.stringify(x));return x})()");p.reload();assert p.evaluate('state.version')==3;assert p.evaluate("state.cards.every(c=>c.folderId==='english')");assert p.evaluate('state.cards[0].memory')==original['cards'][0]['memory'];assert p.evaluate('state.session.doneByFolder.english')==4
 english_first=p.evaluate('state.session.queue[0].id');p.locator('.front').click();p.locator('.grade .primary').click();english_memory=p.evaluate('state.cards.map(c=>c.memory)')
 # Actual mobile folder manager and creation.
 p.locator('#manageFolders').click();p.locator('#folderName').fill('世界史');p.locator('#folderForm button').click();history=p.evaluate('activeFolder');assert history!='english';assert p.locator('#csvFolder').input_value()==history
 p.locator('[data-tab=cards]').click();p.locator('#addCard').click();assert p.locator('#cardFolder').input_value()==history;assert '問題' in p.locator('label[for=f0]').inner_text();assert '答え' in p.locator('label[for=f1]').inner_text()
 values=['フランス革命が始まった年は？','1789年','人権宣言も1789年','関連：バスティーユ牢獄','人々が身分制の廃止を求めた。','自由と平等を求める運動。','🏰 民衆がバスティーユ牢獄の前に集まっている。']
 for i,v in enumerate(values):p.locator('#f'+str(i)).fill(v)
 p.locator('#cardForm [type=submit]').click();cid=p.evaluate('state.cards.at(-1).id');p.locator('[data-tab=study]').click();assert p.locator('.word').inner_text()==values[0];assert '残り1枚' in p.locator('#todayCount').inner_text();p.locator('.front').click();assert '重要な答え' in p.locator('.field-label').first.inner_text();p.screenshot(path=str(Path(tempfile.gettempdir())/'vocab-folder-mobile.png'));p.locator('.grade .negative').click();assert p.evaluate('studyItem().retry')
 # Switching preserves retry and English history.
 p.locator('#folderSelect').select_option('english');assert p.locator('.word').inner_text()!=values[0];p.locator('#folderSelect').select_option(history);assert p.evaluate('studyItem().retry');p.locator('.front').click();p.locator('.grade .primary').click();assert p.evaluate('studyItem()') is None;assert p.evaluate('state.cards.filter(c=>c.folderId===DEFAULT_FOLDER).map(c=>c.memory)')==english_memory;assert p.evaluate('state.session.doneByFolder[activeFolder]')==2
 # 7-column CSV with quoted commas goes to this folder.
 p.locator('[data-tab=data]').click();p.locator('#csv').fill('"submit, history",1789年,,関連事項,This is a short example.,説明,🏰 歴史の資料を読んでいる。');p.locator('#importCsv').click();assert p.evaluate('state.cards.at(-1).folderId')==history;assert p.evaluate('state.cards.at(-1).fields[0]')=='submit, history'
 # Move existing card without changing review history.
 p.locator('[data-tab=cards]').click();p.locator('#folderSelect').select_option('english');p.locator('[aria-label="submitを編集"]').click();before=p.evaluate("state.cards.find(c=>c.fields[0]==='submit')");p.locator('#cardFolder').select_option(history);p.locator('#cardForm [type=submit]').click();after=p.evaluate("state.cards.find(c=>c.fields[0]==='submit')");assert after['memory']==before['memory'] and after['due']==before['due'] and after['folderId']==history
 # Export/import retains folder assignments and all progress.
 p.locator('[data-tab=data]').click();snapshot=p.evaluate('JSON.stringify(state)');p.locator('#jsonText').fill(snapshot);p.locator('#importJson').click();assert p.evaluate('JSON.stringify(state)')==snapshot
 with p.expect_download() as info:p.locator('#exportJson').click()
 exported=json.load(open(info.value.path()));assert exported['version']==3 and len(exported['folders'])==2;assert next(c for c in exported['cards'] if c['id']==cid)['memory']['reviews']==2
 # Rename then remove only folder: cards and their memory survive.
 p.locator('#folderList .folder-row').filter(has=p.get_by_text('世界史',exact=True)).get_by_role('button',name='名前変更').click();assert '世界史・歴史' in p.locator('#folderSelect').inner_text();before=p.evaluate('state.cards');p.locator('#folderList .folder-row').filter(has=p.get_by_text('世界史・歴史',exact=True)).get_by_role('button',name='削除',exact=True).click();assert len(p.evaluate('state.cards'))==len(before);assert p.evaluate("state.cards.every(c=>c.folderId==='english')");assert p.evaluate('state.cards.map(c=>c.memory)')==[c['memory'] for c in before]
 # Malformed v3 imports must not flatten or overwrite valid folder data.
 prior=p.evaluate('JSON.stringify(state)');p.locator('#jsonText').fill('{"version":3,"cards":[],"session":{}}');p.locator('#importJson').click();assert p.evaluate('JSON.stringify(state)')==prior;assert '復元できません' in p.locator('#jsonStatus').inner_text()
 # All-folders mode and local remembered selection.
 p.locator('#folderSelect').select_option('*');p.reload();assert p.locator('#folderSelect').input_value()=='*';assert p.evaluate('state.folders.filter(f=>!f.deleted).length')==1
 assert not errors,errors;print('PASS: v2 migration; mobile folder create/rename/delete; generic fields; filtered study/retry; per-folder progress; CSV targeting; moving cards preserves history; JSON round trip; local selection restored.');b.close()
