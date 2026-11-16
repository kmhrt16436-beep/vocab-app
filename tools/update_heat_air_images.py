from pathlib import Path
import csv,json,shutil,html
R=Path(__file__).resolve().parents[1];D=R/'study/heat-air/complete';BASE='https://kmhrt16436-beep.github.io/vocab-app/study/heat-air/complete/'
old=json.loads((D/'cards.json').read_text())
figs=json.loads((D/'diagrams-v2/catalog.json').read_text());byid={f['id']:f for f in figs};assign={}
def group(ch,first,last,fig):
 assert fig in byid,fig
 for n in range(first,last+1):
  k=f'{ch}-{n:02}';assert k not in assign,k;assign[k]=fig
group('H1',1,8,'h01-wall');group('H1',9,10,'h02-radiation');group('H1',11,19,'h03-room');group('H1',20,20,'h01-wall');group('H1',21,21,'h03-room');group('H1',22,28,'h04-multizone')
group('H2',1,3,'h21-solar');group('H2',4,9,'h05-sat');group('H2',10,12,'h06-glass');group('H2',13,13,'h07-shading');group('H2',14,16,'h08-eaves');group('H2',17,18,'h09-lowe');group('H2',19,19,'h06-glass');group('H2',20,23,'h26-solarload');group('H2',24,34,'h10-neutral')
group('H3',1,5,'h11-capacity');group('H3',6,11,'h12-conduction');group('H3',12,19,'h13-response')
group('H4',1,7,'h14-human');group('H4',8,10,'h02-radiation');group('H4',11,12,'h14-human');group('H4',13,17,'h15-pmv');group('H4',18,20,'h14-human');group('H4',21,23,'h24-wbgt');group('H4',24,24,'h16-globe')
group('H5',1,5,'h23-moisture');group('H5',6,9,'h17-psychrometric');group('H5',10,13,'h19-mixing');group('H5',14,15,'h17-psychrometric');group('H5',16,19,'h18-coil');group('H5',20,21,'h22-airprocess');group('H5',22,25,'h25-shf')
group('H6',1,10,'h20-degreedays');group('H6',11,11,'h05-sat');group('H6',12,12,'h20-degreedays')
group('A1',1,5,'a01-combustion');group('A1',6,10,'a02-oxygen');group('A1',11,12,'a03-hood');group('A1',13,15,'a02-oxygen');group('A1',16,16,'a03-hood');group('A1',17,18,'a02-oxygen')
group('A2',1,8,'a04-contaminant');group('A2',9,11,'a06-filter');group('A2',12,21,'a05-recirculation');group('A2',22,25,'a06-filter');group('A2',26,27,'a07-isolation')
group('A3',1,5,'a04-contaminant');group('A3',6,14,'a09-decay');group('A3',15,16,'a04-contaminant');group('A3',17,19,'a08-tracer');group('A3',20,21,'a09-decay');group('A3',22,22,'a04-contaminant');group('A3',23,23,'a09-decay')
group('A4',1,1,'a10-ventpatterns');group('A4',2,7,'a12-airage');group('A4',8,13,'a10-ventpatterns');group('A4',14,19,'a11-agecurves');group('A4',20,23,'a24-removal');group('A4',24,24,'a10-ventpatterns');group('A4',25,25,'a24-removal')
group('A5',1,4,'a14-pressuremeasure');group('A5',5,9,'a13-pressure');group('A5',10,11,'a26-ductends');group('A5',12,13,'a13-pressure');group('A5',14,16,'a14-pressuremeasure');group('A5',17,19,'a15-operating');group('A5',20,22,'a16-fans');group('A5',23,27,'a17-duct');group('A5',28,28,'a15-operating');group('A5',29,29,'a25-fanblades');group('A5',30,32,'a17-duct')
group('A6',1,6,'a27-draftindex');group('A6',7,8,'a22-draft');group('A6',9,9,'a21-outlets');group('A6',10,13,'a19-jetdecay');group('A6',14,19,'a18-jet');group('A6',20,21,'a20-anemo');group('A6',22,26,'a21-outlets');group('A6',27,29,'a22-draft');group('A6',30,31,'a23-cfd')
assert len(assign)==len(old['cards'])==298
updates=json.loads((D/'image-updates.json').read_text())['updates'] if (D/'image-updates.json').exists() else []
for c in old['cards']:
 previous=c['fields'][6];fig=byid[assign[c['id']]];c['fields'][6]=BASE+'diagrams-v2/'+fig['file'];
 if '/diagrams-v2/' not in previous:updates.append([c['fields'][0],previous,c['fields'][6]])
 c['illustration']=fig['id']
