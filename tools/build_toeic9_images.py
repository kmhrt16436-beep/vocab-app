"""Publish generated artwork unchanged, with four independent SVG view fragments."""
from pathlib import Path
import argparse,base64,json,struct,html

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--work',default='/workspace/toeic9-work');args=parser.parse_args()
folder=ROOT/'study/english/toeic9-part7';pack=json.loads((folder/'cards.json').read_text());work=Path(args.work)
catalog=[]
for index in range(1,38):
    meta=json.loads((work/f'sheet-{index:02}.json').read_text());source=Path(meta['path']);blob=source.read_bytes()
    assert blob.startswith(b'\x89PNG\r\n\x1a\n')
    width,height=struct.unpack('>II',blob[16:24]);half_w,half_h=width/2,height/2
    views=[]
    for tile in range(4):
        x=(tile%2)*half_w;y=(tile//2)*half_h
        views.append(f'<view id="card-{tile+1}" viewBox="{x:g} {y:g} {half_w:g} {half_h:g}"/>')
    # Only the viewing window changes; embedded source pixels are byte-for-byte intact.
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 {width} {height}"><title>Vocabulary illustration sheet {index}</title>'+''.join(views)+f'<image width="{width}" height="{height}" href="data:image/png;base64,'+base64.b64encode(blob).decode()+'"/></svg>\n'
    (folder/f'images/sheet-{index:02}.svg').write_text(svg)
    catalog.append({'sheet':index,'width':width,'height':height,'words':[r[0] for r in meta['words']]})
assert len(catalog)==37
(folder/'image-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
cards=''.join(f'<article><img loading="lazy" src="images/sheet-{c["sheet"]:02}.svg#card-{c["view"]}" alt="{html.escape(c["fields"][0],quote=True)}"><h2>{html.escape(c["fields"][0])}</h2><p>{html.escape(c["fields"][1])}</p><p lang="en">{html.escape(c["fields"][4])}</p><p>{html.escape(c["fields"][5])}</p></article>' for c in pack['cards'])
page='<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公式問題集9 · 145語のイラスト</title><style>body{margin:0;padding:20px;background:#f3f4ee;color:#203c36;font:16px/1.6 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}article{padding:16px;background:#fffefa;border-radius:14px;min-width:0}img{display:block;width:100%;aspect-ratio:1;object-fit:contain}h2{font-size:19px;overflow-wrap:anywhere}p{overflow-wrap:anywhere}a{color:#174d43}</style><h1>公式問題集9 · 画像付き145語</h1><p>利用者の重要な意味に合わせた自作のイラスト・例文です。公式問題の画像・本文は使用していません。</p><p><a href="../../../index.html?pack=toeic9-part7">アプリに「公式問題集9」タグで追加</a> · <a href="cards.csv">7列CSV</a></p><main>'+cards+'</main></html>'
(folder/'illustrations.html').write_text(page)
print('Published 37 original-artwork sheets as 145 independent image views; generated pixels unchanged.')
