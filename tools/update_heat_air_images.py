"""Assign original slide crops without changing questions, answers or review state."""
from pathlib import Path
import csv,json,shutil,html
R=Path(__file__).resolve().parents[1];D=R/'study/heat-air/complete';BASE='https://kmhrt16436-beep.github.io/vocab-app/study/heat-air/complete/'
old=json.loads((D/'cards.json').read_text());figs=json.loads((D/'slide-crops/catalog.json').read_text());byid={f['id']:f for f in figs}
assign={c:f for f in figs for c in f['cards']};assert len(assign)==298
updates=json.loads((D/'image-updates.json').read_text())['updates'];targets={c['fields'][0]:BASE+'slide-crops/'+assign[c['id']]['file'] for c in old['cards']}
sample_path=R/'study/heat-air/sample-01';sample=json.loads((sample_path/'cards.json').read_text());samples=sample['cards'] if isinstance(sample,dict) else sample
sample_ids=['a010-combustion-types','a191-efficiency','a213-pressureprofile','h062-blinds','h069-room-balance']
for row,key in zip(samples,sample_ids):
 fields=row['fields'] if isinstance(row,dict) else row;targets[fields[0]]=BASE+'slide-crops/'+byid[key]['file']
# Preserve all earlier migration paths, including the previous redrawn diagrams.
rows=[]
for front,previous,current in updates:
 target=targets[front];rows.append([front,previous,target])
 if current!=target:rows.append([front,current,target])
for c in old['cards']:
 before=c['fields'][:];target=targets[before[0]]
 if before[6]!=target:rows.append([before[0],before[6],target])
 c['fields'][6]=target;c['illustration']=assign[c['id']]['id'];assert c['fields'][:6]==before[:6]
