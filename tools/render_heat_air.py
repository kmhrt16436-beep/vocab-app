from pathlib import Path
import math,json,csv,shutil,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,Polygon,Circle,FancyArrowPatch,Arc,PathPatch
from matplotlib.path import Path as MPath
from matplotlib.text import Text

ROOT=Path(__file__).resolve().parents[1]/'study/heat-air/complete'
OUT=ROOT/'diagrams-v2';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family':['Noto Sans CJK JP','DejaVu Sans','STIXGeneral'],'axes.unicode_minus':False,'mathtext.fontset':'dejavusans','font.size':13})
INK='#233f3a';BLUE='#237daf';RED='#b72e32';ORANGE='#ce782d';GREEN='#28775c';GREY='#7b8a86';BG='#fffefa';PALE='#edf3f1';GOLD='#e7b64b'
catalog=[];reports=[]
def text(a,x,y,s,size=16,c=INK,ha='left',**kw):return a.text(x,y,s,fontsize=size,color=c,ha=ha,va='center',**kw)
def line(a,x,y,c=GREY,lw=2,**kw):return a.plot(x,y,color=c,lw=lw,**kw)[0]
def arrow(a,x,y,X,Y,c=BLUE,lw=3,**kw):
 p=FancyArrowPatch((x,y),(X,Y),arrowstyle='-|>',mutation_scale=17,lw=lw,color=c,**kw);a.add_patch(p);return p
def box(a,x,y,w,h,fc=PALE,ec=GREY,hatch=None,lw=2):
 p=Rectangle((x,y),w,h,fc=fc,ec=ec,lw=lw,hatch=hatch);a.add_patch(p);return p
def circle(a,x,y,r,fc=PALE,ec=INK,lw=2):a.add_patch(Circle((x,y),r,fc=fc,ec=ec,lw=lw))
def poly(a,xy,fc=PALE,ec=GREY,lw=2):a.add_patch(Polygon(xy,fc=fc,ec=ec,lw=lw))
def start(key,title,source,sub=''):
 f=plt.figure(figsize=(9,9),dpi=140,facecolor=BG);a=f.add_axes([0,0,1,1]);a.set(xlim=(0,1),ylim=(0,1));a.axis('off')
 text(a,.055,.95,title,24,ha='left',weight='bold')
 if sub:text(a,.055,.892,sub,14,c=GREY)
 text(a,.055,.025,source+' ｜ 授業のモデルをもとに再作図',10,c=GREY)
 f._key=key;f._title=title;f._source=source;return f,a
def note(a,s,y=.083,size=16):text(a,.5,y,s,size,ha='center')
def chart(f,rect,xlab,ylab,xlim,ylim):
 p=f.add_axes(rect);p.set(xlim=xlim,ylim=ylim);p.spines[['top','right']].set_visible(False)
 p.set_xlabel(xlab,labelpad=9);p.set_ylabel(ylab,labelpad=10);p.tick_params(labelsize=11);return p
def human(a,x,y,s=1):
 circle(a,x,y+.17*s,.025*s,fc='#efd1ae');box(a,x-.035*s,y+.065*s,.07*s,.075*s,fc='#8fb8ac',ec=GREEN)
 for xx in [-1,1]:line(a,[x+xx*.02*s,x+xx*.035*s],[y+.065*s,y],INK,3);line(a,[x+xx*.035*s,x+xx*.07*s],[y+.125*s,y+.08*s],INK,3)
def room(a,x=.18,y=.27,w=.65,h=.48):box(a,x,y,w,h,fc='#f2f6f2',ec=INK,lw=3)
def flame(a,x,y,s=.06):poly(a,[(x-s/2,y),(x,y+s),(x+s/2,y)],fc=ORANGE,ec=ORANGE)
def sun(a,x,y,r=.035):
 circle(a,x,y,r,fc='#fce7a8',ec=ORANGE)
 for t in np.linspace(0,2*np.pi,8,endpoint=False):line(a,[x+(r+.01)*np.cos(t),x+(r+.025)*np.cos(t)],[y+(r+.01)*np.sin(t),y+(r+.025)*np.sin(t)],ORANGE,1.5)
def save(f):
 f.canvas.draw();ren=f.canvas.get_renderer();issues=[]
 # All visible prose, mathematical labels, tick labels and axis labels are checked.
 ts=[t for t in f.findobj(Text) if t.get_visible() and t.get_text() and t.get_window_extent(ren).width>0]
 bs=[(t,t.get_window_extent(ren).padded(2)) for t in ts]
 for i,(t,b) in enumerate(bs):
  if b.x0<3 or b.y0<3 or b.x1>f.bbox.width-3 or b.y1>f.bbox.height-3:issues.append(('edge',t.get_text()))
  for u,c in bs[i+1:]:
   if b.overlaps(c):issues.append(('text/text',t.get_text(),u.get_text()))
  for a in f.axes:
   for p in [*a.patches,*a.lines]:
    if not isinstance(p,FancyArrowPatch) and p not in a.lines:continue
    if p.get_clip_on() and not b.overlaps(a.bbox):continue
    path=p.get_path().transformed(p.get_transform());prev=None
    for v,code in path.iter_segments(curves=False):
     q=v[-2:]
     if code==MPath.MOVETO:prev=q;continue
     if code==MPath.CLOSEPOLY:prev=None;continue
     if prev is not None and MPath([prev,q],[MPath.MOVETO,MPath.LINETO]).intersects_bbox(b,filled=False):issues.append(('text/arrow-or-line',t.get_text()));break
     prev=q
 reports.append({'id':f._key,'issues':issues});catalog.append({'id':f._key,'title':f._title,'source':f._source,'file':f._key+'.png'})
 f.savefig(OUT/(f._key+'.png'),dpi=140);plt.close(f)
 print(f._key,issues,flush=True)

# H1: physical wall section, then corresponding resistance network.
f,a=start('h01-wall','壁の断面と熱抵抗','熱 PDF p.4–20','温度差で生じる貫流熱：壁内部の伝導と、両表面の熱伝達')
for x,w,fc,label in [(.30,.12,'#c3c6c4','躯体'),(.42,.18,'#f3d585','断熱材'),(.60,.07,'#e1ded2','仕上げ')]:
 box(a,x,.44,w,.34,fc=fc,hatch='..' if label=='断熱材' else None);text(a,x+w/2,.815,label,15,ha='center')
text(a,.15,.72,'室外側',18,ha='center');text(a,.84,.72,'室内側',18,ha='center')
for y in [.52,.62]:arrow(a,.12,y,.88,y,ORANGE)
text(a,.15,.405,'表面熱伝達',13,ha='center');text(a,.485,.405,'熱伝導',16,ha='center');text(a,.84,.405,'対流＋放射',13,ha='center')
xs=[.12,.29,.43,.62,.78,.91];y=.29
for i in range(5):
 xx=np.linspace(xs[i],xs[i+1],13);yy=np.full(13,y);yy[2:-2]+=np.tile([.013,-.013],5)[:9];line(a,xx,yy,INK,2)
for x,s in zip([.20,.36,.525,.70,.85],[r'$1/\alpha_o$',r'$\delta_1/\lambda_1$',r'$\delta_2/\lambda_2$',r'$\delta_3/\lambda_3$',r'$1/\alpha_i$']):text(a,x,.225,s,17,ha='center')
note(a,r'$U=1/R_{total}$　　$Q=UA(\theta_o-\theta_R)$',.13,22);note(a,'直列の熱抵抗は加算。断熱材は温度降下が大きい。',.065,15);save(f)

f,a=start('h02-radiation','気温と平均放射温度 MRT','熱 PDF p.4・108–112・130','人体は空気とも、周囲の壁・窓とも熱交換する')
room(a,.16,.30,.68,.48);box(a,.17,.42,.06,.25,fc='#b7deec',ec=BLUE);human(a,.51,.34,1.35)
text(a,.30,.70,'冷たい窓',16,c=BLUE,ha='center');text(a,.73,.70,'周囲壁面',16,ha='center')
arrow(a,.46,.59,.25,.59,ORANGE);arrow(a,.58,.59,.79,.59,ORANGE);arrow(a,.51,.64,.51,.74,BLUE)
text(a,.51,.815,'空気との対流',17,c=BLUE,ha='center');text(a,.29,.515,'放射',16,c=ORANGE,ha='center');text(a,.72,.515,'放射',16,c=ORANGE,ha='center')
note(a,r'$MRT\simeq\sum_i F_i\theta_i$　　$\sum_i F_i=1$',.21,22)
note(a,r'$\theta_e=\frac{\alpha_c\theta_a+\alpha_r MRT}{\alpha_c+\alpha_r}$',.125,23);note(a,'大きく見える面・温度差の大きい面の影響に注意。',.06,15);save(f)

f,a=start('h03-room','単室の熱収支と自然室温','熱 PDF p.21–26・69','外皮・換気・内部発熱を、同じ室の収支として捉える')
room(a,.42,.28,.48,.48);box(a,.41,.46,.025,.22,fc='#b7deec',ec=BLUE)
for y,label,c in [(.66,'外皮の貫流熱',ORANGE),(.47,'換気が運ぶ熱',BLUE)]:text(a,.065,y+.055,label,16,c=c);arrow(a,.07,y,.60,y,c)
human(a,.65,.32,.8);box(a,.77,.33,.07,.08,fc='#c6d2d1');flame(a,.8,.43,.04)
text(a,.68,.585,'室温 θR',18,ha='center');text(a,.19,.30,'外気 θo',18,ha='center');text(a,.72,.23,'人体・機器の内部発熱 H',15,ha='center')
note(a,r'$G=\sum UA+C_p\rho V$　[W/K]',.17,22)
note(a,r'$Q_C=G(\theta_o-\theta_R)+H$',.115,22);note(a,r'冷暖房なし：$\theta_R=\theta_o+H/G$',.065,18);save(f)

