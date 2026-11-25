// Opt-in installation: only an explicit ?pack=toeic9-part7 link imports this set.
let requestedPackBusy=false;
const TOEIC9_PACK_ID='toeic9-part7-v1',TOEIC9_PACK_TAG='公式問題集9';
function packPanelMessage(message,error=false){
 $('toeic9PackPanel').hidden=false;$('toeic9PackStatus').textContent=message;$('toeic9PackStatus').setAttribute('role',error?'alert':'status');
}
function packNoteUnion(...values){return [...new Set(values.flatMap(v=>v.split(/\r?\n|／/)).map(v=>v.trim()).filter(Boolean))].join('／')}
function validateToeic9Pack(pack){
 if(pack?.version!==1||pack.id!==TOEIC9_PACK_ID||pack.tag!==TOEIC9_PACK_TAG||pack.count!==145||!Array.isArray(pack.cards)||pack.cards.length!==145)throw Error('追加セットの形式が正しくありません。');
 const ids=new Set(),words=new Set();
 for(const [i,row] of pack.cards.entries()){
  if(row.id!=='toeic9-part7-'+String(i+1).padStart(3,'0')||ids.has(row.id)||!Array.isArray(row.fields)||row.fields.length!==7||row.fields.some(v=>typeof v!=='string')||!row.fields[0].trim()||!row.fields[1].trim()||words.has(row.fields[0]))throw Error('カードの形式が正しくありません。');
  if(!/^https:\/\/kmhrt16436-beep\.github\.io\/vocab-app\/study\/english\/toeic9-part7\/images\/sheet-\d{2}\.svg#card-[1-4]$/.test(row.fields[6]))throw Error('画像の形式が正しくありません。');
  ids.add(row.id);words.add(row.fields[0]);
 }
 return pack;
}
function combineToeic9Pack(input,pack,targetFolder){
 validateToeic9Pack(pack);const next=validate(JSON.parse(JSON.stringify(input))),folder=next.folders.find(f=>f.id===targetFolder&&!f.deleted&&f.kind==='vocabulary');
 if(!folder)throw Error('追加先の英単語フォルダがありません。');let added=0,updated=0,kept=0;
 for(const row of pack.cards){
  let existing=next.cards.find(c=>c.id===row.id||c.mergedIds.includes(row.id));
  if(!existing)existing=next.cards.filter(c=>next.folders.find(f=>f.id===c.folderId)?.kind==='vocabulary'&&c.fields[0].normalize('NFKC').trim().toLowerCase()===row.fields[0].normalize('NFKC').trim().toLowerCase()).sort((a,b)=>Number(b.folderId===folder.id)-Number(a.folderId===folder.id)||b.memory.reviews-a.memory.reviews||a.id.localeCompare(b.id))[0];
  if(existing){
   if(existing.id!==row.id)existing.mergedIds=validateStringSet([...existing.mergedIds,row.id],'統合元ID');
   existing.tags=validateTags([...existing.tags,TOEIC9_PACK_TAG]);if(existing.folderId!==folder.id)existing.sharedFolderIds=validateStringSet([...existing.sharedFolderIds,folder.id],'共有フォルダ');
   if(existing.tagPresets.includes(TOEIC9_PACK_ID)){kept++;continue}
   const old=[...existing.fields],customImage=CARD_IMAGE_REF.test(old[6])||CARD_IMAGE_DATA.test(old[6]);
   existing.fields=[...row.fields];existing.fields[2]=packNoteUnion(row.fields[2],old[1]===row.fields[1]?'':old[1],old[2]);existing.fields[3]=packNoteUnion(row.fields[3],old[3]);if(customImage)existing.fields[6]=old[6];
   existing.tagPresets=validateStringSet([...existing.tagPresets,TOEIC9_PACK_ID],'セットの適用履歴');updated++;
  }else{
   const c=card([...row.fields],folder.id);c.id=row.id;c.tags=[TOEIC9_PACK_TAG];c.tagPresets=[TOEIC9_PACK_ID];next.cards.push(c);next.session.queue.push({id:c.id,retry:false});added++;
  }
 }
 return {state:validate(next),added,updated,kept};
}
async function installRequestedToeic9Pack(){
 if(new URLSearchParams(location.search).get('organize')==='shinsoku-listening')return organizeShinsokuListening();
 if(new URLSearchParams(location.search).get('pack')!=='toeic9-part7'||requestedPackBusy)return;
 tab('data');
 if(storageBlocked){packPanelMessage('保存データを読み込めていないため追加を停止しました。元のデータを復元してから再度開いてください。',true);return}
 if(localStorage.getItem(AUTH_KEY)&&(!cloudAuth?.user?.id||!cloudReady||!cloudBase)){
  packPanelMessage('ログインと同期が完了すると「公式問題集9」を追加します。接続状態を確認してください。');return;
 }
 if(cloudBusy){setTimeout(installRequestedToeic9Pack,1200);return}
 requestedPackBusy=true;const owner=activeStorageKey,epoch=cloudEpoch;packPanelMessage('「公式問題集9」145語の画像付きカードを読み込んでいます。');tab('data');
 try{
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);let pack;
  try{const response=await fetch('./study/english/toeic9-part7/cards.json',{cache:'no-cache',signal:controller.signal});if(!response.ok)throw Error('追加セットを取得できませんでした。');pack=validateToeic9Pack(await response.json())}finally{clearTimeout(timeout)}
  if(owner!==activeStorageKey||epoch!==cloudEpoch)throw Error('アカウントが変わったため追加を停止しました。追加用リンクを開き直してください。');
  syncDay();const target=state.folders.find(f=>f.id===activeFolder&&!f.deleted&&f.kind==='vocabulary')||state.folders.find(f=>f.id===DEFAULT_FOLDER&&!f.deleted&&f.kind==='vocabulary')||state.folders.find(f=>!f.deleted&&f.kind==='vocabulary');if(!target)throw Error('英単語フォルダを作成してから追加してください。');
  const before=JSON.stringify(state),backup=owner+':before-pack:'+TOEIC9_PACK_ID;if(!localStorage.getItem(backup))localStorage.setItem(backup,before);
  const result=combineToeic9Pack(state,pack,target.id);localStorage.setItem(owner,JSON.stringify(result.state));state=result.state;activeFolder=target.id;activeTag=TOEIC9_PACK_TAG;localStorage.setItem(FOLDER_VIEW_KEY,activeFolder);localStorage.setItem(TAG_VIEW_KEY,activeTag);revealed=false;orderStudyQueue();persist();render();
  const url=new URL(location.href);url.searchParams.delete('pack');history.replaceState(null,'',url.pathname+url.search+url.hash);
  packPanelMessage(`「公式問題集9」に追加しました。新規${result.added}枚・既存カードを更新${result.updated}枚・登録済み${result.kept}枚。元のタグと復習履歴は引き継いでいます。`);
  $('toeic9PackStudy').hidden=false;if(cloudReady)await syncCloud();
 }catch(e){packPanelMessage('追加できませんでした：'+e.message+' 接続後、このリンクを開き直すと再試行できます。',true)}
 finally{requestedPackBusy=false}
}
$('toeic9PackStudy').onclick=()=>tab('study');
$('toeic9PackBackup').onclick=async()=>{const value=localStorage.getItem(activeStorageKey+':before-pack:'+TOEIC9_PACK_ID);if(!value){packPanelMessage('この端末には追加前のバックアップがありません。',true);return}try{const payload=await exportCardImages(JSON.parse(value),activeStorageKey),blob=new Blob([JSON.stringify(payload)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='before-toeic9-part7.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){packPanelMessage('バックアップを保存できません：'+e.message,true)}};
window.addEventListener('online',installRequestedToeic9Pack);

let shinsokuBusy=false;
function classifyShinsokuListening(input){
 const next=JSON.parse(JSON.stringify(input)),vocabulary=new Set(next.folders.filter(f=>!f.deleted&&f.kind==='vocabulary').map(f=>f.id));let total=0,added=0;
 for(const c of next.cards){
  const official=c.tags.includes(TOEIC9_PACK_TAG)||c.tagPresets.includes(TOEIC9_PACK_ID)||[c.id,...c.mergedIds].some(id=>/^toeic9-part7-\d{3}$/.test(id))||/^https:\/\/kmhrt16436-beep\.github\.io\/vocab-app\/study\/english\/toeic9-part7\/images\//.test(c.fields[6]);
  if(!vocabulary.has(c.folderId)||!belongsToFolder(c,DEFAULT_FOLDER)||official)continue;
  total++;if(!c.tags.includes('神速リスニング')){c.tags=validateTags([...c.tags,'神速リスニング']);added++}
 }
 return {state:next,total,added};
}
async function organizeShinsokuListening(){
 if(new URLSearchParams(location.search).get('organize')!=='shinsoku-listening'||shinsokuBusy)return;
 const panel=$('shinsokuPanel'),status=$('shinsokuStatus');panel.hidden=false;tab('data');
 if(storageBlocked){status.textContent='元の保存データを読み込めていないため、タグ付けを停止しました。';return}
 if(localStorage.getItem(AUTH_KEY)&&(!cloudAuth?.user?.id||!cloudReady||!cloudBase)){status.textContent='ログインと同期が完了するとタグを付けます。接続状態を確認してください。';return}
 if(cloudBusy){setTimeout(organizeShinsokuListening,1200);return}
 shinsokuBusy=true;
 try{
  const result=classifyShinsokuListening(state);localStorage.setItem(activeStorageKey,JSON.stringify(result.state));state=result.state;activeFolder=DEFAULT_FOLDER;activeTag='神速リスニング';localStorage.setItem(FOLDER_VIEW_KEY,activeFolder);localStorage.setItem(TAG_VIEW_KEY,activeTag);revealed=false;persist();render();
  const url=new URL(location.href);url.searchParams.delete('organize');history.replaceState(null,'',url.pathname+url.search+url.hash);
  status.textContent=`英語フォルダの対象${result.total}枚を「神速リスニング」にまとめました（新たにタグを追加${result.added}枚）。「公式問題集9」と他の教科、既存タグ、画像、復習履歴はそのままです。`;
  $('shinsokuStudy').hidden=result.total===0;if(cloudReady)await syncCloud();
 }catch(e){status.textContent='タグを付けられませんでした：'+e.message+' 接続後に整理用リンクを開き直してください。'}
 finally{shinsokuBusy=false}
}
$('shinsokuStudy').onclick=()=>tab('study');
