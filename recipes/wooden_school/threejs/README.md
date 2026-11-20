# Three.js 版（木造校舎: 廃墟と復元）

ブラウザで、廃墟と復元した校舎を切り替えて見るページです。フライスルー（Blender・UE と同じカメラ軌道）、自由視点、歩く、の 3 つの見方があります。

| フォルダ / ファイル | 中身 | Web サーバーに置く |
|---|---|---|
| `public/` | 公開する一式: `index.html`、`proc.js`（材質の式）、`materials.json`、`scene.json`、`ruin.glb`・`ruin_veg.glb`・`ruin.json`、`restored.glb`・`restored_veg.glb`・`restored.json`、BGM（`bgm_ruin.m4a`・`bgm_restored.m4a`・`bgm.json`） | **はい（このフォルダの中身だけ）** |
| `logs/` | Blender からの書き出しログ | いいえ |
| `export_web.py` | Blender から `public/` へ書き出す（背景実行） | いいえ |
| `make_bgm.py` | BGM の 2 曲を合成する（numpy と ffmpeg。`"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" web\make_bgm.py`。`balance` を付けると旋律と伴奏の音量差を出す） | いいえ |
| `make_materials.py` | `ue\ue_mats.py` の材質表から `materials.json` を作る | いいえ |
| `serve.ps1` | 手元で見るためのサーバー（http://127.0.0.1:8771） | いいえ |
| `shader_check.html` | 材質を 1 つずつ描いて、シェーダーのコンパイルで落ちる材質を探す確認ページ（`public/` にコピーして `http://名前.localhost:8771/shader_check.html` で開く） | いいえ |

- 手元で見る: `serve.ps1` を実行する（`file://` では glb / json を読めないため、サーバーが要る）。
- 公開: `public/` の 13 ファイルを、サーバーの同じフォルダにそのまま置く。three.js は jsDelivr（CDN）から読むので、ほかのファイルは要らない。
- 書き出し直し（モデルのフォルダで）:
  - `python web\make_materials.py`（材質の数値を変えたとき）
  - `blender -b ruin_school.blend -P web\export_web.py -- ruin`（約 30 秒）
  - `blender -b ruin_school_restored.blend -P web\export_web.py -- restored`（約 40 秒。戸を全部開けた状態でメモリ上に作り直す。.blend は保存しない）
- 切り替え: パネルの「廃墟 / 復元 / 比較」、またはキー 1 / 2 / 3。比較は画面を左右に分け、境界をドラッグできる。`index.html?v=restored` で復元から始まる。
- 画質: どの端末でも「高」で始まる。パネルの「画質」ボタンで 軽量 → 標準 → 高 と切り替わる（ページを読み込み直す）。`?q=low|mid|high` でも指定できる。
- 表示言語: ブラウザの優先言語が日本語なら日本語、それ以外は英語。パネル右上のボタン、または `?lang=ja` / `?lang=en`。
- 材質は画像を使わず、`blender\bl_mats.py` と同じ式をブラウザで画素ごとに計算している（写真の焼き込みは無い）。木は Blender の手続き的な木の葉を板（カード）にまとめたもの。
- 室内の明るさ: ブラウザには間接光が無いので、建物の平面の内側で空からの光を減らし、屋根の穴の下だけ明るくしている（近似）。太陽の光は窓と穴から影の計算で入る。室内に入ると露出が上がる。
- 「歩く」は床と地面の高さに沿うだけで、壁の当たり判定は無い。
- シェーダーを直したら `shader_check.html` で全部の材質が描けること（`ALL DRAWN`、`LOG` が無いこと）を確かめてから本体を開く。Windows のブラウザは、シェーダーのコンパイル失敗で WebGL を 2 回失うと、その接続元（origin）の WebGL を止める。
- 音量: 「♪ BGM」の横のスライダー（0〜100 %、既定 50 %。選んだ値はそのブラウザに保存）。スライダーの値を 2 乗して使うので、小さい音量ほど細かく調整できる。
- BGM: パネルの「♪ BGM」で鳴らす・止める（ブラウザは操作の後にしか音を出せない）。廃墟と復元は「同じ曲の 2 つの状態」で、長さと拍が同じ（72 BPM、16 小節、53.3 秒）。2 曲を同時に走らせて音量だけを切り替えるので、切り替えは同じ小節の中でのクロスフェードになり、比較表示では境界の位置に応じて 2 曲が混ざる。