f,a=start('h04-multizone','多数室：内壁と空気移動','熱 PDF p.28–41','室ごとに収支を立てる。室間の貫流は全室合計で相殺する。')
room(a,.12,.37,.76,.38);box(a,.49,.37,.02,.38,fc='#e2dac5',ec=INK)
text(a,.29,.68,'室1　θ₁',22,ha='center');text(a,.71,.68,'室2　θ₂',22,ha='center')
text(a,.50,.82,'共通の内壁：U₁₂A₁₂',17,ha='center');arrow(a,.68,.58,.32,.58,ORANGE)
text(a,.50,.525,'内壁を通る熱',15,c=ORANGE,ha='center');arrow(a,.32,.44,.68,.44,BLUE)
text(a,.50,.31,'移動空気：室1の温度を運ぶ',17,c=BLUE,ha='center')
note(a,r'室1へ：$U_{12}A_{12}(\theta_2-\theta_1)$',.215,22)
note(a,r'室2へ：$C_p\rho V_{1\to2}(\theta_1-\theta_2)$',.14,22)
note(a,'空調室は設定室温、自然室温の室は QC＝0 として連立。',.065,15);save(f)

f,a=start('h05-sat','外壁表面と相当外気温度 SAT','熱 PDF p.45–54','不透明部位：日射と夜間放射を等価な外気温度へまとめる')
box(a,.53,.30,.16,.47,fc='#b8beb8',hatch='..');text(a,.61,.815,'外壁の断面',18,ha='center');sun(a,.14,.735)
arrow(a,.18,.71,.51,.63,ORANGE);text(a,.10,.61,'吸収日射 aₛJ',16,c=ORANGE)
arrow(a,.51,.70,.28,.85,BLUE);text(a,.73,.72,'室内側',15,ha='left')
text(a,.07,.47,'外気 θo',19);arrow(a,.13,.40,.51,.40,BLUE);text(a,.16,.34,'外気との熱伝達',15,c=BLUE)
arrow(a,.57,.55,.91,.55,ORANGE);text(a,.76,.62,'室内への熱流 q',15,c=ORANGE,ha='center')
text(a,.51,.245,'夜間放射：外表面からの正味放熱',16,c=BLUE,ha='center')
note(a,r'$SAT=\theta_o+\frac{a_sJ}{\alpha_o}-\frac{\varepsilon J_n}{\alpha_o}$',.155,25)
note(a,r'$q=U(SAT-\theta_R)$',.075,23);save(f)

f,a=start('h06-glass','ガラスに入射した日射の行き先','熱 PDF p.57–60','透過した分と、吸収後に室内へ放出された分が日射熱取得')
box(a,.47,.31,.05,.48,fc='#b7deec',ec=BLUE);text(a,.495,.825,'ガラス',18,ha='center');sun(a,.13,.72)
arrow(a,.18,.70,.45,.57,ORANGE,lw=4);text(a,.22,.835,'入射日射 J',17,c=ORANGE,ha='center')
arrow(a,.46,.55,.20,.35,GREY);text(a,.20,.29,'反射',17,ha='center')
arrow(a,.54,.55,.91,.39,ORANGE,lw=4);text(a,.80,.325,'直接透過',17,c=ORANGE,ha='center')
circle(a,.495,.51,.018,fc=ORANGE,ec=ORANGE);arrow(a,.53,.46,.82,.46,RED);arrow(a,.46,.46,.28,.46,RED)
text(a,.78,.65,'吸収後の室内側放熱',14,c=RED,ha='center');text(a,.18,.565,'屋外',17,c=GREY);text(a,.83,.755,'室内',17,c=GREY)
note(a,'日射熱取得 ＝ 直接透過 ＋ 吸収後の室内側放熱',.20,17)
note(a,r'$S=\eta A_w J$　　$SC$：3mm透明ガラスを基準',.12,20);note(a,'ηは日射による取得、Uは温度差による伝熱の性能。',.06,15);save(f)

f,a=start('h07-shading','内ブラインドと外ブラインド','熱 PDF p.61–62','熱を吸収する位置と、吸収後に放出される側を比較する')
for x,out,title in [(.065,True,'外ブラインド'),(.535,False,'内ブラインド')]:
 text(a,x+.20,.80,title,21,ha='center',weight='bold');wx=x+.23;bx=wx-.075 if out else wx+.075
 box(a,wx,.37,.018,.34,fc='#b7deec',ec=BLUE)
 for y in np.linspace(.40,.68,6):line(a,[bx-.026,bx+.026],[y+.013,y-.013],GREEN,4)
 arrow(a,x+.015,.64,bx-.03,.64,ORANGE,lw=4)
 arrow(a,bx-.005 if out else bx+.02,.49,x+.035 if out else x+.385,.49,RED,lw=3)
 text(a,x+.075,.31,'屋外',15,ha='center');text(a,x+.33,.31,'室内',15,ha='center')
 text(a,x+.20,.23,'吸収熱を屋外へ' if out else '室内に吸収熱を放出',17,c=RED,ha='center')
 text(a,x+.20,.16,'η＝0.13・SC＝0.15' if out else 'η＝0.50・SC＝0.58',17,c=GREEN if out else RED,ha='center')
note(a,'数値はスライドの組合せ例。条件・製品によって変わる。',.075,15);save(f)

f,a=start('h08-eaves','南面の水平庇と太陽高度','熱 PDF p.45・61–66','方位・季節・緯度・庇寸法が、日射の入り方を変える')
for x,summer in [(.08,True),(.55,False)]:
 text(a,x+.18,.80,'夏：太陽高度が高い' if summer else '冬：太陽高度が低い',18,ha='center')
 box(a,x+.27,.29,.025,.37,fc='#c2c7bf');box(a,x+.11,.66,.185,.025,fc='#c2c7bf');box(a,x+.27,.36,.025,.23,fc='#abd5e6',ec=BLUE)
 sun(a,x+.035,.735 if summer else .53,.027)
 if summer:
  for dx in [.015,.065]:arrow(a,x+.055+dx,.735,x+.08+dx,.685,ORANGE,lw=2)
  poly(a,[(x+.12,.65),(x+.27,.40),(x+.27,.65)],fc='#dce6e1',ec='none')
 else:
  for yy in [.49,.56]:arrow(a,x+.07,yy,x+.36,yy-.12,ORANGE,lw=2)
 text(a,x+.19,.225,'庇で直射日光を遮る' if summer else '低い日射を取り入れる',16,ha='center')
note(a,'採光・まぶしさ・眺望も同時に評価する。',.13,18)
note(a,'東西面では低高度の日射も多く、南面と同じ働きとは限らない。',.065,14);save(f)

f,a=start('h09-lowe','Low-E複層ガラスの膜位置','熱 PDF p.63–67','中空層に面する低放射膜が、ガラス間の放射伝熱を抑える')
for x,shade in [(.07,True),(.54,False)]:
 text(a,x+.20,.79,'遮熱タイプ' if shade else '断熱タイプ',21,ha='center')
 for gx in [x+.13,x+.29]:box(a,gx,.36,.025,.33,fc='#a7d6e8',ec=BLUE)
 mx=x+.16 if shade else x+.28;line(a,[mx,mx],[.36,.69],RED,5)
 text(a,x+.20,.30,'中空層',16,ha='center');text(a,x+.20,.225,'外側ガラスの中空層側' if shade else '内側ガラスの中空層側',14,c=RED,ha='center')
 text(a,x+.055,.73,'屋外',13,ha='center');text(a,x+.365,.73,'室内',13,ha='center')
 arrow(a,x+.165,.56,x+.27,.56,ORANGE,lw=2);arrow(a,x+.27,.46,x+.165,.46,ORANGE,lw=2)
note(a,'膜の位置は授業の構成例。膜の性能やガス・層数でも変化する。',.13,14)
note(a,'低放射膜：放射を低減　／　密閉中空層：伝導・対流にも抵抗',.065,14);save(f)

f,a=start('h10-neutral','日射取得がある室の冷暖房負荷','熱 PDF p.69・過去問 問4','G＝46 W/K、取得熱S＝200 W、許容室温22〜27℃')
p=chart(f,[.16,.36,.76,.43],'外気温 θo [℃]','冷房負荷 QC [W]',(0,35),(-850,650))
x=np.linspace(0,35,400);lo=22-200/46;hi=27-200/46;y=np.where(x<lo,46*x-812,np.where(x>hi,46*x-1042,0))
p.axhline(0,color=GREY,lw=1);p.plot(x,y,color=GREEN,lw=3);p.axvspan(lo,hi,color='#c9e2d3',alpha=.7);p.set_xticks([0,10,round(lo,2),round(hi,2),30,35]);p.tick_params(axis='x',labelsize=10);p.set_yticks([-800,-400,0,400]);p.grid(alpha=.15)
text(a,.24,.835,'負：暖房',17,c=BLUE,ha='center');text(a,.73,.835,'正：冷房',17,c=RED,ha='center')
note(a,'無負荷帯：外気温 約17.65〜22.65℃',.22,20)
note(a,r'自然室温 $\theta_{R,nat}=\theta_o+200/46$',.15,21)
note(a,'室温22〜27℃と、外気温の無負荷帯は異なる。',.075,16);save(f)

