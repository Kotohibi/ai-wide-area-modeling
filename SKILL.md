---
name: ai-wide-area-modeling
description: 撮影データ（写真とカメラ姿勢、SfM / dense 点群、任意で LichtFeld Studio (LFS) の 3D Gaussian Splatting）を測りながら、広い範囲の実在シーン（街路・インフラ・寺社・ダムなど）を Blender MCP で軽量な形状モデルに起こす汎用の手順と道具。COLMAP 形式のカメラ姿勢・撮影写真・点群を参照する。LFS の MCP からのデータの取り方、座標系とスケールの決め方、写真・3DGS・Blender を同じ視点で並べた差分確認、撮影写真（cubemap の面など）と同じ姿勢・画角で最終レンダーを描いて差分を原因まで掘り生成スクリプトを直す仕上げの往復（ブラッシュアップ）、点群とモデルの 3D 距離の確認、細い物の三角測量、できたモデルの Unreal Engine への移行（UE MCP、材質・植物・歩行）と、Three.js でブラウザに公開する手順（glb 書き出し、式で描く材質、別案の切り替え、スマホ対応）を含む。屋外の街並み・インフラ・建物・室内・物体など、シーンの種類を問わない。ユーザーが「3DGS をモデリング」「LFS の視点から Blender で作って」「ガウシアンスプラットからメッシュ／CAD 風モデルに」「COLMAP / SfM の結果を Blender に」「点群からモデルを起こして」「モデルと 3DGS（写真）のずれを確認して」「写真と同じ視点でレンダリングして比較して」「比較してずれを直して」「Blender のモデルを UE に持っていって」「Three.js / ブラウザで見られるようにして」などと言ったら、3DGS・COLMAP・Blender・LichtFeld のいずれかが話に出ている限り、明示されなくてもこのスキルを使うこと。
---

# AI Wide Area Modeling（撮影データ → Blender モデリング）

写真・点群・3DGS といった撮影データから、広い範囲の実在シーンを AI エージェントが Blender でモデリングするためのスキルです。LichtFeld Studio（3DGS）は任意で、COLMAP 形式のカメラ姿勢と点群だけでも使えます（`setup_project.py --no-lfs`）。

**3DGS で全体像をつかみ、SfM 点群で寸法を取り、撮影写真で確定する。** 3DGS はフローターが多く、撮影位置から離れると崩れ、縮尺も不定です。写真とその姿勢は、どの視点で見ても正しい唯一のデータなので、判断に迷ったら写真を見ます。各データの得手不得手と、実例で踏んだ失敗は [references/knowledge.md](references/knowledge.md) にあります。作業を始める前に一度読んでください。

## 道具（`scripts/`）
Python は numpy と Pillow を使います（環境の落とし穴は knowledge.md の末尾）。`P.json` は `setup_project.py` が作る `project.json` です。

