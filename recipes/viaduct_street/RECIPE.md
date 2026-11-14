# レシピ: 高架道路と街路

歩行者目線の 360° 撮影（6 ビュー／フレーム、7,206 枚、15M ガウシアン）から、二層の高架・門型橋脚・片側二車線の道路・歩道・横断歩道・信号・標識・街路灯・周辺建物・鉄塔・樹木を作った手順です。**経路に沿って長く伸びるシーン**（道路・鉄道・河川・トンネル・廊下）なら、同じ考え方が使えます。

## このレシピのスクリプトについて（先に読む）
- `analysis/`（Python）と `blender/`（Blender 内で exec）は、汎用ツール（`scripts/`）より前に書いたものです。座標は独自の **site → leveled フレーム**（3DGS 単位。Blender に入れるときに `S` 倍する）を使い、`project.json` のモデル座標系は使っていません。
- 先頭付近に案件固有の定数があります（`M`、基準カメラ位置、経路の距離 s の範囲 88〜448、SfM フォルダのパス、`S=1.15/1.6`）。流用するときは必ず書き換えます。
- 新しい案件では、可能な限り汎用ツール（`setup_project.py` のモデル座標系、`views.py`、`pick3d.py`、`compare_sheet.py`、`bl_point_diff.py`）を使います。経路展開（`unwrap.py`）や真上写真（`ortho_photo.py`）、`straighten.py` のような**このレシピ特有の解析だけ**を、ここから持っていきます。
- 実例の設定値は `examples_viaduct/` にあります（params_v3 / params_road / params_extras / params_markings / manual_buildings_spec / pole_review）。似た現場の出発点にはなりますが、値は案件ごとに測り直します。

## 1. 経路フレーム（経路沿いのシーンの基本）
- `analysis/prep2.py` → `ground.py`（**カメラより下の点だけ**で路面を RANSAC。上側の点を使うと高架の下面に吸われる）→ `basis.py` → `site.py` / `sparse.py`。
- `stations.py` → 軌跡と各地点の断面。`export_path.py` で経路を滑らかにし、`level.py` で経路の路面平面を水平にする（SfM は約 20° 傾いていた）。
- 経路の距離 s と横位置 lat（進行方向の右が +）で考えると、幅・オフセット・橋脚の間隔がすべて 1 次元の表になります。経路は 4 次多項式で平滑化したので、実際の撮影位置とは最大約 2 単位ずれます。

## 2. 高架
- `unwrap.py` → 経路に沿って展開した疎点群の地図（横＝s、縦＝lat）。`extract.py` で数値化、`heights.py` で桁と梁の高さの層（桁下高はこれが一番安定）。`unwrap_zoom.py` で区間を拡大。
- **床版の平面形は「下から見上げた写真の投影」で読む。** 疎点群は真上の面がほとんど点にならず、幅を過小評価します。
  - `ortho_photo.py <SP> 1 0.15 9 4.3 top underside` … 真上向きの写真を、桁下高の面に投影します。
  - `straighten.py <SP> underside <s0> <s1> -12 24 10 out.png` … 経路に沿ってまっすぐに伸ばした画像です。横位置は build_v3 と同じ経路が基準です。
- **二連の床版は高さが違うことがある。** 平面形が分かったら、`band_heights.py <SP> "-3:6,10:17" 88 446 15 14` で床版ごとに高さを測ります（実例: 内側の桁下 4.3、外側 10.4 → 6.5）。
- 橋脚は、見上げ画像の梁の縦縞・展開図・経路沿いの写真一覧（`sheet.py`）で決めます。柱の横位置は LFS と写真で決めます。**どの床版を支えるかは橋脚ごとに違います。**
- `blender/build_v3.py` ＋ `params_v3.json`：`decks`（床版ごとの `cp`、`zg`、`cols`）、`cols`、`piers`（`s`、`c1`、`c2`、`skew`、`decks`）。

## 3. 建物
- `buildings.py <SP> 2.0 10` → 壁面のクラスタを向き付きの箱にします。`finalize_buildings.py` で、**道路に重なる箱を除外**します（誤検出の典型）。
- 大きな建物や円形の建物は自動では薄い壁にしかなりません。上面図 `bld_overlay.png` を見て、`manual_buildings.py <SP> spec.json` に輪郭を書きます（高さは輪郭内の点から自動）。

