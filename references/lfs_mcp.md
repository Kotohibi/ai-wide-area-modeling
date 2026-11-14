# LichtFeld Studio MCP: 何が取れて何が取れないか

エンドポイントは `http://127.0.0.1:45677/mcp` です（JSON-RPC over HTTP）。この作業では `scripts/lfs_mcp.py`（Python、標準ライブラリだけ）か `scripts/lfs_mcp.ps1` で直接呼びます。Claude Desktop から使うときは `mcp-remote` 経由です。
- LichtFeld を再起動すると「Server not initialized」になります。どちらのヘルパーも `initialize` を自動で送ります。
- ツールの一覧は `python lfs_mcp.py tools`、引数の定義は `python lfs_mcp.py schema <tool>` で見られます。**バージョンでツールが増減するので、最初に一覧を確認します。**

## 学習データへのアクセス
| 欲しいもの | MCP で | 実際の取り方 |
|---|---|---|
| 学習カメラの姿勢・内部パラメータ | ○ `camera_list` | uid、name、position（raw 座標の中心）、focal、center、fov、image_path、depth_path、mask_path |
| 学習写真の画素 | ×（パスだけ） | `image_path` のファイルを直接読む |
| 初期点群（COLMAP points3D） | ×（中身は返らない） | `image_path` の 2 階層上の SfM フォルダから直接読む（`colmap_io.py`、txt / bin / ply）。`scene_export_colmap` で LFS 内のカメラと点群を COLMAP 形式に書き出すこともできる |
| 3DGS 本体 | ○ `scene_export_ply`（PLY に書き出し）、`gaussians_read`（指定した点のテンソル） | `export_points.py 3dgs --export` |
| 写真と同じ視点の 3DGS 画像 | ○ `render_capture camera_index=<uid>` | 写真と画素単位で一致する。差分確認の要 |
| 現在のビューポート | ○ `camera_get`（eye、forward、up、fov_degrees、width、height は world 座標）、`render_capture`（camera_index なし） | `views.py viewport` |
| ビューポートを動かす | ○ `camera_set_view`（eye、target、up、fov_degrees）、`camera_go_to_dataset_camera`（uid） | `views.py look` / `views.py goto` |
| LFS 内での任意の Python | ○ `editor_run` | 最後の手段。結果はコンソール出力で返る |

LFS の画面上で写真を 3DGS に重ねて見る操作は、MCP にはありません。その代わりが「`render_capture camera_index` ＋ 写真」の並べ比べです。

## 座標系
- `transform_get node=<splat node>` の `world.matrix` を `M` とすると、**raw = M @ world** です（高架の実例では x 軸まわりの反転を含む直交行列、平行移動 0）。行列が列優先で返る場合は、平行移動が最終行に出ます（`setup_project.py` が自動で判定）。
- raw 座標で返るもの: `camera_list` の position、COLMAP の images.txt・points3D、`scene_export_ply`。world 座標で返るもの: `camera_get`、`camera_set_view`。
- `setup_project.py` は、`camera_list` の位置と COLMAP の中心が一致するかを検査します。一致しない場合は、LFS が読み込み時にデータを変換しているので、その変換を調べるまで先に進みません。

## 注意点
- `camera_list` は 7,000 枚規模で約 2 MB の JSON になります。ファイルに保存して使います（`lfs_cameras.json`）。
- `scene_list_nodes` はカメラも 1 ノードずつ返すので巨大です。splat ノードは `type == "splat"` で探します。
- **`render_capture`（camera_index なし）は、ビューポートが最後に描いた画面を返します。** LFS のウィンドウが最小化・非表示だと（`camera_get` の width と height が 160×1 のような小さい値になる）、`camera_set_view` で視点を変えても画面は描き直されません。待っても古い画面のままです（実例で確認）。ユーザーの視点を取るときは LFS のウィンドウを表示してもらい、`camera_get` の width と height がまともな値かを確かめます（`views.py viewport` は警告を出す）。`camera_index` 付きの `render_capture` は画面外で描くので、この影響を受けません。
- `camera_get` の `fov_degrees` は縦の画角として扱います（前回の作業で、ユーザーの視点と Blender が一致した）。縦横比は `render_capture` の画像サイズを使います。
- `render_capture camera_index` は、レンズのカメラをピンホールとして描きます。魚眼のデータセットでは写真と一致しません。
- `scene_export_ply` は、15M ガウシアンで約 1 GB・数十秒かかります。`sh_degree=0` で軽くします。
- 地上撮影の 3DGS は、上空や撮影経路から離れた視点では崩れて見えます。LFS で確認するときは、撮影位置に近い地上視点を使います。作業前に `camera_get` を控えて、最後に元の視点へ戻します。
