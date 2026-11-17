# 熱・空気の原図を切り出す

アプリは外部ライブラリなしで動作します。開発時の抽出には Python 3 と PyMuPDF を使用します。

```sh
python tools/extract_slide_crops.py --heat-pdf /path/to/熱1-7.pdf --air-pdf /path/to/空気8-13.pdf
python tools/update_heat_air_images.py
python tests/test_heat_air_images.py
```

- `slide_crops.json`：173箇所の資料名・PDFページ・正規化した切り出し範囲・対応カードID。298枚を重複なく割り当てています。
- `extract_slide_crops.py`：元PDFの指定範囲を直接PNGへレンダリングします。描き直し、文字・矢印の追加、合成はしません。`slide-crops/catalog.json` に寸法・座標・SHA256・元ページの出典表示を記録します。`boundary-review.json` は文字の端が欠ける候補の検出結果です。埋め込み画像中の文字は検出できないため、目視確認も必要です。
- `update_heat_air_images.py`：⑥だけを変更し、16種類のCSV・原図一覧・旧URLの互換画像・画像更新表を再生成します。表面・①〜⑤は変更しません。初期版・前回版の画像URLから移行できます。
- `tests/test_heat_air_images.py`：旧画像の更新、独自画像・独自問題文の保護、オフライン復帰、通信中の編集、クラウド自動保存、学習履歴保持を検証します。

元の授業PDF、過去問写真、氏名・学籍番号をリポジトリに含めないでください。原図の文字・矢印・記号は変更しません。これまでの作図スクリプトは旧版用で、現在の画像には使用しません。
