# Azure同期API（移行準備版）

現行のSupabaseメールログインを継続し、カード・画像・学習進捗の保存先をAzureへ移すためのAPIです。公開アプリの `AZURE_STORAGE_CONFIG.enabled` は **false** のままです。配置や検証前に保存先は切り替わりません。

## 配置ZIPの権限修正

旧配置スクリプトは秘密情報用の `umask 077` をコードのZIPにも引き継ぎ、Flex Consumptionで必要な読み取り権限を満たしていませんでした。`package.py` は送信対象の公開コードだけを644、フォルダを755としてZIPへ格納します。接続キーを含む一時ファイルの600は維持し、ZIPに含めません。

すでに `flashcards-api-97c87b4b3a` を作成済みの場合は、修正版コミットの `redeploy.sh` をCloud Shellで実行すると、既存リソースと接続設定を使ってコードだけを再配置できます。キーの再入力・リソースの新規作成・データの削除・公開アプリの保存先変更は行いません。

```bash
export FLASH_SOURCE_REF=COMMIT_SHA
curl -fsSL "https://raw.githubusercontent.com/kmhrt16436-beep/vocab-app/$FLASH_SOURCE_REF/azure-sync/redeploy.sh" -o redeploy-azure.sh
bash redeploy-azure.sh
```

ホスト名はAzure Resource Managerの `properties.defaultHostName` から取得します。CLIの配置処理が終わっただけでは成功とせず、`check-health.py` がAPIのHTTP 200・`ready: true`・サービス名を確認します。503が続く場合は失敗として停止します。

## 今あるリソース

- サブスクリプション：Azure for Students
- リソースグループ：`flash-cards-rg`
- Cosmos DB for NoSQL：`flashcards-16436`（Japan East、Free Tier有効）
- データベース：`flashcards`
- コンテナー：`user-data`、パーティションキー `/userId`、手動400 RU/s

## ブラウザからの接続許可

Azureのホスト側がOPTIONSリクエストを処理するため、API内の許可だけでなく、Function AppのCORSにも `https://kmhrt16436-beep.github.io` を登録します。配置スクリプトはこの設定を行います。既存リソースでは次のコマンドだけでも反映できます。

```bash
az functionapp cors add --resource-group flash-cards-rg --name flashcards-api-97c87b4b3a --allowed-origins https://kmhrt16436-beep.github.io
```

実Azure上で、Origin・Access-Control-Request-Method・Access-Control-Request-Headersを付けたOPTIONS応答に、許可するOriginとメソッド・ヘッダーが含まれることを確認してからブラウザで移行を試します。`/api/health` の成功だけではブラウザ側のCORS設定の完了までは分かりません。

## 保存と認証の仕組み

- Azure Functions Node.js 22 / Flex ConsumptionがAPIを提供します。
- ブラウザは既存のSupabase access tokenをBearerで送信します。APIが**固定された自分のSupabaseプロジェクト**の `/auth/v1/user` へ問い合わせて本人を検証します。検証成功は最長60秒だけメモリに保持し、有効期限を越えてキャッシュしません。
- ユーザーIDは本人確認の結果からのみ決定します。URLやJSONに別人のIDを書いても他人のパーティションにはアクセスしません。CORSは追加の制限であり、認証の代わりではありません。
- 非公開Blobコンテナー `flashcards-private` に圧縮したJSONと画像を保存します。画像はユーザー内でハッシュによって重複排除します。画像の中身・解像度は変えません。画像をURLとして一般公開しません。
- Cosmosには各ユーザーの最新版番号・非公開Blob名・チェックサムだけを保存します。Cosmosの1項目2MB制限を画像入りJSONが超えない設計です。
- 画像→新しいJSON→Cosmosの版番号の順に保存します。版番号の一致確認はCosmosのETagによる条件付き更新です。競合時は409を返し、既存の3方向マージが再試行します。保存完了が不明な場合はファイルを削除しません。
- 古いJSONは最低24時間保持し、毎日UTC03:17に最新版以外を削除します。**直接アップロードした画像は、カードから削除されてもBlob内では保持します**。画像の自動削除とアカウント全体の削除UIはこの版には含めません。公開サービスとして販売する前に、画像の保管期限・アカウント削除処理を追加してください。
- 画像を含む1回の保存JSON上限は90MiBです。超えた場合は未同期として端末データを残します。大量データでは通信時間とメモリ使用量が増えます。
- 10秒の保存まとめ・60秒の版番号確認・即時の端末保存・IndexedDBの画像・JSONバックアップは継続します。画像はBlob内で重複排除しますが、端末間通信では現行方式と同じく完全なJSONを転送します。

## 配置する手順

このリポジトリには秘密鍵を入れません。配置は**ユーザー本人がログインしたAzure Cloud Shell（Bash）**から行います。

1. コードとテストを確認してGitHubへ保存したコミットの40桁SHAを用意します。
2. 次のように配置スクリプトをそのコミットからダウンロードします。`COMMIT_SHA` を実際のSHAへ置き換えます。

```bash
curl -fsSL https://raw.githubusercontent.com/kmhrt16436-beep/vocab-app/COMMIT_SHA/azure-sync/deploy.sh -o deploy-azure.sh
FLASH_SOURCE_REF=COMMIT_SHA bash deploy-azure.sh
```

