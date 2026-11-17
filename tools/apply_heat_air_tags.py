"""Keep heat/air preset tags in the public catalog and single-file app."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'study/heat-air/complete';catalog=json.loads((folder/'cards.json').read_text())
PRESET='heat-air-subject-priority-v1'
def tags_for(c):
 assert c['subject'] in ('熱','空気')
 return ([c['subject']+'分野']+(['テスト用'] if c['rank']!='重要補完' else []))
rows=[]
for c in catalog['cards']:
 c['tags']=tags_for(c);rows.append([c['fields'][0],c['tags']])
sample=json.loads((ROOT/'study/heat-air/sample-01/cards.json').read_text());sample=sample['cards'] if isinstance(sample,dict) else sample
for row in sample:
 fields=row['fields'] if isinstance(row,dict) else row
 assert fields[0].startswith(('【空気】','【熱】'))
 rows.append([fields[0],['空気分野' if fields[0].startswith('【空気】') else '熱分野','テスト用']])
assert len(rows)==len({r[0] for r in rows})==303
assert sum('熱分野' in c['tags'] for c in catalog['cards'])==142
assert sum('空気分野' in c['tags'] for c in catalog['cards'])==156
assert sum('テスト用' in c['tags'] for c in catalog['cards'])==218
(folder/'cards.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
block='// BEGIN HEAT_AIR_TAG_PRESET\nconst HEAT_AIR_TAG_PRESET='+json.dumps(PRESET)+';\nconst HEAT_AIR_PRESET_TAGS=new Map('+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+');\n// END HEAT_AIR_TAG_PRESET'
p=ROOT/'index.html';source=p.read_text();source,n=re.subn(r'// BEGIN HEAT_AIR_TAG_PRESET\n.*?// END HEAT_AIR_TAG_PRESET',lambda _:block,source,flags=re.S);assert n==1;p.write_text(source)
print('Preset tags: heat 142, air 156, priority 218; plus 5 initial samples')