old['illustrationRevision']=2;old['illustrations']=figs
(D/'cards.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
for key,count in old['sets'].items():
 cards=[c for c in old['cards'] if key=='all' or key==c['chapter'] or key=='heat' and c['subject']=='熱' or key=='air' and c['subject']=='空気' or key=='priority' and c['rank']!='重要補完']
 assert len(cards)==count,(key,len(cards),count)
 with (D/(key+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f,lineterminator='\n',quoting=csv.QUOTE_ALL).writerows(c['fields'] for c in cards)
# Keep old URLs useful even for clients that have not loaded the app's image-only update.
aliases={1:'a01-combustion',2:'a10-ventpatterns',3:'a13-pressure',4:'h07-shading',5:'h26-solarload',6:'h13-response',7:'a09-decay',8:'h10-neutral',9:'a19-jetdecay',10:'h01-wall',11:'a05-recirculation',12:'h14-human',13:'h17-psychrometric',14:'h20-degreedays'}
for n,key in aliases.items():shutil.copyfile(D/'diagrams-v2'/byid[key]['file'],D/('diagrams/' if n>5 else '')/f'heat-air-{n:03}.png')
sample=json.loads((R/'study/heat-air/sample-01/cards.json').read_text())
if isinstance(sample,dict):sample=sample['cards']
for n,c in enumerate(sample,1):
 fields=c['fields'] if isinstance(c,dict) else c
 target=BASE+'diagrams-v2/'+byid[aliases[n]]['file'];updates.append([fields[0],fields[6],target]);shutil.copyfile(D/'diagrams-v2'/byid[aliases[n]]['file'],R/'study/heat-air/sample-01'/f'heat-air-{n:03}.png')
updates=list({(row[0],row[1]):row for row in updates}.values())
(D/'image-updates.json').write_text(json.dumps({'version':2,'updates':updates},ensure_ascii=False,indent=2)+'\n')
gallery='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>熱・空気 図解一覧｜Flash Cards</title><style>*{box-sizing:border-box}body{margin:0;background:#f3f4ee;color:#203c36;font:16px/1.7 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:24px 16px 64px}a{color:#174d43}h1{font-size:28px}h2{font-size:20px;margin:0}#gallery{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{padding:16px;border:1px solid #d5ded6;border-radius:14px;background:#fffefa}img{width:100%;height:auto}small{color:#63736d}input{font:inherit;width:100%;padding:14px;margin:18px 0;border-radius:8px;border:1px solid #cad6ce}section{margin:24px 0}button{font:inherit;min-height:48px}@media(max-width:700px){#gallery{grid-template-columns:1fr}}</style><main><h1>熱・空気：授業図に基づく図解53種類</h1><p><a href="./">298枚のカード一覧</a> ／ <a href="../../../index.html">アプリを開く</a></p><p>壁・窓・コイル・燃焼器具・室内気流・吹出し口の構造と、授業の式に対応する曲線を再作図しました。画像をタップすると拡大できます。記号・基準値は授業でのモデルに従います。</p><p>すでにカードを登録している場合は、アプリをオンラインで再読み込みすると、対象の旧画像URLだけが自動で更新されます。問題・答え・フォルダ・学習進捗は保持します。独自の画像に変更したカードは対象外です。CSVを重ねて追加する必要はありません。</p><input id="search" type="search" aria-label="図を検索" placeholder="熱・空気・キーワードで検索"><p id="count" role="status"></p><div id="gallery">'''
for fig in figs:
 ids=[c['id'] for c in old['cards'] if c['illustration']==fig['id']]
 gallery+=f'<article data-search="{html.escape(fig["id"]+fig["title"]+fig["source"],quote=True)}"><h2>{html.escape(fig["title"])}</h2><p><small>{html.escape(fig["source"])}</small></p><a href="diagrams-v2/{fig["file"]}" target="_blank" rel="noopener"><img loading="lazy" width="1260" height="1260" src="diagrams-v2/{fig["file"]}" alt="{html.escape(fig["title"],quote=True)}"></a><p><small>対応カード：{", ".join(ids)}</small></p></article>'
gallery+='''</div><section id="references"><h2>図の根拠と公開参考資料</h2><p>主な根拠は、ユーザー提供の「熱1-7」「空気8-13」。各図にPDF先頭からの通しページ番号を表示しました。原本のスクリーンショットは公開せず、構造・関係を描き直しています。</p><ul><li><a href="https://www.tac-school.co.jp/file/tac/kouza_kenchiku/pdf/kansetu_03.pdf">TAC「伝熱・結露」公開教材</a>：壁体の伝熱、熱抵抗・空気層・放射の関係の補助確認（PDF p.2–4）。</li><li><a href="https://news-sv.aij.or.jp/kankyo/s7/Handout/2020/20200729_Handout_Yanagi_1.pdf">日本建築学会公開講習資料（柳宇）</a>：ピストンフロー・完全混合・置換換気の流れの描き分け（PDF p.7）。</li><li><a href="https://www.mitsubishielectric.co.jp/ldm/ventilationfan/knowledge/detail_02.html">三菱電機「換気扇・送風機の基礎」</a>：全圧・静圧・動圧の説明と測定模式図の補助確認。</li><li><a href="https://www.ykkap.co.jp/business/law/tec/solar-heat-gain/">YKK AP「日射熱取得性」</a>：窓の日射熱取得率と遮蔽物の効果の補助確認。</li></ul><p>外部資料の図の転載ではなく、授業内容に合わせた独自の作図です。空気線図は標準大気圧での計算例、噴流や圧力曲線は説明用の代表モデルです。</p></section></main><script>const search=document.getElementById('search'),items=[...document.querySelectorAll('article')];function filter(){const q=search.value.trim().toLowerCase();items.forEach(x=>x.hidden=!x.dataset.search.toLowerCase().includes(q));document.getElementById('count').textContent=items.filter(x=>!x.hidden).length+'図を表示'}search.addEventListener('input',filter);filter()</script></html>'''
(D/'diagrams.html').write_text(gallery)
print('UPDATED',len(old['cards']),'cards;',len(figs),'figures;',len(updates),'migration entries')