f,a=start('h11-capacity','断熱性・熱容量と室温変動','熱 PDF p.81–83・99','同じ熱損失係数なら、熱容量が大きいほど応答は緩やか')
for x,heavy in [(.10,False),(.56,True)]:
 text(a,x+.17,.80,'熱容量 小' if not heavy else '熱容量 大',20,ha='center')
 box(a,x,.56,.34,.17,fc='#e8ece7',ec=GOLD,hatch=None,lw=6)
 if heavy:box(a,x+.04,.58,.04,.12,fc='#898e88');box(a,x+.26,.58,.04,.12,fc='#898e88')
 flame(a,x+.17,.58,.07)
p=chart(f,[.17,.25,.73,.24],'時間 t','室温変化（応答率）',(0,5),(0,1.05));t=np.linspace(0,5,200);p.plot(t,1-np.exp(-2*t),color=ORANGE,lw=3);p.plot(t,1-np.exp(-t/2),color=BLUE,lw=3);p.set_yticks([0,.5,1]);p.set_xticks([])
text(a,.27,.515,'小：立上りが速い',14,c=ORANGE,ha='center');text(a,.72,.515,'大：立上りが遅い',14,c=BLUE,ha='center')
note(a,r'熱容量 $C=\rho cV$　　時定数 $\tau=C/G$',.12,22)
note(a,'蓄熱への寄与は、露出面積・厚さ・配置によっても変わる。',.06,14);save(f)

f,a=start('h12-conduction','壁内の小領域の熱収支','熱 PDF p.89–97','壁を小区間に分割：流入と流出の差が、その領域に蓄えられる')
for i in range(7):box(a,.15+i*.10,.43,.10,.29,fc='#f4d98b' if i==3 else '#d5dbd5',ec=GREY)
for x,s in [(.40,'i−1'),(.50,'i'),(.60,'i＋1')]:text(a,x,.77,s,19,ha='center')
arrow(a,.31,.57,.465,.57,ORANGE);arrow(a,.535,.57,.69,.57,ORANGE)
text(a,.34,.365,'流入 qᵢ₋₁',16,c=ORANGE,ha='center');text(a,.65,.365,'流出 qᵢ',16,c=ORANGE,ha='center')
text(a,.50,.29,'蓄熱変化 ＝ 流入 − 流出',21,ha='center')
note(a,r'$q=-\lambda\frac{\partial\theta}{\partial x}$　　$\rho c\frac{\partial\theta}{\partial t}=\lambda\frac{\partial^2\theta}{\partial x^2}$',.18,24)
note(a,r'陽解法：$p=\lambda\Delta t/(\rho c\Delta x^2)$　内部節点は $0\leq p\leq1/2$',.085,18);save(f)

f,a=start('h13-response','集中熱容量モデルのステップ応答','熱 PDF p.99–106','室温と一体の相当熱容量Cを置く近似。外気・発熱は一定。')
p=chart(f,[.16,.34,.76,.45],'無次元時間 t/τ','温度差の比',(0,4),(0,1.06));t=np.linspace(0,4,250);p.plot(t,1-np.exp(-t),c=ORANGE,lw=3);p.plot(t,np.exp(-t),c=BLUE,lw=3);p.axvline(1,c=GREY,ls=':');p.set_xticks([0,1,2,3,4]);p.set_yticks([0,.368,.632,1]);p.grid(alpha=.15)
text(a,.30,.83,r'加熱開始：$1-e^{-t/\tau}$',17,c=ORANGE,ha='center');text(a,.73,.83,r'加熱停止：$e^{-t/\tau}$',17,c=BLUE,ha='center')
note(a,r'$C\frac{d\theta_i}{dt}=G(\theta_o-\theta_i)+H$　　$\tau=C/G$',.20,23)
note(a,'1時定数後：上昇は63.2%　／　残る温度差は36.8%',.12,16)
note(a,'3時定数後：最終変化の約95%へ到達',.065,15);save(f)

f,a=start('h14-human','人体の熱収支と温熱環境6要素','熱 PDF p.108–117','環境側4要素と人体側2要素を、放熱の経路と結び付ける')
room(a,.10,.28,.80,.51);human(a,.49,.31,1.85)
text(a,.20,.72,'気温 θa',18,c=BLUE,ha='center');text(a,.76,.72,'平均放射温度 MRT',16,c=ORANGE,ha='center')
arrow(a,.41,.60,.18,.60,BLUE);arrow(a,.58,.60,.82,.60,ORANGE)
text(a,.20,.535,'対流 C',17,c=BLUE,ha='center');text(a,.77,.535,'放射 R',17,c=ORANGE,ha='center')
arrow(a,.49,.69,.49,.80,GREEN);text(a,.50,.835,'相対湿度 → 蒸発放熱 E',17,c=GREEN,ha='center')
text(a,.19,.39,'気流速度',16,c=BLUE,ha='center');text(a,.76,.40,'着衣量 clo',17,ha='center');text(a,.51,.22,'代謝量 met → 産熱 M',20,ha='center')
note(a,r'$M=C+R+E$',.145,26)
note(a,'1met＝58.2 W/m²　／　1clo＝0.155 m²K/W',.08,17);save(f)

f,a=start('h15-pmv','PMVとPPDの対応','熱 PDF p.117–129','PMVは平均温冷感、PPDは予測不満足者率')
p=chart(f,[.16,.35,.76,.43],'PMV','PPD [%]',(-3,3),(0,105));v=np.linspace(-3,3,400);ppd=100-95*np.exp(-.03353*v**4-.2179*v*v);p.plot(v,ppd,color=ORANGE,lw=3);p.axvspan(-.5,.5,color='#cfe5d4');p.set_xticks([-3,-2,-1,0,1,2,3]);p.set_yticks([5,10,25,50,75,100]);p.tick_params(axis='y',labelsize=10);p.grid(alpha=.18)
text(a,.26,.83,'寒い側',17,c=BLUE,ha='center');text(a,.50,.83,'中立',17,ha='center');text(a,.76,.83,'暑い側',17,c=RED,ha='center')
note(a,'授業の快適範囲：−0.5 ≦ PMV ≦ ＋0.5',.21,19)
note(a,'この範囲でPPDは約10%以下。PMV＝0でも最小約5%。',.13,15)
note(a,'気温・放射・湿度・気流・着衣・代謝の6要素で評価。',.065,15);save(f)

f,a=start('h16-globe','グローブ温度計の熱収支','熱 PDF p.130–132','黒球は空気との対流と、周囲壁面との放射を同時に受ける')
circle(a,.50,.56,.12,fc='#384441',ec=INK);box(a,.492,.31,.016,.25,fc='#cfd3ce');box(a,.477,.52,.046,.13,fc='#e6e4d8');text(a,.50,.75,'黒球の温度 θg',20,ha='center')
arrow(a,.13,.59,.36,.59,BLUE);arrow(a,.64,.59,.87,.59,ORANGE)
text(a,.17,.68,'気温 θa',17,c=BLUE,ha='center');text(a,.82,.68,'壁面 MRT',17,c=ORANGE,ha='center')
text(a,.20,.45,'対流',18,c=BLUE,ha='center');text(a,.80,.45,'放射',18,c=ORANGE,ha='center')
note(a,r'$\alpha_c(\theta_a-\theta_g)=\alpha_r(\theta_g-MRT)$',.235,23)
note(a,r'$\theta_g=\frac{\alpha_c\theta_a+\alpha_rMRT}{\alpha_c+\alpha_r}$',.145,25)
note(a,'WBGTは湿球・黒球温度を使用し、日射の有無で式を変える。',.065,14);save(f)

def sat(t):
 t=np.asarray(t);pws=.61078*np.exp(17.2694*t/(t+237.29));return 1000*.622*pws/(101.325-pws)
f,a=start('h17-psychrometric','空気線図：加熱・冷却と露点','熱 PDF p.136・142–147','標準大気圧101.325 kPa。加熱では絶対湿度xが一定。')
p=chart(f,[.17,.32,.74,.47],'乾球温度 t [℃]','絶対湿度 x [g/kg(DA)]',(0,40),(0,30));t=np.linspace(0,40,400)
for rh in [.2,.4,.6,.8,1]:
 ps=.61078*np.exp(17.2694*t/(t+237.29));x=1000*.622*rh*ps/(101.325-rh*ps);p.plot(t,x,color=GREEN if rh==1 else '#a8bbb0',lw=2 if rh==1 else 1)
for h in range(20,121,20):
 xx=(h-1.01*t)/(2500+1.81*t)*1000;mask=(xx>0)&(xx<sat(t));p.plot(t[mask],xx[mask],color='#d6b78f',lw=.8,ls=':')
xx=8.7;dew=float(np.interp(xx,sat(t),t));p.scatter([20,32,dew],[xx]*3,color=RED,zorder=4);arrow(p,20,xx,32,xx,ORANGE,lw=2);arrow(p,19.8,xx,dew,xx,BLUE,lw=2);p.grid(alpha=.15)
text(a,.22,.835,'緑：飽和曲線',14,c=GREEN);text(a,.55,.835,'薄緑：相対湿度20〜100%',13,c=GREY)
note(a,'20℃・60% → x 約8.7 g/kg(DA)、露点 約12℃',.21,16)
note(a,'橙：加熱（右へ）　／　青：冷却（左へ、飽和まで）',.14,15)
note(a,'飽和後にさらに冷却すると、結露によりxも低下する。',.07,15);save(f)