| スクリプト | 役割 |
|---|---|
| `lfs_mcp.py` / `lfs_mcp.ps1` | LFS の MCP を直接呼ぶ（`python lfs_mcp.py tools`、`call <tool> k=v`、`image out.png render_capture camera_index=12`） |
| `colmap_io.py` | COLMAP（txt / bin / ply）の読み込み、投影、画素からの光線 |
| `setup_project.py` | `project.json` を作る: LFS と COLMAP の対応、上方向、モデル座標系、スケール |
| `project.py` | 座標変換（world ↔ raw ↔ model）、写真のカメラを Blender 用に |
| `export_points.py` | SfM 点群・フィルタした 3DGS をモデル座標（m）で書き出す |
| `plot_points.py` | 点群の上面・正面・側面の画像（1 m グリッド付き）。断面にすると寸法が読める |
| `views.py` | 写真の選択（ある点が写っている写真）、LFS での同視点レンダリング、LFS ビューポートの取得・移動・復元 |
| `pick_views.py` | ある点を画面中央に写した写真を、距離帯と方位を散らして選ぶ（＋一覧画像）。建物の外観を 4 方向から見るとき。`views.py select --near` は近い順なので、建物の真下の写真ばかりになる |
| `pick3d.py` | 写真上の画素から 3D 位置（三角測量か平面との交点）、2 点間の距離 |
| `vray.py` | `views.py viewport` で作ったビューセット（LFS のキャプチャ）の画素から 3D 位置。学習写真が無い視点・撮影経路の外の物（奥の建物）を測る |
| `gridcrop.py` | 画像の一部を、元の画素座標の目盛り付きで切り出す（画素を読むため） |
| `photo_ortho.py` | 写真の真上画像（地面の格子の各セルを、それが写っている一番近い写真の色で塗る）。石畳・砂利・芝・縁石の境を読む。点の色は撮影時の影に覆われて読めないことがある |
| `set_sheet.py` | ビューセットの画像を、視点の位置付きで一覧にする |
| `compare_sheet.py` | 写真｜3DGS｜Blender｜重ねの 4 列比較と、輪郭の一致率 |
| `cmp_select.py` / `cmp_set.py` | 仕上げの差分比較の準備: 確認したい物ごとに、よく写っている学習写真（cubemap の面）を候補一覧にし、選んだ写真をそのまま複製して姿勢・内部パラメーターを `cameras.json` に書く |
| `blender/bl_cmp_render.py` | 選んだ写真と同じ姿勢・画角・解像度で、最終の材質と光のまま Cycles で描き、写真の横に `NN_<名前>_blender.png` を置く |
| `blender/bl_cmp_probe.py` | 比較画像の画素に、モデルの何（物体・材質・3D 位置・距離）が写っているかを調べる。ずれの原因の特定に使う |
| `cmp_review.py` | 写真｜Blender｜輪郭の重ね、修正前後の並び（`keep` で版を残す）、原寸の切り出し（画素の目盛り付き）、同じ枠の平均色（`patch`） |
| `blender/bl_views.py` | 写真と同じ姿勢・画角での Blender レンダリング、確認用カメラの作成 |
| `blender/bl_point_diff.py` | モデルと点群の 3D 距離（系統的なずれ、作り忘れ、根拠の無い形） |
| `ue_mcp.py` / `blender/bl_export_groups.py` | Unreal Engine への移行の入口（UE MCP を HTTP で直接呼ぶ、まとまりごとの FBX と `export_manifest.json` の書き出し）。手順・単位と軸・ツールの癖は [references/unreal.md](references/unreal.md) |
| `unreal/ue_port.py` | UE: 材質（マテリアルの色から）・取り込み（Nanite・当たり判定）・レベル・配置・Third Person で歩く設定。設定は JSON 1 つ |
| `unreal/ue_surfaces.py` | UE: UV の無いメッシュの材質（ワールド座標の手続き的マテリアル、Poly Haven のテクスチャの三面投影） |
| `unreal/ue_vegetation.py` | UE: 植物アセット（Megaplants など）の寸法を測り、測った位置・高さ・樹冠の径で木と生垣を置く |
| `unreal/ue_py.py` | UE 5.9 以降: エディタの中の Python を実行する（`run(code)` / `call(toolset, tool, args)`）。以下の 5.9 用の道具の土台 |
| `unreal/ue_viewport_cap.py` | UE 5.9: 比較写真と同じ姿勢・画角（`cameras.json`）や任意の視点で、ライブのビューポートから撮る（Lumen が入った絵になる） |
| `unreal/ue_walk_check.py` | UE 5.9: PIE のキャラクターを戸口ごとに実際に歩かせ、通れるかを判定する |
| `unreal/ue_niagara_fall.py` | UE 5.9: 花びら・落ち葉・雪など、ゆっくり落ちる粒の Niagara システムを作って置く（量・風・乱流は JSON） |
| `blender/bl_camera_json.py` / `unreal/ue_camera_seq.py` | カメラワークを Blender から UE へ: コマごとの位置と注視点の JSON → Level Sequence → Movie Render Queue で連番 |
| `frames_check.py` | 連番（Blender・UE）の欠け・単色のコマ（めり込み）・飛びの検査と一覧画像 |
| `threejs/shader_check.html` | Three.js: 材質を 1 つずつ描き、ブラウザのシェーダーコンパイラ（Windows の D3D）が落ちる材質を探す。使い方は [references/threejs.md](references/threejs.md) |
| `blender/bl_bake_queue.py` | Blender MCP の制限時間を超える処理を、Blender の中のタイマーで順に実行する |
| `blender/bl_coplanar.py` | Z ファイティングの候補（同じ向きで同じ平面に重なる面）を全メッシュから探す。生成スクリプトを直したら毎回かける |

Blender のスクリプトは共有フォルダに置き、`exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())` で実行します。設定は実行前に dict（`VIEWCFG`、`PDIFF`）で渡し、結果は `result` に入ります。