## 4. 道路・歩道・横断歩道
- **道路は写真テクスチャではなく形状で作る**（ユーザーの要望でした）。写真の投影は位置を読む下絵として使います。
- `ortho_photo.py <SP> 3 0.12 16` → 路面への真上写真。`road_profile.py` で分類（車道・歩道・草）の横並びを見ます。`straighten.py` で縁石・白線・分離帯の横位置を読みます。
- `params_road.json`（区間ごとの `road` / `sidewalk` / `median` / `planting`、白線の種類、交差点の `openings`、`side_streets`、`skip_lines`）→ `blender/build_road.py`。
- 横断歩道は、まっすぐに伸ばした路面画像から範囲と縞の向きを読み、`build_markings.py` で作ります。白線は `detect_lines.py` で検出し、`lines_check.png` で必ず目視します。

## 5. 街路灯・信号・標識
- `poles.py` の候補は位置だけ信用します（高さでの自動分類は誤りが多かった）。
- `sign_views.py`（全ポールを写真から切り出した一覧と、4 方向からの拡大）で、種類と表の向き（`face`: 0=+s、90=+lat、180=−s、−90=−lat）を 1 本ずつ決めます。→ `pole_review.json` → `make_furniture_spec.py` → `blender/build_furniture.py`。
- 点群に無い細い柱は、`ground_pick.py` で位置を出します（汎用版は `scripts/pick3d.py`）。
- **柱の根元は車道に置かない。** `build_furniture.py` は `params_road.json` を読み、根元を縁石の内側 0.4 m に寄せます（`snap_to_kerb`、柱ごとに `"fixed": true` で無効）。

## 6. その他
- `extras.py` → 鉄塔・電柱・樹木。点の少ない高い塊はノイズです。高い塊が鉄塔とは限りません（実例では白い円筒の塔だった）。
- Blender での実行順: `build_v3.py`（PARAMS = params_v3.json）→ `build_ground.py`（`GROUND_MESHES=False`、`POLES_AUTO=False`）→ `build_furniture.py` → `build_road.py`（RPARAMS）→ `build_markings.py`（MPARAMS）→ `build_extras.py`（XPARAMS）。どれも自分のコレクションを作り直します。

## このシーンで効いた確認
- 3 枚並べ（写真｜同じカメラの 3DGS｜Blender）。汎用版は `views.py` ＋ `bl_views.py` ＋ `compare_sheet.py` です。
- **カメラが柱の中に入る**（比較画像が一面の灰色）＝柱の位置が経路上にある。前方と右方の両方で確認します。
- ユーザーが LFS で見せた視点の再現（汎用版は `views.py viewport`）で、交差点をまたぐ門型の開口の位置のずれが見つかりました。
- 撮影リグのビュー名（front/right…）の方向は一定ではありません。物の側は点群の座標で決めます。

## 2 回目の実例（360° カメラ、LFS なし）
同じ現場を、cubemap 展開の COLMAP と dense 点群（1.1 億点）だけから作り直した。スクリプトは案件フォルダにあり、`project.json` のモデル座標系を使う。
- 経路は橋脚の中心を通るスプライン（`route.py`、s と lat）。桁・床版の表（s, lat_e, lat_w, z）は、断面画像（`sec2.py`）と桁下面の高さの数表（`tab.py`）から読む。橋脚の柱の面は `fit_piers.py` で点群から自動で測る。
- 道路は `gen_ground.py`（区間の多角形 → 0.5 m 格子、縁石・側溝は断面の掃引、路面の轍と細かい凹凸）、街路は `gen_street.py`（写真で振り分けた柱の一覧から街灯・信号・標識）、高架の細部は `gen_detail.py`（支承、桁間の金網、ケーブルラック、橋梁灯、階段塔、T 形橋脚の梯子と縦どい）。
- 車両と動き: `gen_vehicles.py`（形式だけの車種、サブディビジョンのケージ）＋ `bl_build_veh.py`、`lanes.py`（車線）、`sim.py traffic|chase`（車間距離モデル、信号、追跡の横方向の回避、滑り、カメラの割り）→ `bl_anim.py`（車輪の回転と操舵、ブレーキ灯、信号の点灯、タイヤ煙、スキッド痕、はね飛ぶポール）。バックグラウンドの Blender で連番を書き、ffmpeg で MP4 にする（`render_all.sh`、1280×720・48 spp で 1 フレーム約 1 秒）。