f,a=start('h18-coil','冷却・除湿コイルとドレン','熱 PDF p.135–137','コイル表面温度が露点以下になると水蒸気が凝縮する')
box(a,.12,.40,.76,.32,fc='#edf5f6',ec=BLUE);box(a,.46,.43,.10,.26,fc='#b7d7df',ec=BLUE,hatch='///')
arrow(a,.05,.56,.43,.56,ORANGE,lw=4);arrow(a,.59,.56,.95,.56,BLUE,lw=4)
text(a,.24,.78,'入口空気：h₁・x₁',18,ha='center');text(a,.76,.78,'出口空気：h₂・x₂',18,ha='center')
text(a,.34,.335,'冷却コイル',17,ha='center');line(a,[.57,.57,.70],[.42,.28,.28],BLUE,3);arrow(a,.70,.28,.70,.20,BLUE,lw=2)
for x,y in [(.58,.45),(.62,.37),(.65,.32)]:circle(a,x,y,.007,fc=BLUE,ec=BLUE)
text(a,.80,.315,'凝縮水を排出',16,c=BLUE,ha='center')
note(a,r'除去熱量 $q_c=G(h_1-h_2)$ [kW]',.14,22)
note(a,r'除湿量 $L=G(x_1-x_2)$ [kg/s]　※xはkg/kg(DA)',.075,17);save(f)

f,a=start('h19-mixing','混合空気と加湿の状態変化','熱 PDF p.135–138','混合は乾き空気質量で保存。水噴霧と蒸気の加湿を区別する。')
box(a,.38,.48,.25,.24,fc='#e1ebe6',ec=GREEN)
arrow(a,.12,.66,.36,.66,BLUE);arrow(a,.12,.52,.36,.52,ORANGE);arrow(a,.65,.60,.91,.60,GREEN)
text(a,.22,.765,'空気1：G₁,h₁,x₁',15,ha='center');text(a,.22,.43,'空気2：G₂,h₂,x₂',15,ha='center');text(a,.76,.735,'混合空気3',18,ha='center')
text(a,.505,.60,'混合箱',20,ha='center');text(a,.76,.46,'G₃＝G₁＋G₂',17,ha='center')
note(a,r'$h_3=\frac{G_1h_1+G_2h_2}{G_1+G_2}$　　$x_3=\frac{G_1x_1+G_2x_2}{G_1+G_2}$',.30,22)
note(a,'水噴霧：ほぼ等エンタルピー、温度低下・x増加',.19,17)
note(a,'蒸気加湿：蒸気の熱が加わり、h・xとも増加',.12,17)
note(a,'h−x線図では混合点は2状態点の線分を反対側の流量比で内分。',.06,13);save(f)

f,a=start('h20-degreedays','暖房デグリーデーと参照温度','熱 PDF p.149–159','設定温度との差が正になる日だけ、温度差を積み上げる')
p=chart(f,[.16,.35,.76,.43],'日','日平均温度 [℃]',(.5,7.5),(0,25));d=np.arange(1,8);tt=np.array([10,15,20,12,7,17,21]);p.plot(d,tt,c=BLUE,lw=2,marker='o');p.axhline(18,c=ORANGE,lw=2);p.fill_between(d,tt,18,where=tt<18,color='#edc68f',alpha=.7,interpolate=True);p.set_xticks(d);p.set_yticks([0,5,10,15,18,25]);p.grid(alpha=.1)
text(a,.28,.835,'青：日平均外気温',16,c=BLUE,ha='center');text(a,.73,.835,'橙：暖房設定18℃',16,c=ORANGE,ha='center')
note(a,r'$DD_H=\sum\max(\theta_{set}-\bar\theta_o,0)$　[K・日]',.225,20)
note(a,r'$Q_{total}=0.0864G\,DD_H$ [MJ]',.15,22)
note(a,r'内部発熱Hを考慮：$\theta_{ref}=\theta_{set}-H/G$',.075,20);save(f)

# Air: equipment and transport paths, rather than abstract process boxes.
f,a=start('a01-combustion','燃焼器具の給気元と排気先','空気 PDF p.11–14','青：燃焼用空気　／　橙：燃焼廃ガス')
for y,name,air,ex in [(.71,'開放型','室内','室内'),(.46,'半密閉型','室内','屋外'),(.21,'密閉型','屋外','屋外')]:
 text(a,.07,y+.06,name,22,weight='bold');text(a,.07,y-.005,'給気：'+air,16,c=BLUE);text(a,.07,y-.065,'排気：'+ex,16,c=ORANGE)
 box(a,.57,y-.07,.36,.15,fc='#edf2ec',ec=GREEN);box(a,.80,y-.05,.07,.08,fc='#c8d3ca');flame(a,.835,y-.023,.035)
 arrow(a,.65 if air=='室内' else .43,y+.015,.795,y+.015,BLUE,lw=2.5);arrow(a,.838,y-.04,.923 if ex=='室内' else .43,y-.04,ORANGE,lw=2.5)
 text(a,.46,y+.105,'屋外',12,c=GREY,ha='center');text(a,.75,y+.105,'室内',12,c=GREY,ha='center')
note(a,'半密閉：CF 自然排気／FE 強制排気　密閉：BF 自然／FF 強制',.065,13);save(f)

f,a=start('a02-oxygen','開放型器具の酸素収支','空気 PDF p.26–28','酸素は「発生」ではなく「消費」。室内濃度の下限との差を使う。')
room(a,.24,.34,.52,.42);box(a,.44,.38,.12,.08,fc='#a5b8ae');flame(a,.50,.48,.07)
arrow(a,.07,.64,.40,.64,BLUE);arrow(a,.60,.49,.93,.49,ORANGE)
text(a,.21,.81,'外気 C₀＝0.21',18,ha='center');text(a,.78,.81,'室内 C≧0.205',18,ha='center')
text(a,.10,.58,'流入 C₀Q',15,c=BLUE);text(a,.78,.42,'流出 CQ',15,c=ORANGE,ha='center')
text(a,.50,.265,'器具による酸素消費 M＝−0.21 Aₜₕ',18,ha='center')
note(a,r'$CQ=C_0Q+M$　　$Q=\frac{0.21A_{th}}{0.21-0.205}=42A_{th}$',.16,21)
note(a,'外気21%と室内下限20.5%は、体積分率へ換算して計算。',.075,14);save(f)

f,a=start('a03-hood','排気フードの捕集と測定','空気 PDF p.43–50','発生した廃ガスのうち、室内に広がる前に排気される割合')
box(a,.15,.32,.70,.47,fc='#f4f3e9');box(a,.40,.34,.22,.04,fc='#bbc2bb');flame(a,.51,.40,.075)
poly(a,[(.33,.66),(.69,.66),(.60,.74),(.42,.74)],fc='#9fb7b0',ec=GREEN);box(a,.48,.74,.06,.09,fc='#9fb7b0',ec=GREEN)
for xx in [.46,.55]:arrow(a,xx,.49,xx,.64,ORANGE,lw=2,connectionstyle='arc3,rad=.15')
arrow(a,.57,.48,.76,.60,ORANGE,lw=2,connectionstyle='arc3,rad=-.3');arrow(a,.51,.835,.51,.87,BLUE,lw=2)
text(a,.73,.75,'排気 Q・Cᴇ',16,c=BLUE);text(a,.23,.47,'発生 M',17,ha='center');text(a,.73,.38,'背景 Cʙ',16,ha='center')
note(a,r'$\eta=Q(C_E-C_B)/M$',.22,25)
note(a,r'室内へ漏れる割合：$1-\eta$　必要換気量：$42(1-\eta)A_{th}$',.14,18)
note(a,'捕集率ηとフィルタ捕集率ηは、対象・定義を区別する。',.07,14);save(f)

f,a=start('a04-contaminant','室内汚染の定常・非定常収支','空気 PDF p.56–76・101–106','完全混合の室：入る量＋発生量−出る量が、室内の蓄積となる')
room(a,.23,.32,.54,.44);arrow(a,.07,.65,.40,.65,BLUE);arrow(a,.60,.46,.93,.46,ORANGE)
human(a,.50,.35,1.1);text(a,.50,.70,'室容積 V・室濃度 C',19,ha='center')
text(a,.14,.81,'外気 C₀・風量 Q',16,ha='center');text(a,.82,.70,'流出 CQ',16,c=ORANGE,ha='center');text(a,.50,.26,'人体等の発生量 M',19,ha='center')
note(a,r'$V\frac{dC}{dt}=C_0Q+M-CQ$',.18,25)
note(a,r'定常：$C=C_0+M/Q$　　必要換気量：$Q=M/(C_{lim}-C_0)$',.09,18);save(f)

f,a=start('a05-recirculation','外気・循環空気とフィルタの配置','空気 PDF p.82–93','循環分も濾過するモデル。給気量 Qs＝外気量 Q₀＋循環量 Qr。')
room(a,.66,.33,.27,.42);text(a,.795,.64,'室内 C',20,ha='center');text(a,.795,.52,'発じん M',17,c=ORANGE,ha='center')
line(a,[.09,.66],[.71,.71],BLUE,9);line(a,[.66,.20,.20],[.38,.38,.71],GREEN,7);arrow(a,.24,.71,.40,.71,INK,lw=2);arrow(a,.62,.38,.38,.38,INK,lw=2);arrow(a,.18,.38,.07,.38,ORANGE,lw=2)
box(a,.12,.67,.035,.08,fc='#efce8a',ec=ORANGE);box(a,.48,.65,.045,.12,fc='#d7dfe4',ec=BLUE,hatch='///')
text(a,.13,.81,'外気 C₀Q₀',16,ha='center');text(a,.105,.57,'プレフィルタ Pf',11,ha='center');text(a,.50,.81,'主フィルタ P',16,ha='center')
text(a,.49,.585,'給気中の汚染量',16,c=BLUE,ha='center');text(a,.48,.535,'P(P𝒇C₀Q₀＋CQr)',17,ha='center')
text(a,.40,.305,'循環 CQ r',16,c=GREEN,ha='center');text(a,.13,.29,'排気 CQ₀',15,c=ORANGE,ha='center')
note(a,r'$P(C_0Q_0+CQ_r)+M=CQ_s$　（$P_f=1$の例）',.20,20)
note(a,'プレフィルタは外気側だけ。循環分へ一律に掛けない。',.12,15)
note(a,'粉じんフィルタによるCO₂除去は、このモデルでは見込まない。',.06,14);save(f)