## 手順

### 0. 接続と作業場所
1. LFS の MCP に届くか確認します（`python lfs_mcp.py tools`）。届かなければ、LFS が起動しているか、MCP が有効かをユーザーに確認します。
2. Blender の MCP で `render_viewport_to_path` を一度呼びます。返るパスの `...\blender_mcp\` が、Blender と双方から見える共有フォルダです。`scripts/blender/*.py` をそこへコピーします。
3. 作業フォルダ（プロジェクトフォルダ）を決めます。中間データは数百 MB〜数 GB になることがあります。
4. **作業前に LFS の視点を控えます**（`setup_project.py` が `viewport_at_setup` に保存）。ユーザーの視点なので、`views.py look/goto` で動かした後は `views.py P.json restore` で戻します。

### 1. プロジェクトの設定
```
python setup_project.py <project_dir> --shared <共有フォルダ> [--scale m/unit | --cam-height-m 1.6] [--up auto] [--ref viewport]
```
- LFS の `camera_list` から、学習カメラ（uid、姿勢、写真のパス）と SfM フォルダを見つけます。splat ノードのワールド行列 `M` も取ります（`raw = M @ world`）。
- **LFS のカメラ位置と COLMAP のカメラ中心が一致するかを検査します。** 一致しなければ、LFS が読み込み時にデータを変換しているので、先へ進まずに調べます。
- 上方向は、カメラの上方向の平均を事前値とし、カメラより下の点の平面（床・地面・台）で補正します。結果を確認します: 地面の傾き、カメラ高（単位）、モデル座標でのカメラの範囲。
- モデル座標系は、メートル・Z 上・原点がユーザーの視点に最も近い学習カメラの真下の地面・+Y がその視点の水平方向です。**以降はすべてこの座標で考え、Blender にもこの座標のまま作ります。**
- スケールは、指定が無ければ「カメラ高 1.6 m」という仮定です。手順 3 で既知の寸法を測って確かめ、必要なら `--rescale` で直します。
- 詳細（LFS で取れるもの・取れないもの、座標系の注意）は [references/lfs_mcp.md](references/lfs_mcp.md) にあります。

### 2. シーンを把握して、作る物を決める
- ユーザーの LFS 視点を `views.py viewport` で取り、そのキャプチャを見ます。ユーザーが見ている物が最優先です。
- `export_points.py P.json sfm` → `plot_points.py ... --view top --cams` で、全体の平面図と撮影経路を見ます。壁・柱・縁が密度の線として見えます。
- 気になる場所は `views.py find x,y,z --out sheet.png` で、その場所が写っている写真を切り出して見ます。
- **配置を見渡すときは、LFS を上空から見ない**（地上撮影の 3DGS は上から見るとぼやけて使えない）。地上の高さ（1.5〜3 m）のまま、撮影経路に沿って前後に、また左右に数 m ずらした視点を `views.py look` で作り、`views.py viewport <set>` でキャプチャをビューセットに貯めます。学習カメラの間の視点でもきれいに描けるので、奥の建物（撮影経路の終点の先）や配置の全体がよく分かります。そのセットは、そのまま 4 列比較（`bl_views.py` → `compare_sheet.py`）と `vray.py` の三角測量に使えます。木の幹や葉の近くの視点はフローターで崩れるので、間が空いている所を選びます。
- 舗装・砂利・芝の区画の配置は、点の色ではなく `photo_ortho.py` の写真の真上画像で読みます（点の色は影に覆われることがある）。
- 作る物の一覧（部位・優先度・詳細度）を決めて、ユーザーと合わせます。フローターの多い所、撮影範囲の外、作らなくてよい物（車・人・植栽など）も確認します。
- **レシピは、対象の種類が同じときだけ読みます。** レシピは実例の記録で、対象を限定する物ではありません。レシピが無い種類（室内、物体、工場、洋風の建物など）は、この手順と `references/` だけで作ります。
  - 読んだレシピから使うのは、**測り方と失敗例**です。寸法・比率・形の規則（屋根の形、柱の割り付けなど）は、その現場の物なので流用しません。必ず目の前の写真と点群で測り直します。
  - レシピのスクリプトには実例の数値が入っています。そのまま実行せず、値を書き換えるか、作り方の参考にとどめます。
  - 種類が近いだけで様式が違うとき（例: 寺のレシピで教会を作る）は、読まない方が安全です。
  - 高架・道路・街路（経路に沿った長いシーン）: [recipes/viaduct_street/RECIPE.md](recipes/viaduct_street/RECIPE.md)
  - 寺社の門・境内・木造の伝統建築（楼門、本堂の流れ向拝、鐘楼、庫裏、入母屋屋根、組物、生垣・木）: [recipes/temple_gate/RECIPE.md](recipes/temple_gate/RECIPE.md)
  - ダム・洪水吐・減勢池・ダム湖と川・山地の地形（ドローン撮影、国土地理院 DEM との当てはめ、UE の水と森）: [recipes/dam_spillway/RECIPE.md](recipes/dam_spillway/RECIPE.md)
  - 木造校舎など、室内に入れる木造の建物（柱間ごとの壁、現況の廃墟と想像の復元の 2 状態、UE 版、Three.js 版の切り替え・花びら・BGM）: [recipes/wooden_school/RECIPE.md](recipes/wooden_school/RECIPE.md)

### 3. 測る
- **寸法と位置は、SfM 点群の断面で読みます**（`plot_points.py --box=...` で薄い板を切る。床から 1 m の高さの平面図、柱を通る縦断面など）。3DGS の点（`export_points.py 3dgs`）は密ですが、フローターが混ざります。
- 細い物、点群に無い物、向きは写真で決めます。`pick3d.py` で画素から 3D 位置を出します（2 枚以上なら三角測量。同じリグの同じフレームのビュー同士では奥行きが出ない）。
- **スケールを確かめます。** 既知の寸法（ドア、天井高、階段、車線、横断歩道、車など。表は knowledge.md）の両端を `pick3d.py` で測ります。複数の手掛かりで整合する値を採り、`setup_project.py <dir> --rescale <m/unit> "<根拠>"` で直します。モデルを作り始める前に決めておくと、後で全部を作り直さずに済みます。
- 測った値と根拠は、パラメータファイル（JSON）に残します。

### 4. Blender で作る
- **パラメータ（JSON）と生成スクリプトを分けます。** 生成スクリプトは「自分のコレクションを消して作り直す」ように書くと、値を直して何度でも再実行できます。コレクションは部位ごとに分けます。
- 大きい物から作ります（地面・床 → 主要な構造 → 建物・壁の箱 → 開口・段差 → 設備・細部）。規則的な物は規則で作ります（等間隔の柱、車線、窓の並び）。
- 向きのある物（標識・扉・窓・ベンチ）は、表と裏の色を変えます（比較で向きの誤りがすぐ分かる）。
- 物理的に成り立つかを最後に確かめます。支える面の上にあるか、めり込んでいないか、撮影者が通った場所（カメラ位置）が空いているか。点群からの位置は数十 cm ずれるので、規則で寄せる処理を入れます。
- 写真のテクスチャを貼って形の代わりにしません。写真は位置を読む下絵として使います（ユーザーが求めない限り）。
- 作業用のスクリプトは、案件のフォルダに置きます。汎用的に使える物ができたら、このスキルの `scripts/` かレシピに加えます。

### 5. 差分を確認する（毎回必ず。数字ではなく絵で合わせる）
詳しくは [references/verification.md](references/verification.md) を読みます。
```
python views.py P.json select <set> --near x,y,z --n 6         # その場所が写っている写真（向きを散らす）
python views.py P.json lfs <set>                                # 同じ学習カメラで 3DGS をレンダリング
(Blender) VIEWCFG = {"set": "<set>", "mode": "render", "width": 640}; exec bl_views.py
python compare_sheet.py P.json <set>                            # 写真｜3DGS｜Blender｜重ね
(Blender) PDIFF = {"points": "points_sfm.npy", "collections": [...], "tol": 0.15}; exec bl_point_diff.py
```
- 4 列比較で、欠け・余分・ずれ・向きを見ます。写真と 3DGS は画素単位で一致するので、3DGS が崩れている所は写真を信じます。
- 3D 距離で、系統的なずれ（物ごとの符号付き距離）、作り忘れ（`unmodelled_clusters`）、根拠の無い形（`supported` が低い）を洗い出します。
- ユーザーが LFS で視点を見せたら、`views.py viewport` でその視点を再現して並べます。
- 比較画像は、必ず自分で開いて見ます。直したら、同じ視点で再確認します。

#### 5b. 仕上げの差分比較（ブラッシュアップの往復）
形がおおむねでき、材質と光も入ったら、**写真と同じ視点・画角の最終レンダーを並べ、差分を 1 つずつ原因まで掘って直す**往復を回します。実例で、仕上げに最も効いたやり方です。詳細と判断の目安は [references/verification.md](references/verification.md) の「E」。
```
python cmp_select.py P.json targets.json --out <dir>\cands     # 物ごとに写りのよい写真の候補一覧 → 目で選ぶ
python cmp_set.py P.json chosen.json <dir>                      # 写真の複製と cameras.json
(Blender) CMPCFG={"dir": <dir>, "spp": 128}; exec bl_cmp_render.py   # 1 回 4 枚まで（MCP の制限時間）
python cmp_review.py <dir> sheets                               # 写真｜Blender｜輪郭の重ね
python cmp_review.py <dir> keep                                 # 直す前に今の版を _v1 に残す
(差分ごとに) cmp_review.py crop → bl_cmp_probe.py → 写真・点群で測る → 生成スクリプトを直す
python cmp_review.py <dir> patch <stem> x0 y0 x1 y1 <名前> ...  # 色・明るさは数字で合わせる
python cmp_review.py <dir> sheets                               # 修正前後の並びで、直ったか・他を壊していないかを見る
```
- 比較する物（標識・橋脚・縁石・桁下・遠景など）を 8〜12 か所に決め、それぞれ 1 枚選びます。真上向きの面（`_top`）は桁下・天井に、正面から写る面は標識の表に向きます。
- 差分は**表にしてユーザーに見せ**、直す順番を合わせます。直すのは生成スクリプトとパラメーターで、Blender 上の手直しはしません。
- 1 か所の修正（光の強さなど）は全部の視点に効くので、毎回全視点を描き直して、修正前後の並びで確かめます。

### 6. ユーザーとの往復
- 結果の画像（比較シート、ユーザーの視点、全体の俯瞰）をユーザーに送り、どこが違うかを聞きます。
- ユーザーの指摘は、たいてい一般的な規則（「二つの床版は高さが違う」「柱の根元は車道に置かない」）です。その場所だけ直さず、規則として生成スクリプトに入れます。**このスキルにも書き足します**（シーンに依存しない知識は knowledge.md、シーンの種類に固有の物はレシピ）。

### 7. ゲームエンジン・ブラウザへ移す（求められたら）
- Unreal Engine へは [references/unreal.md](references/unreal.md) の手順で移します（`bl_export_groups.py` → `unreal/ue_port.py` → `ue_surfaces.py` → `ue_vegetation.py`）。
- ブラウザで見せる（Three.js）場合は [references/threejs.md](references/threejs.md) を読みます（glb の書き出し、式で描く材質、葉のカード、SSAO、季節・BGM・言語の切り替え、別案（現状と復元など）の切り替えと左右比較、室内の明るさ、Windows のブラウザで落ちるシェーダーの書き方、読み込み画面、スマホ、公開フォルダの分け方）。
- UE 5.9 以降はツール名と単位の扱いが違います（`ue_mcp.py toolsets` に `PythonScriptingTools` があれば 5.9）。unreal.md の「UE 5.9 での違い」を先に読み、`unreal/ue_py.py` と 5.9 用の道具（撮影・歩行確認・Niagara・カメラワーク）を使います。
- 移す前に、Blender で面の向きと物体の変換を確かめます（UE は裏面を描かず、Blender は両面を描くので、裏返りに気づけない）。
- 材質に学習写真を焼き込まず、植物は Blender で作った物を使わずに、本物のアセットに置き換えます（どちらも実例での評価）。素材のダウンロードや、プロジェクト設定の変更・エディタの再起動は、了解を得てから行います。

### 8. 報告に必ず書くこと
- スケールは推定であること（根拠・手掛かり同士の食い違い・±誤差）。
- 部位ごとの確度（写真と合った所、粗い所、自動検出のままの所）、作っていない物。
- 確認に使った画像（比較シート・ユーザーの視点）。
- .blend を保存していない場合はその旨（保存先はユーザーに確認する）。

## 新しいシーンの種類のレシピを足すとき
`recipes/<種類>/RECIPE.md` に、そのシーンの部位の作り方、効いた測り方、間違えやすい所、実例の設定値を書きます。汎用の道具で済む所は道具を参照するだけにして、そのシーン特有の解析スクリプトだけを `recipes/<種類>/` に置きます。
