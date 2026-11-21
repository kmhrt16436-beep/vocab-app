"""Embed reviewed Japanese TOEIC columns so the single-file app works offline."""
from pathlib import Path
import csv,json,re

ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'study/english/columns.json').read_text())
articles=catalog['articles']
assert catalog['version']==1 and len({a['id'] for a in articles})==len(articles)
assert any(not a['words'] for a in articles), 'New user words need a shared grammar column.'
with (ROOT/'TOEIC_images.csv').open(encoding='utf-8-sig',newline='') as f:
    words=[row[0] for row in csv.reader(f)]
assert [word for a in articles[:13] for word in a['words']]==words
for a in articles:
    assert a['title'] and a['intro'] and a['sections'] and a['takeaway']
    assert len(a['quiz']['choices'])==3 and 0<=a['quiz']['answer']<3
    assert all(len(row)==len(a['table']['headers']) for row in a['table']['rows'])
block='// BEGIN ENGLISH_COLUMNS\nconst ENGLISH_COLUMN_LIBRARY='+json.dumps(articles,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n// END ENGLISH_COLUMNS'
path=ROOT/'index.html';source=path.read_text()
source,count=re.subn(r'// BEGIN ENGLISH_COLUMNS\n.*?// END ENGLISH_COLUMNS',lambda _:block,source,flags=re.S)
assert count==1
path.write_text(source)
print(f'Embedded {len(articles)} English columns; no runtime library or network required.')