f,a=start('a06-filter','粒子の捕集：濾材と電気集じん','空気 PDF p.79–87','通過率 P＝1−η。質量基準と個数基準の捕集率は区別する。')
text(a,.27,.79,'エアフィルタ',21,ha='center');text(a,.75,.79,'電気集じん器',21,ha='center')
box(a,.24,.43,.07,.27,fc='#d8dfcf',ec=GREEN,hatch='xxx')
for x,y in [(.10,.63),(.15,.56),(.20,.49),(.245,.64),(.27,.55)]:circle(a,x,y,.009,fc=ORANGE,ec=ORANGE)
circle(a,.40,.57,.008,fc=ORANGE,ec=ORANGE);arrow(a,.07,.38,.44,.38,BLUE,lw=2)
for xx in [.65,.72,.80,.87]:box(a,xx,.43,.012,.25,fc='#b0c5d1',ec=BLUE)
for yy in [.48,.55,.62]:circle(a,.69,yy,.007,fc=ORANGE,ec=ORANGE);arrow(a,.70,yy,.715,yy,ORANGE,lw=1)
text(a,.75,.33,'帯電した粒子を電極で捕集',15,ha='center');text(a,.27,.30,'濃度：C → PC',18,ha='center')
note(a,'HEPA：0.3µmで99.97%以上　／　ULPA：0.15µmで99.9995%以上',.20,14)
note(a,'通過する汚染量：PCQ　／　捕集する汚染量：ηCQ',.13,17)
note(a,'上記の性能値は授業資料の条件。気体と粒子を混同しない。',.065,14);save(f)

f,a=start('a07-isolation','汚染源隔離と室間の気流方向','空気 PDF p.61–63','非喫煙側から喫煙側へ流す。屋外排気で漏出を抑える。')
room(a,.12,.34,.76,.40);box(a,.50,.34,.025,.40,fc='#b9c5bb');box(a,.50,.44,.025,.18,fc=BG,ec=BG)
text(a,.30,.67,'非喫煙側',21,ha='center');text(a,.71,.67,'喫煙室',21,ha='center')
human(a,.30,.39,.9);human(a,.71,.39,.9);arrow(a,.40,.55,.61,.55,BLUE,lw=4);arrow(a,.78,.50,.95,.50,ORANGE,lw=4)
text(a,.50,.285,'授業の例：境界の気流速度0.2 m/s以上',18,ha='center')
note(a,'空気清浄機だけでは、ガス状の全成分を除去できるとは限らない。',.17,14)
note(a,'発生源の隔離・気流の向き・屋外排気を組み合わせる。',.09,16);save(f)

f,a=start('a08-tracer','トレーサガスで換気量を測る','空気 PDF p.115–131','均一化した濃度を測定。発生停止後の減衰から換気を求める。')
room(a,.30,.35,.58,.40);circle(a,.54,.64,.035,fc='#c9d8d1',ec=GREEN)
for t in [0,2*np.pi/3,4*np.pi/3]:arrow(a,.54,.64,.54+.025*np.cos(t),.64+.025*np.sin(t),GREEN,lw=1)
box(a,.08,.36,.055,.17,fc='#b7cdd7',ec=BLUE);line(a,[.108,.108,.40],[.53,.58,.58],BLUE,2);text(a,.11,.29,'ガス供給',15,ha='center')
for x,y in [(.44,.48),(.69,.61),(.77,.43)]:circle(a,x,y,.012,fc=ORANGE,ec=ORANGE)
box(a,.48,.17,.21,.10,fc='#d5dfd8',ec=GREEN);text(a,.585,.22,'濃度計',17,ha='center');line(a,[.69,.69,.65],[.61,.28,.28],GREY,1.5)
text(a,.61,.81,'攪拌して均一に混合',19,ha='center')
note(a,'定常濃度法：一定供給して定常を待つ → Q＝M/(C−C₀)',.12,16)
note(a,'一定濃度法：濃度を一定に保つよう、供給量を調整する。',.065,15);save(f)

f,a=start('a09-decay','濃度減衰と片対数表示','空気 PDF p.103–113・119–123','室濃度Cそのものではなく、背景濃度C₀との差を見る')
for rect,log in [([.15,.39,.33,.36],False),([.63,.39,.31,.36],True)]:
 p=chart(f,rect,'無次元時間 Nt','ln(濃度差の比)' if log else '濃度差の比',(0,3),(-3.15,.15) if log else (0,1.05));t=np.linspace(0,3,180);p.plot(t,-t if log else np.exp(-t),c=BLUE,lw=3);p.set_xticks([0,1,2,3]);p.set_yticks([-3,-2,-1,0] if log else [0,.368,1]);p.grid(alpha=.15)
text(a,.30,.81,'通常の表示：指数減衰',17,ha='center');text(a,.76,.81,'片対数：直線',17,ha='center')
note(a,r'$C-C_0=(C_s-C_0)e^{-Nt}$　　$N=Q/V$',.255,22)
note(a,r'$N=\frac{\ln[(C_1-C_0)/(C_2-C_0)]}{t_2-t_1}$',.16,24)
note(a,'Nt＝1で36.8%、Nt＝3で約5%の濃度差が残る。',.07,16);save(f)

f,a=start('a10-ventpatterns','室内の流れと空気交換効率','空気 PDF p.198・AIJ公開講習資料 p.7','同じ換気量でも、居住域への届き方は異なる')
for x,y,kind,title in [(.08,.53,'piston','ピストンフロー'),(.55,.53,'mix','完全混合'),(.08,.19,'disp','置換換気'),(.55,.19,'short','ショートサーキット')]:
 text(a,x+.18,y+.265,title,18,ha='center');room(a,x,y+.045,.36,.18)
 if kind=='piston':
  for yy in [y+.09,y+.15,y+.20]:arrow(a,x-.02,yy,x+.38,yy,BLUE,lw=1.8)
 elif kind=='mix':
  a.add_patch(Arc((x+.18,y+.14),.23,.12,theta1=20,theta2=340,color=BLUE,lw=2));arrow(a,x+.286,y+.17,x+.26,y+.198,BLUE,lw=2);arrow(a,x-.02,y+.18,x+.06,y+.18,BLUE,lw=1.8);arrow(a,x+.30,y+.10,x+.38,y+.10,ORANGE,lw=1.8)
 elif kind=='disp':
  human(a,x+.23,y+.052,.65);arrow(a,x-.02,y+.08,x+.16,y+.08,BLUE,lw=2);arrow(a,x+.23,y+.11,x+.23,y+.24,ORANGE,lw=2);arrow(a,x+.26,y+.21,x+.38,y+.21,ORANGE,lw=2)
 else:
  arrow(a,x-.02,y+.19,x+.38,y+.19,BLUE,lw=2);box(a,x+.05,y+.06,.26,.07,fc='#e9d7c5',ec='none')
 text(a,x+.18,y,'εᵃ＝1.0' if kind=='piston' else 'εᵃ＝0.5' if kind=='mix' else '0.5＜εᵃ＜1.0' if kind=='disp' else 'εᵃ＜0.5の場合',16,c=GREEN if kind!='short' else RED,ha='center')
note(a,r'$\varepsilon^a=\frac{\tau_n/2}{\langle\tau\rangle}$　　$\tau_n=V/Q$',.085,23);save(f)

f,a=start('a11-agecurves','ステップ法で空気齢を測る','空気 PDF p.168–173','色を塗った面積が局所平均空気齢。背景との差で正規化する。')
for rect,up in [([.14,.43,.34,.33],True),([.62,.43,.32,.33],False)]:
 p=chart(f,rect,'経過時間 t','正規化濃度',(0,4),(0,1.05));t=np.linspace(0,4,250);y=1-np.exp(-t) if up else np.exp(-t);p.plot(t,y,c=BLUE,lw=2);p.fill_between(t,y,1 if up else 0,color='#8fb7d5',alpha=.7);p.set_xticks([0,2,4]);p.set_yticks([0,1]);p.axhline(1,c=GREY,lw=1,ls=':')
text(a,.30,.82,'ステップアップ',18,ha='center');text(a,.76,.82,'ステップダウン',18,ha='center')
note(a,r'アップ：$\tau_P=\int_0^\infty[1-C_{up}(t)/C_s]dt$',.285,22)
note(a,r'ダウン：$\tau_P=\int_0^\infty C_{dn}(t)/C_s\,dt$',.19,22)
note(a,r'パルス法：$\tau_P=\int tC_Pdt\,/\,\int C_Pdt$',.095,22);save(f)

f,a=start('a12-airage','局所平均空気齢と室平均空気齢','空気 PDF p.158–162・182–191','入口で空気齢0。室内の地点・室全体・排気口は異なる評価対象。')
room(a,.15,.38,.70,.38)
for x,y,X,Y in [(.08,.65,.36,.65),(.36,.65,.65,.61),(.65,.61,.91,.49),(.30,.59,.42,.46),(.55,.48,.66,.55)]:arrow(a,x,y,X,Y,BLUE,lw=2)
circle(a,.49,.59,.018,fc=ORANGE,ec=ORANGE);text(a,.49,.82,'地点P：局所平均 τP',19,ha='center')
text(a,.18,.31,'給気：0',16,ha='center');text(a,.78,.31,'排気：τn＝V/Q',16,ha='center')
note(a,r'点の評価：$\varepsilon_P^a=\tau_n/\tau_P$',.225,24)
note(a,r'室全体：$\varepsilon^a=(\tau_n/2)/\langle\tau\rangle$',.145,24)
note(a,'汚染質除去の指標は濃度と発生源を用いる：εᶜ＝Cₑ/〈C〉',.065,15);save(f)