old['illustrationRevision']=3;old['illustrations']=figs
(D/'cards.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
for key,count in old['sets'].items():
 cards=[c for c in old['cards'] if key=='all' or key==c['chapter'] or key=='heat' and c['subject']=='熱' or key=='air' and c['subject']=='空気' or key=='priority' and c['rank']!='重要補完'];assert len(cards)==count
 with (D/(key+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f,lineterminator='\n',quoting=csv.QUOTE_ALL).writerows(c['fields'] for c in cards)
compat={'h01-wall':'h004-wall','h02-radiation':'h005-surface','h03-room':'h015-balance','h04-multizone':'h035-airflow','h05-sat':'h050-sat','h06-glass':'h057-window','h07-shading':'h062-blinds','h08-eaves':'h026-eaves','h09-lowe':'h064-lowe','h10-neutral':'h069-room-balance','h11-capacity':'h081-heavy','h12-conduction':'h090-controlvolume','h13-response':'h104-response','h14-human':'h112-environment','h15-pmv':'h125-ppd','h16-globe':'h130-globe','h17-psychrometric':'h144-chart','h18-coil':'h135-coolingcoil','h19-mixing':'h135-mixing','h20-degreedays':'h150-degreedays','h21-solar':'h045-solar','h22-airprocess':'h137-humidification','h23-moisture':'h141-moistair','h24-wbgt':'h129-wbgt','h25-shf':'h138-shf','h26-solarload':'h069-windowbalance','a01-combustion':'a010-combustion-types','a02-oxygen':'a028-oxygenbalance','a03-hood':'a048-capturetest','a04-contaminant':'a073-dustbalance','a05-recirculation':'a088-recirculation','a06-filter':'a079-filtration','a07-isolation':'a063-smoking','a08-tracer':'a119-decaysetup','a09-decay':'a123-semilog','a10-ventpatterns':'a198-mixing','a11-agecurves':'a170-stepdown','a12-airage':'a158-airage','a13-pressure':'a213-pressureprofile','a14-pressuremeasure':'a215-dynamic','a15-operating':'a230-operatingpoint','a16-fans':'a230-seriesparallel','a17-duct':'a231-friction','a18-jet':'a276-jettypes','a19-jetdecay':'a278-region1','a20-anemo':'a288-anemocone','a21-outlets':'a276-jettypes','a22-draft':'a263-colddraft','a23-cfd':'a298-cfdmesh','a24-removal':'a145-knownsource','a25-fanblades':'a227-blades','a26-ductends':'a237-bellmouth','a27-draftindex':'a257-dr'}
for previous,key in compat.items():shutil.copyfile(D/'slide-crops'/byid[key]['file'],D/'diagrams-v2'/(previous+'.png'))
(D/'diagrams-v2/catalog.json').write_text(json.dumps([{**byid[key],'id':previous,'file':previous+'.png','originalCrop':key,'cards':[]} for previous,key in compat.items()],ensure_ascii=False,indent=2)+'\n')
(D/'diagrams-v2/layout-report.json').unlink(missing_ok=True)
aliases={1:'a01-combustion',2:'a10-ventpatterns',3:'a13-pressure',4:'h07-shading',5:'h26-solarload',6:'h13-response',7:'a09-decay',8:'h10-neutral',9:'a19-jetdecay',10:'h01-wall',11:'a05-recirculation',12:'h14-human',13:'h17-psychrometric',14:'h20-degreedays'}
for n,key in aliases.items():shutil.copyfile(D/'slide-crops'/byid[compat[key]]['file'],D/('diagrams/' if n>5 else '')/f'heat-air-{n:03}.png')
for n,(row,key) in enumerate(zip(samples,sample_ids),1):
 fields=row['fields'] if isinstance(row,dict) else row;target=targets[fields[0]]
 if fields[6]!=target:rows.append([fields[0],fields[6],target])
 fields[6]=target;shutil.copyfile(D/'slide-crops'/byid[key]['file'],sample_path/f'heat-air-{n:03}.png')
(sample_path/'cards.json').write_text(json.dumps(sample,ensure_ascii=False,indent=2)+'\n')
for file in sample_path.glob('*.csv'):
 with file.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f,lineterminator='\n',quoting=csv.QUOTE_ALL).writerows(x['fields'] if isinstance(x,dict) else x for x in samples)
rows=list({(r[0],r[1]):r for r in rows}.values());assert all('/slide-crops/' in r[2] for r in rows)
(D/'image-updates.json').write_text(json.dumps({'version':3,'updates':rows},ensure_ascii=False,indent=2)+'\n')
# Searchable source gallery. Captions stay outside the original images.
parts=['''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>熱・空気 授業スライドの図｜Flash Cards</title><style>*{box-sizing:border-box}body{margin:0;background:#f3f4ee;color:#203c36;font:16px/1.7 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:24px 16px 64px}a{color:#174d43}h1{font-size:28px}h2{font-size:20px;margin:0}#gallery{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{padding:16px;border:1px solid #d5ded6;border-radius:14px;background:#fff}img{width:100%;height:360px;object-fit:contain}small{color:#63736d;overflow-wrap:anywhere}input{font:inherit;width:100%;padding:14px;margin:18px 0;border-radius:8px;border:1px solid #cad6ce}section{margin:24px 0}[hidden]{display:none!important}@media(max-width:700px){#gallery{grid-template-columns:1fr}img{height:auto;max-height:520px}}</style><main><h1>熱・空気：授業スライドの図・写真・式</h1><p><a href="./">298枚のカード一覧</a> ／ <a href="../../../index.html">アプリを開く</a></p><p>「熱1-7」「空気8-13」の原図を、その用語に必要な範囲で切り出しました。文字・矢印・記号・写真は原資料のままです。数式が中心のカードは、対応する原資料の式を使っています。画像をタップすると拡大できます。</p><p>登録済みカードはアプリをオンラインで再読み込みすると、対象の画像だけ更新されます。問題・答え・フォルダ・学習進捗を保持します。CSVの再追加は不要です。</p><input id="search" type="search" aria-label="図を検索" placeholder="用語・カード番号・資料名で検索"><p id="count" role="status"></p><div id="gallery">''']
for f in figs:
 ids=f['cards'];source=f'{f["sourceFile"]} PDF p.{f["page"]}';q=' '.join([f['title'],source,*ids]);esc=lambda s:html.escape(s,quote=True)
 parts.append(f'<article data-search="{esc(q)}"><h2>{esc(f["title"])}</h2><p><small>{esc(source)}（PDF先頭からの通し番号）</small></p><a href="slide-crops/{f["file"]}" target="_blank" rel="noopener" aria-label="{esc(f["title"])}を拡大"><img loading="lazy" width="{f["width"]}" height="{f["height"]}" src="slide-crops/{f["file"]}" alt="{esc(f["title"])}"></a><p><small>対応カード：{esc(", ".join(ids) or "先行5枚：燃焼器具の分類")}</small></p>')
 for credit in f['credits']:parts.append(f'<p><small>原資料の出典表示：{esc(credit)}</small></p>')
 parts.append('</article>')
parts.append('''</div><section id="references"><h2>出典</h2><p>ユーザー提供の授業資料「熱1-7.pdf」「空気8-13.pdf」。各画像に資料名とPDFページを併記しています。原図のラベルや注釈は変更していません。授業資料全体や過去問写真、氏名・学籍番号は掲載していません。</p><p>初期版の解釈確認に使用した公開資料は、<a href="../sample-01/index.html#references">先行版の参考資料</a>に記載しています。今回の画像は授業資料からの直接切り出しです。</p></section></main><script>const search=document.getElementById('search'),items=[...document.querySelectorAll('article')];function filter(){const q=search.value.trim().toLowerCase();items.forEach(x=>x.hidden=!x.dataset.search.toLowerCase().includes(q));document.getElementById('count').textContent=items.filter(x=>!x.hidden).length+'図を表示'}search.addEventListener('input',filter);filter()</script></html>''')
(D/'diagrams.html').write_text(''.join(parts))
print(f'UPDATED 298 cards; {len(figs)} original crops; {len(rows)} migration paths')
