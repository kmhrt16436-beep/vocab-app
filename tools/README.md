# 熱・空気の図解を再生成する

アプリは従来どおり外部ライブラリなしで動作します。以下は開発時だけ使う作図用スクリプトです。

必要環境：Python 3、NumPy、Matplotlib、Noto Sans CJK JP（Debian系では `fonts-noto-cjk`）。

```sh
MPLCONFIGDIR=/tmp/heat-air-mpl python tools/render_heat_air.py
python tools/update_heat_air_images.py
python tests/test_heat_air_images.py
```

- `render_heat_air.py`：授業図をもとにした53種類の断面・配置・気流・科学グラフを描きます。テキスト同士、テキストと矢印・描画線の衝突、およびキャンバスからのはみ出しを描画後の座標で検査します。検出時は非ゼロ終了します。結果は `diagrams-v2/layout-report.json` に保存します。図は目視でも確認してください。
- `update_heat_air_images.py`：298枚のカードの⑥のみを差し替え、16種類のCSV、画像一覧、旧URLの互換画像、旧画像から新画像への対応表を更新します。表面・①〜⑤は書き換えません。対応表を保持して再実行できます。
- `test_heat_air_images.py`：Playwright＋Chromiumを使用し、旧298枚と先行5枚の画像更新、独自画像・独自の問題文の保護、通信失敗からの再試行、通信中の編集・復習、クラウドの自動保存、学習履歴の保持を検証します。

根拠のページと公開参考資料は [図解一覧](../study/heat-air/complete/diagrams.html) に記載しています。元の授業PDF・過去問写真・個人情報はリポジトリに含めません。
