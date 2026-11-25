"""Install the explicit-link pack importer; never import into other users by default."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'index.html';s=p.read_text()
runtime=(ROOT/'tools/toeic9_pack_runtime.js').read_text()
block='// BEGIN TOEIC9_PACK\n'+runtime+'\n// END TOEIC9_PACK\n'
if '// BEGIN TOEIC9_PACK' in s:
    s,n=re.subn(r'// BEGIN TOEIC9_PACK\n.*?// END TOEIC9_PACK\n',lambda _:block,s,flags=re.S);assert n==1
else:s=s.replace('async function initCloud(){',block+'async function initCloud(){',1)
if 'id="toeic9PackPanel"' not in s:
    html='<div id="toeic9PackPanel" class="panel" hidden><h2>公式問題集9 · 画像付き145語</h2><p>今回の記録した意味を①として優先し、「公式問題集9」タグで追加します。既存の英語カードのタグは変更しません。対応する同じ語があれば履歴を引き継ぎます。</p><p id="toeic9PackStatus" role="status"></p><button id="toeic9PackStudy" class="primary" hidden>「公式問題集9」を学習する</button><button id="toeic9PackBackup">追加前のデータをJSONで保存</button></div>'
    s=s.replace('<section id="data" hidden>','<section id="data" hidden>'+html,1)
if 'initCloud().then(installRequestedToeic9Pack);' not in s:
    s=s.replace('\ninitCloud();','\ninitCloud().then(installRequestedToeic9Pack);',1)
anchor="cloudMessage('自動同期を開始しています。');await syncCloud(true);"
if anchor+'await installRequestedToeic9Pack();' not in s:
    assert s.count(anchor)==1;s=s.replace(anchor,anchor+'await installRequestedToeic9Pack();',1)
assert 'id="toeic9PackPanel"' in s
p.write_text(s)
print('Installed explicit-link importer. Normal page loads do not import or retag anything.')