f,a=start('a13-pressure','送風系の全圧・静圧・動圧','空気 PDF p.211–215','断面一定のダクト。送風機以外では全圧は流れに沿って低下。')
line(a,[.16,.90],[.77,.77],BLUE,17);circle(a,.51,.77,.034,fc='#70a1bd',ec=BLUE);arrow(a,.06,.77,.13,.77,ORANGE,lw=2);arrow(a,.92,.77,.98,.77,ORANGE,lw=2)
text(a,.51,.83,'送風機',17,ha='center')
p=chart(f,[.16,.36,.74,.33],'流れ方向の位置','圧力（大気圧を基準）',(0,9),(-2.5,3.5));x=np.array([0,1,4,5,8,9]);pt=np.array([0,-.3,-1.2,2.8,.6,0]);ps=np.array([0,-.9,-1.8,2.2,0,0]);p.plot(x,pt,c=BLUE,lw=3);p.plot(x,ps,c=RED,lw=3);p.axhline(0,c=GREY,lw=1);p.set_xticks([]);p.set_yticks([0]);
for xx in [1,4,5,8]:p.axvline(xx,c='#aebbb2',ls=':',lw=1)
text(a,.28,.255,'青：全圧 PT',17,c=BLUE,ha='center');text(a,.70,.255,'赤：静圧 Ps',17,c=RED,ha='center')
note(a,r'$P_T=P_s+\rho U^2/2$　　2線の差が動圧',.175,23)
note(a,'送風機全圧＝前後の全圧差',.115,17)
note(a,'送風機静圧＝送風機全圧−吐出し口動圧',.065,16);save(f)

f,a=start('a14-pressuremeasure','流れる空気の圧力を測る','空気 PDF p.211–215・三菱電機 技術資料','全圧は流れを正面で受け、静圧は壁面の孔で測る模式図')
box(a,.08,.50,.84,.24,fc='#edf3f5',ec=BLUE)
for yy in [.56,.63,.70]:arrow(a,.12,yy,.37,yy,BLUE,lw=2)
line(a,[.47,.59,.59],[.61,.61,.83],INK,4);line(a,[.78,.78],[.50,.30],INK,3)
text(a,.61,.86,'全圧管（正面）',17,ha='center');text(a,.77,.23,'静圧孔（壁面）',17,ha='center')
text(a,.29,.40,'静止するまで減速',16,ha='center');text(a,.29,.34,'運動エネルギーも圧力へ',14,ha='center')
note(a,r'$P_d=P_T-P_s=\rho U^2/2$ [Pa]',.15,25)
note(a,'ρ＝1.2kg/m³、U＝10m/s なら動圧は60Pa。',.075,17);save(f)

f,a=start('a15-operating','送風機の動作点と系の抵抗','空気 PDF p.218–231','風量は、送風機特性とダクト系抵抗の交点で決まる')
p=chart(f,[.16,.35,.76,.43],'風量 Q','圧力 P',(0,1.5),(0,1.3));q=np.linspace(0,1.5,300);p.plot(q,1.2-.45*q*q,c=BLUE,lw=3);p.plot(q,.7*q*q,c=ORANGE,lw=3);p.plot(q,1.3*q*q,c=RED,lw=2,ls='--');q1=math.sqrt(1.2/1.15);q2=math.sqrt(1.2/1.75);p.scatter([q1,q2],[.7*q1*q1,1.3*q2*q2],s=70,color=GREEN,zorder=4);p.set_xticks([]);p.set_yticks([])
text(a,.25,.83,'青：送風機特性',16,c=BLUE,ha='center');text(a,.72,.83,'橙・赤：系抵抗',16,c=ORANGE,ha='center')
note(a,'抵抗が増える（赤破線）→ 動作点は小風量側へ',.23,18)
note(a,r'圧力損失は概ね $\Delta P\propto Q^2$',.155,22)
note(a,r'空気動力 $W_{air}=QP_T$　　軸動力 $W_{shaft}=QP_T/\eta_f$',.08,19);save(f)

f,a=start('a16-fans','送風機の直列・並列運転','空気 PDF p.224–231','同じ送風機2台の理想的な加算。実際の風量は抵抗曲線との交点。')
for y,series in [(.68,True),(.39,False)]:
 text(a,.07,y+.12,'直列運転' if series else '並列運転',22)
 if series:
  line(a,[.12,.87],[y,y],BLUE,12)
  for x in [.42,.64]:circle(a,x,y,.045,fc='#9cb9cb',ec=BLUE)
  arrow(a,.88,y,.95,y,BLUE,lw=2)
 else:
  for yy in [y-.055,y+.055]:line(a,[.20,.73],[yy,yy],BLUE,10);circle(a,.48,yy,.04,fc='#9cb9cb',ec=BLUE)
  line(a,[.20,.20],[y-.055,y+.055],BLUE,9);line(a,[.73,.73],[y-.055,y+.055],BLUE,9);arrow(a,.76,y,.94,y,BLUE,lw=2)
 text(a,.50,y-.13,'同じ風量で、圧力を加算' if series else '同じ圧力で、風量を加算',19,ha='center')
note(a,'回転数k倍：風量k倍・圧力k²倍・動力k³倍',.135,18)
note(a,'相似則には、同じ機種・相似条件などの前提がある。',.07,14);save(f)

f,a=start('a17-duct','直管・曲がり・拡大部の損失','空気 PDF p.233–245','各区間の流速で動圧を求め、経路の摩擦・局部損失を加算する')
poly(a,[(.10,.64),(.40,.64),(.40,.43),(.56,.43),(.74,.36),(.91,.36),(.91,.65),(.74,.65),(.56,.57),(.54,.57),(.54,.78),(.10,.78)],fc='#d8e5e9',ec=BLUE,lw=2)
arrow(a,.13,.71,.35,.71,BLUE,lw=3);arrow(a,.47,.68,.47,.51,BLUE,lw=3);arrow(a,.58,.50,.85,.50,BLUE,lw=3)
text(a,.25,.83,'直管：摩擦損失',17,ha='center');text(a,.40,.32,'曲がり：局部損失',17,ha='center');text(a,.79,.72,'拡大：減速',16,ha='center')
note(a,r'直管：$\Delta P=\lambda\frac{l}{d}\frac{\rho U^2}{2}$',.225,23)
note(a,r'局部：$\Delta P=\zeta\frac{\rho U^2}{2}$　　流量：$Q=UA$',.14,23)
note(a,'急な拡大・縮小を避け、剥離・乱れ・騒音を抑える。',.065,15);save(f)

f,a=start('a18-jet','噴流の広がりと周囲空気の誘引','空気 PDF p.275–282','吹出し直後は速く、下流ほど周囲の空気を巻き込み広がる')
box(a,.08,.48,.08,.12,fc='#c7d3d7',ec=BLUE);poly(a,[(.16,.48),(.89,.29),(.89,.79),(.16,.60)],fc='#e2eef3',ec='none')
line(a,[.16,.90],[.48,.29],BLUE,2);line(a,[.16,.90],[.60,.79],BLUE,2);line(a,[.16,.90],[.54,.54],GREY,1,ls='--')
for x,w,amp in [(.25,.08,.06),(.49,.17,.045),(.75,.25,.025)]:
 yy=np.linspace(.54-w,.54+w,90);xx=x+amp*np.exp(-3*((yy-.54)/w)**2);line(a,xx,yy,ORANGE,2)
for x,y,X,Y in [(.44,.77,.48,.67),(.68,.27,.70,.36),(.85,.84,.84,.73)]:arrow(a,x,y,X,Y,GREEN,lw=2)
text(a,.24,.82,'吹出し口径 D₀',16,ha='center');text(a,.57,.84,'周囲空気を誘引',16,c=GREEN,ha='center')
text(a,.50,.215,'橙：断面の速度分布（中心が速い）',16,c=ORANGE,ha='center')
note(a,r'第3域：$V_x/V_0=KD_0/X$',.145,25)
note(a,'噴流は下流ほど太くなり、中心軸速度は低下する。',.07,16);save(f)

f,a=start('a19-jetdecay','噴流の4領域と到達距離','空気 PDF p.278–283','軸対称噴流の模式図。領域境界の距離は例であり固定値ではない。')
p=chart(f,[.16,.34,.76,.44],'吹出し口からの距離 X / D₀','中心速度比 Vx / V₀',(1,100),(.01,1.4));p.set_xscale('log');p.set_yscale('log');xx=np.logspace(0,2,400);yy=np.where(xx<=4,1,np.where(xx<=12,2/np.sqrt(xx),np.where(xx<=60,math.sqrt(48)/xx,math.sqrt(48)/60*(60/xx)**4)));p.plot(xx,yy,c=BLUE,lw=3);p.set_xticks([1,4,12,60,100],['1','4','12','60','100']);p.set_yticks([.01,.1,1],['0.01','0.1','1']);p.grid(which='both',alpha=.14)
for x in [4,12,60]:p.axvline(x,c=GREY,ls=':',lw=1)
note(a,'①定速域 → ②遷移域 → ③主流域 → ④消滅域',.23,17)
note(a,'①ほぼ一定　②1/√X　③1/X　④急減衰',.155,18)
note(a,r'到達距離：$X_t=KD_0V_0/V_t$　（通常 $V_t=0.25$ m/s）',.08,19);save(f)