3. `Supabase Publishable key` を聞かれたら、アプリで使っている**公開キー**を貼り付けてEnterを押します。入力は画面に表示されません。`sb_secret_...` や `service_role` キーは使用しません。
4. スクリプトは既存のFree Tierとコンテナーを確認し、Japan EastでFlex Consumptionが利用可能か確認します。利用できなければ停止します。EUAPや有料の別プランへ自動変更しません。
5. 非公開Standard LRSストレージとFunctionsを作り、接続情報をサーバーのアプリ設定へ登録し、固定コミットからコードを配置します。名前はサブスクリプションIDのハッシュから決め、再実行してもリソースが増えないようにします。Application Insightsは作りません。Always Readyは設定しません。
6. 最後に `https://...azurewebsites.net/api/health` への接続確認が実行されます。`ready: true` はAPIからBlob/Cosmosへ接続できたことを示します。メール認証・ユーザーデータの移行・端末間同期が成功したことまでは示しません。

Azure認証情報をChatGPTへ貼り付ける必要はありません。スクリプトがAzure CLI経由で取得し、保護された一時ファイルからサーバー設定へ登録します。一時ファイルは終了時に削除します。

### 料金

Cosmosの手動400 RU/sは確認済みのFree Tier内です。**Blob Storage・Functions等がすべて無期限無料になるという意味ではありません。** ストレージ容量・操作・実行・通信は該当サービスの料金と学生クレジットの対象です。API利用開始後はAzureのコスト管理で実測してください。Supabase認証を残すため、SupabaseのCPU警告が完全に消えることも保証しません。

## 公開アプリを切り替える前の検証

1. PCとスマホを同期済みにしてJSONバックアップを保存し、切り替え作業中は古いアプリからの編集・学習を止めます。
2. 公開アプリを変更する前に、ローカルのテスト用コピーの `AZURE_STORAGE_CONFIG` だけを変更して既存のGitHub Pagesのoriginから検証するか、別のテスト用originを明示してAPIの `ALLOWED_ORIGINS` に追加して検証します。localhostのテストは本番のCORS設定のままでは許可されません。
3. 本人の既存のログインでGETが成功することを確認します。Azureにそのアカウントの記録がない場合だけ、同じ本人のBearerトークンと公開キーでSupabaseのRLS保護テーブルを読み、旧データを一度コピーします。旧保存先に接続できない場合は空と見なさず停止します。元データは変更しません。
4. カード数・フォルダ・タグ・画像・復習履歴をバックアップと照合します。PC追加→スマホ表示、スマホ判定→PC反映、競合・オフライン復帰、別アカウントから閲覧不可を確認します。
5. 検証後に公開 `index.html` の `AZURE_STORAGE_CONFIG` を次のように有効化します。

```js
const AZURE_STORAGE_CONFIG={
  enabled:true,
  authUrl:'https://glpnosfxkewlqzpqnsep.supabase.co',
  dataUrl:'https://実際のFunctionsホスト名.azurewebsites.net/api'
};
```

6. PCとスマホの**両方で再読み込み**し、「データ」のアカウント表示が `保存先：Azure` となり、「同期済み」であることを確認します。未更新の古いアプリは引き続きSupabaseへ書きます。初回コピー後の古い端末によるSupabaseへの更新は自動で再コピーされないため、全端末を更新するまで併用しないでください。

保存先ごとに版番号を分けます。移行時は旧Supabaseのマージ基準を引き継いで、他の端末で消したカードを復活させにくくします。Azureを一度使った端末は保存先を記憶し、古いHTMLや通信障害を理由にSupabaseへ自動で戻りません。API障害時は「未同期」として端末保存を継続します。

## 停止・復旧

- API停止時は端末JSONを退避します。保存先だけを戻しても、Azure側で追加したカード・判定はSupabaseへ自動反映されません。
- 切り戻す場合は全端末の操作を止め、Azureの最新JSONをバックアップし、整合性を確認してから旧保存先へ復元します。その後に公開設定と各端末の保存先記憶を切り替えます。公開フラグをfalseにするだけで既存端末を勝手に戻す機能はありません。
- Supabaseはログイン・トークン更新に使うため、移行後もプロジェクトを削除しません。
- 全ユーザーの移行が済んでから `BOOTSTRAP_FROM_SUPABASE` をfalseにできます。それまでは未移行ユーザーの初回コピーに旧テーブルが必要です。

## ローカル検証

```bash
cd azure-sync
npm ci --ignore-scripts
npm test
```

`test/sync.test.js` は偽ストレージを使って認証・別アカウント分離・条件付き更新・大きい画像の保存・チェックサム・移行競合・通信応答消失・古いJSONの整理を検証します。`tests/test_azure_sync.py` はPlaywrightでブラウザ側の保存先変更と画像、旧版番号の分離、削除のマージ、トークン更新、未同期の再送を確認します。実Azure環境での配置と実データの移行は、これらのローカル検証とは別に必要です。

公式資料：[Flex Consumptionの配置](https://learn.microsoft.com/azure/azure-functions/flex-consumption-how-to)、[Cosmos Free Tier](https://learn.microsoft.com/azure/cosmos-db/free-tier)。
