"""Render focused, unaltered rectangles from the user-provided lecture PDFs."""
from pathlib import Path
import argparse,hashlib,json
import fitz

ROOT=Path(__file__).resolve().parents[1]
def extract(heat_pdf,air_pdf):
 out=ROOT/'study/heat-air/complete/slide-crops';out.mkdir(exist_ok=True)
 specs=json.loads((ROOT/'tools/slide_crops.json').read_text())
 docs={'heat':fitz.open(heat_pdf),'air':fitz.open(air_pdf)}
 catalog=[];issues=[];assigned=set()
 for spec in specs:
  assert spec['source'] in docs and len(spec['rect'])==4
  page=docs[spec['source']][spec['page']-1];x0,y0,x1,y1=spec['rect'];assert 0<=x0<x1<=1 and 0<=y0<y1<=1
  assert not assigned.intersection(spec['cards']),spec['id'];assigned.update(spec['cards'])
  clip=fitz.Rect(x0*page.rect.width,y0*page.rect.height,x1*page.rect.width,y1*page.rect.height)
  # Render the original PDF content directly. No image generation, overlays or compositing.
  scale=min(4.0,1900/max(clip.width,clip.height))
  pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=clip,alpha=False)
  file=out/(spec['id']+'.png');pix.save(file)
  edges=[]
  for block in page.get_text('rawdict')['blocks']:
   for line in block.get('lines',[]):
    for span in line['spans']:
     for ch in span['chars']:
      if not ch['c'].strip():continue
      box=fitz.Rect(ch['bbox']);hit=box&clip
      if hit.is_empty:continue
      if hit.get_area()<box.get_area()*.80:edges.append(ch['c'])
  if edges:issues.append({'id':spec['id'],'edge_characters':''.join(edges)[:120]})
  credits=[]
  for b in page.get_text('blocks'):
   if b[1]>page.rect.height*.78 and any(t in b[4] for t in ['出典','※','より','著：']):
    credit=' '.join(b[4].split())
    if len(credit)<600:credits.append(credit)
  catalog.append({**spec,'file':file.name,'mode':'original-pdf-crop','sourceFile':'熱1-7.pdf' if spec['source']=='heat' else '空気8-13.pdf','width':pix.width,'height':pix.height,'scale':scale,'rectPoints':list(clip),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'credits':credits})
 assert len(assigned)==298
 (out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
 print(f'Extracted {len(catalog)} focused crops for {len(assigned)} cards; {sum((out/c["file"]).stat().st_size for c in catalog)/1024/1024:.1f} MiB')
 print('Boundary candidates for visual inspection:',len(issues))
 (out/'boundary-review.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2)+'\n')
 return catalog,issues

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--heat-pdf',type=Path,required=True);parser.add_argument('--air-pdf',type=Path,required=True)
 args=parser.parse_args();extract(args.heat_pdf,args.air_pdf)