f,a=start('a20-anemo','アネモ型吹出し口の断面','空気 PDF p.287','中コーンを動かして、冷房と暖房の吹出し方向を変える')
for x,cool in [(.07,True),(.55,False)]:
 text(a,x+.19,.80,'冷房：中コーンを下げる' if cool else '暖房：中コーンを上げる',15,ha='center')
 box(a,x+.15,.63,.08,.12,fc='#bdcdd2',ec=BLUE)
 line(a,[x+.02,x+.14],[.59,.59],GREY,4);line(a,[x+.24,x+.38],[.59,.59],GREY,4)
 for d in [0,.05,.10]:
  y=.56-d*.18;line(a,[x+.19-.065-d*.5,x+.19,x+.19+.065+d*.5],[y+.035,y,y+.035],INK,2)
 cy=.49 if cool else .60;poly(a,[(x+.13,cy+.025),(x+.25,cy+.025),(x+.19,cy-.005)],fc='#90a6a3',ec=GREEN)
 if cool:
  arrow(a,x+.15,.57,x+.02,.53,BLUE,lw=3);arrow(a,x+.25,.57,x+.38,.53,BLUE,lw=3)
 else:arrow(a,x+.13,.56,x+.15,.37,RED,lw=3);arrow(a,x+.25,.56,x+.23,.37,RED,lw=3)
 text(a,x+.19,.28,'水平吹出し' if cool else '下向き吹出し',21,c=BLUE if cool else RED,ha='center')
note(a,'暖房では、暖気を居住域まで届ける下向き成分が重要。',.17,16)
note(a,'誘引性・混合拡散性がよく、大きな風量を処理しやすい。',.09,15);save(f)

f,a=start('a21-outlets','吹出し口の形状と噴流','空気 PDF p.284–296','形状によって拡散・誘引・到達距離・風向調整が異なる')
for x,y,name,kind in [(.08,.55,'ノズル：軸対称噴流','nozzle'),(.55,.55,'スロット：平面噴流','slot'),(.08,.21,'パン型：放射状噴流','pan'),(.55,.21,'グリル／レジスタ','grille')]:
 text(a,x+.18,y+.25,name,16,ha='center')
 if kind=='nozzle':
  poly(a,[(x+.01,y+.06),(x+.11,y+.10),(x+.11,y+.17),(x+.01,y+.21)],fc='#c4d3d7',ec=BLUE)
  for d in [-.03,0,.03]:arrow(a,x+.12,y+.135+d,x+.35,y+.135+2*d,BLUE,lw=2)
 elif kind=='slot':
  poly(a,[(x+.03,y+.12),(x+.18,y+.20),(x+.21,y+.18),(x+.06,y+.10)],fc='#b4c7ce',ec=BLUE)
  for d in [0,.055,.11]:arrow(a,x+.08+d,y+.13+d*.4,x+.20+d,y+.06+d*.4,BLUE,lw=2)
 elif kind=='pan':
  box(a,x+.15,y+.13,.06,.08,fc='#b4c7ce',ec=BLUE);poly(a,[(x+.09,y+.11),(x+.27,y+.11),(x+.24,y+.07),(x+.12,y+.07)],fc='#b4c7ce',ec=BLUE)
  arrow(a,x+.14,y+.14,x+.02,y+.07,BLUE,lw=2);arrow(a,x+.22,y+.14,x+.34,y+.07,BLUE,lw=2)
 else:
  box(a,x+.03,y+.055,.22,.15,fc='#dbe4e2',ec=BLUE)
  for yy in [y+.08,y+.115,y+.15,y+.185]:line(a,[x+.04,x+.24],[yy,yy+.012],GREEN,2)
  arrow(a,x+.27,y+.12,x+.36,y+.15,BLUE,lw=2)
note(a,'パン型はアネモ型より誘引が小さく到達距離が長い。',.105,15)
note(a,'グリル：風量調整シャッタなし　／　レジスタ：シャッタあり',.06,14);save(f)

f,a=start('a22-draft','窓の冷下降流と暖房時の成層','空気 PDF p.260–274','室平均温度が同じでも、窓際・足元の温度と気流は異なる')
for x,draft in [(.08,True),(.55,False)]:
 text(a,x+.18,.80,'冷たい窓：コールドドラフト' if draft else '天井の暖気：上下温度差',15,ha='center');room(a,x,.36,.36,.35);human(a,x+.23,.38,.85)
 if draft:
  box(a,x+.005,.45,.02,.21,fc='#91c7e2',ec=BLUE);arrow(a,x+.07,.63,x+.07,.40,BLUE,lw=3);arrow(a,x+.07,.40,x+.30,.40,BLUE,lw=3);text(a,x+.18,.28,'窓下暖房・窓断熱などで対策',13,ha='center')
 else:
  box(a,x+.01,.60,.34,.09,fc='#f1d7b8',ec='none');arrow(a,x+.17,.65,x+.32,.65,RED,lw=3);text(a,x+.18,.28,'下向き成分・到達距離を確保',13,ha='center')
note(a,'DRが増える条件：空気温度が低い・風速が大きい・乱れが大きい',.18,14)
note(a,'居住域は授業では床上1.8mまで。ADPIは快適条件を満たす点の割合。',.10,13);save(f)

f,a=start('a23-cfd','室内気流の予測とタスク領域','空気 PDF p.297–307','形状・メッシュ・給排気・温度・発熱条件を与え、実測で検証する')
room(a,.13,.32,.74,.45)
for x in np.linspace(.13,.87,17):line(a,[x,x],[.32,.77],'#d3dfd7',.6)
for y in np.linspace(.32,.77,11):line(a,[.13,.87],[y,y],'#d3dfd7',.6)
human(a,.53,.36,1.25);box(a,.59,.43,.14,.015,fc='#bda384',ec=ORANGE);box(a,.62,.45,.05,.045,fc='#afcbd5',ec=BLUE)
for yy in [.65,.70]:arrow(a,.17,yy,.76,yy,BLUE,lw=2)
arrow(a,.70,.71,.70,.53,BLUE,lw=2);arrow(a,.49,.61,.49,.74,ORANGE,lw=2)
text(a,.50,.83,'背景のアンビエント領域',18,ha='center');text(a,.50,.255,'人の周囲のタスク領域を重点的に空調',18,ha='center')
note(a,'CFDの色・流線だけで判断せず、境界条件と測定結果を確認。',.15,15)
note(a,'タスク・アンビエント空調は、全室を同一条件にする方式と区別。',.08,14);save(f)

f,a=start('h21-solar','面に入射する日射の3成分','熱 PDF p.45–46','面の方位・傾斜・太陽位置・周辺の遮蔽で入射量が変わる')
box(a,.59,.29,.16,.43,fc='#c2c9be',ec=GREEN);line(a,[.07,.94],[.27,.27],GREY,3);sun(a,.16,.77)
poly(a,[(.29,.79),(.40,.82),(.48,.78),(.42,.74),(.30,.75)],fc='#d8e7eb',ec='none')
arrow(a,.20,.74,.57,.60,ORANGE,lw=3);arrow(a,.40,.73,.58,.67,BLUE,lw=3);arrow(a,.23,.29,.57,.43,GREEN,lw=3)
text(a,.22,.59,'直達日射 Jd',18,c=ORANGE,ha='center');text(a,.65,.81,'天空日射 Js',18,c=BLUE,ha='center');text(a,.24,.39,'地物反射 Jr',18,c=GREEN,ha='center')
text(a,.80,.52,'外壁',18,ha='center');note(a,r'$J=J_d+J_s+J_r$',.18,27)
note(a,'日射は短波、夜間放射は大気等との正味長波放射。',.09,16);save(f)

f,a=start('h22-airprocess','空気線図上の混合と加湿','熱 PDF p.135–138','h−x表示：混合は直線、水噴霧はほぼ等エンタルピー')
p=chart(f,[.18,.34,.72,.45],'絶対湿度 x [g/kg(DA)]','比エンタルピー h [kJ/kg(DA)]',(0,20),(0,90))
p.plot([4,16],[20,70],c=GREEN,lw=3);p.scatter([4,8,16],[20,110/3,70],c=GREEN,s=65,zorder=4);arrow(p,8,110/3,13,110/3,BLUE,lw=2);arrow(p,8,110/3,12,49,ORANGE,lw=2);p.set_xticks([0,4,8,12,16,20]);p.set_yticks([0,20,40,60,80]);p.grid(alpha=.15)
text(a,.28,.83,'緑：状態1と2の混合線',14,c=GREEN,ha='center');text(a,.73,.83,'混合比 G₁:G₂＝2:1 の例',14,ha='center')
note(a,'青：水噴霧（hほぼ一定）　／　橙：蒸気加湿（hも増加）',.23,15)
note(a,'混合点は、流量が多い状態点の近くに位置する。',.15,17)
note(a,'温度の加重平均は近似。hとxの保存で状態を決める。',.075,16);save(f)

f,a=start('h23-moisture','絶対湿度と相対湿度を区別する','熱 PDF p.133–134・142–147','絶対湿度xは乾き空気質量基準、相対湿度φは飽和圧に対する比')
for x,warm in [(.13,False),(.57,True)]:
 box(a,x,.40,.30,.33,fc='#f9e7cf' if warm else '#e1edf3',ec=ORANGE if warm else BLUE)
 for dx,dy in [(.055,.08),(.14,.19),(.22,.26),(.23,.11),(.11,.28)]:circle(a,x+dx,.40+dy,.011,fc=BLUE,ec=BLUE)
 text(a,x+.15,.795,'加熱前' if not warm else '加熱後',22,ha='center');text(a,x+.15,.33,'水蒸気量は同じ',17,ha='center')
note(a,'加熱してもxは一定。飽和水蒸気圧が増えるのでφは低下。',.225,16)
note(a,r'$x=\frac{0.622f}{P-f}$　　$\varphi=\frac{f}{f_s}\times100$ [%]',.14,24)
note(a,'x：kg/kg(DA)　／　f：水蒸気分圧　／　fs：飽和水蒸気圧',.065,14);save(f)

f,a=start('h24-wbgt','WBGTで用いる3つの温度','熱 PDF p.130–132','日射ありと日射なしで、黒球・乾球の重みが変わる')
for x,name,kind in [(.22,'自然湿球 θwb','wet'),(.50,'黒球 θg','globe'),(.78,'乾球 θa','dry')]:
 if kind=='globe':circle(a,x,.59,.065,fc='#394642',ec=INK)
 else:
  box(a,x-.012,.43,.024,.26,fc='#e6e5d9',ec=GREY);circle(a,x,.44,.025,fc='#87bed6' if kind=='wet' else ORANGE,ec=BLUE if kind=='wet' else ORANGE)
  if kind=='wet':box(a,x-.034,.37,.068,.07,fc='#d6e5ed',ec=BLUE,hatch='///')
 line(a,[x,x],[.28,.41 if kind!='globe' else .52],GREY,2);text(a,x,.77,name,20,ha='center')
note(a,r'日射あり：$WBGT=0.7\theta_{wb}+0.2\theta_g+0.1\theta_a$',.21,20)
note(a,r'日射なし：$WBGT=0.7\theta_{wb}+0.3\theta_g$',.135,22)
note(a,'湿球：蒸発のしやすさ　／　黒球：放射と対流　／　乾球：気温',.065,14);save(f)

f,a=start('a24-removal','汚染質の発生源と除去の指標','空気 PDF p.143–156','空気の若さを測る空気交換と、発生源からの汚染除去を区別する')
room(a,.15,.35,.70,.41);human(a,.41,.38,1.05);flame(a,.43,.62,.045);arrow(a,.07,.48,.30,.48,BLUE,lw=3);arrow(a,.48,.67,.91,.67,ORANGE,lw=3)
circle(a,.69,.48,.018,fc=GREEN,ec=GREEN);text(a,.40,.82,'発生源の位置を指定',19,ha='center');text(a,.74,.61,'排気濃度 Ce',16,c=ORANGE,ha='center');text(a,.69,.29,'地点Pの濃度 CP',16,c=GREEN,ha='center')
note(a,r'局所の清浄度：$\varepsilon_P^c=C_e/C_P$',.21,23)
note(a,r'室全体の除去効率：$\varepsilon^c=C_e/\langle C\rangle$',.135,23)
note(a,'給気濃度を背景として補正。既知発生源の条件で評価する。',.065,14);save(f)

f,a=start('a25-fanblades','シロッコとターボの羽根','空気 PDF p.216–225','遠心送風機の羽根を回転方向との関係で比較する模式図')
for x,forward in [(.27,True),(.74,False)]:
 text(a,x,.81,'シロッコ：前向き羽根' if forward else 'ターボ：後向き羽根',16,ha='center')
 circle(a,x,.55,.17,fc='#edf1ed',ec=GREEN);circle(a,x,.55,.065,fc='#c0d1c9',ec=GREEN)
 for t in np.linspace(0,2*np.pi,12 if forward else 8,endpoint=False):
  r=np.linspace(.075,.16,30);ang=t+(1 if forward else -1)*.65*(r-.075)/.085;line(a,x+r*np.cos(ang),.55+r*np.sin(ang),BLUE,2)
 arrow(a,x+.19,.49,x+.19,.61,ORANGE,lw=2,connectionstyle='arc3,rad=.25')
 text(a,x,.29,'外周側へ向かう羽根が\n回転方向へ曲がる' if forward else '外周側へ向かう羽根が\n回転と逆方向へ曲がる',15,ha='center',linespacing=1.6)
note(a,'橙矢印：反時計回りの回転方向　／　羽根の曲がりは模式化',.15,14)
note(a,'授業では、ターボの高効率などの特性も比較する。',.08,15);save(f)

f,a=start('a26-ductends','ベルマウス入口と大気開放出口','空気 PDF p.237–238','入口では加速、出口では噴流の運動エネルギーが下流で散逸')
for x,entry in [(.08,True),(.55,False)]:
 text(a,x+.18,.81,'ベルマウス入口' if entry else '大気開放出口',19,ha='center')
 if entry:
  line(a,[x+.02,x+.05,x+.11,x+.33],[.51,.57,.60,.60],BLUE,3);line(a,[x+.02,x+.05,x+.11,x+.33],[.77,.71,.68,.68],BLUE,3)
 else:
  line(a,[x+.02,x+.19],[.59,.59],BLUE,3);line(a,[x+.02,x+.19],[.70,.70],BLUE,3)
  for d in [-.03,0,.03]:arrow(a,x+.20,.645+d,x+.37,.645+d*2,BLUE,lw=2)
 arrow(a,x+.04,.645,x+.16,.645,ORANGE,lw=2)
 text(a,x+.18,.44,'全圧損失が小さい' if entry else '出口静圧＝大気圧',17,ha='center')
 text(a,x+.18,.35,'ζ ≒ 0' if entry else '出口損失 ζ ≒ 1',22,c=GREEN,ha='center')
note(a,'入口：静圧を下げて加速、動圧は増加する。',.235,17)
note(a,'出口：残っている動圧が拡散・散逸し、全圧が低下する。',.16,16)
note(a,r'局部損失：$\Delta P=\zeta\rho U^2/2$',.08,23);save(f)

f,a=start('a27-draftindex','局所的な気流の不快感とDR','空気 PDF p.251–259','平均温度だけでなく、局所温度・平均風速・乱れを確認する')
p=chart(f,[.16,.35,.76,.43],'平均気流速度 v [m/s]','DR [%]',(.05,.40),(0,80));v=np.linspace(.05,.4,200)
for temp,c in [(20,BLUE),(26,ORANGE)]:p.plot(v,(34-temp)*(v-.05)**.62*(.37*v*40+3.14),c=c,lw=3)
p.set_xticks([.05,.1,.2,.3,.4]);p.set_yticks([15,30,50,70]);p.grid(alpha=.15)
text(a,.27,.83,'青：20℃',17,c=BLUE,ha='center');text(a,.72,.83,'橙：26℃',17,c=ORANGE,ha='center')
note(a,'乱れの強さTu＝40%の比較例。低温・強風ほどDRが大きい。',.23,15)
note(a,r'$DR=(34-t_a)(v-0.05)^{0.62}(0.37v\,Tu+3.14)$',.15,20)
note(a,'EDTは温度差と風速、ADPIは快適条件を満たす点の割合。',.07,15);save(f)

f,a=start('h25-shf','顕熱・潜熱と室内の状態変化','熱 PDF p.137–138','冷たく乾いた吹出し空気が、室内で熱と水蒸気を受け取る')
p=chart(f,[.17,.35,.74,.42],'乾球温度 t [℃]','絶対湿度 x [g/kg(DA)]',(14,30),(5,13));p.scatter([18,26],[7,10],color=GREEN,s=70,zorder=4)
arrow(p,18,7,26,7,ORANGE,lw=2.5);arrow(p,26,7,26,10,BLUE,lw=2.5);arrow(p,18,7,26,10,GREEN,lw=2);p.set_xticks([14,18,22,26,30]);p.set_yticks([7,10,13]);p.grid(alpha=.15)
text(a,.28,.83,'吹出し：18℃・7g/kg',16,ha='center');text(a,.74,.83,'室内：26℃・10g/kg',16,ha='center')
note(a,'橙：温度上昇＝顕熱　／　青：水蒸気増加＝潜熱',.23,17)
note(a,r'$SHF=q_s/(q_s+q_l)$　　$u=\Delta h/\Delta x$',.15,23)
note(a,'室内負荷の顕熱比に合う方向に、吹出し状態点を設定する。',.075,15);save(f)

f,a=start('h26-solarload','窓1面＋換気の定常熱負荷','熱 PDF p.69・過去問 問4','他の壁面・内部発熱・夜間放射は無視。冷房側を正とする。')
room(a,.44,.30,.47,.45);box(a,.43,.47,.025,.23,fc='#a6cfe0',ec=BLUE);box(a,.43,.33,.025,.06,fc=BG,ec=BLUE)
for yy,label,c in [(.65,'貫流熱 UA₍w₎(θo−θR)',ORANGE),(.50,'日射熱取得 ηA₍w₎J',ORANGE),(.35,'換気熱 CpρV(θo−θR)',BLUE)]:
 text(a,.07,yy+.055,label,14,c=c);arrow(a,.07,yy,.60,yy,c,lw=3)
text(a,.77,.68,'室温 θR',19,ha='center');text(a,.21,.795,'外気温 θo',18,ha='center');arrow(a,.79,.53,.79,.25,GREEN,lw=3)
text(a,.77,.205,'除去する熱 QC',18,c=GREEN,ha='center')
note(a,r'$Q_C=(UA_w+C_p\rho V)(\theta_o-\theta_R)+\eta A_wJ$',.125,21)
note(a,'図は外気温＞室温の場合。負の負荷は暖房を意味する。',.065,14);save(f)

(OUT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
(OUT/'layout-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
print('TOTAL',len(catalog),'issues',sum(len(r['issues']) for r in reports))

if any(r['issues'] for r in reports):raise SystemExit('Text or arrow collisions detected; see layout-report.json')
