# Blender のモデルを Unreal Engine へ移す（UE MCP 経由）

道具: `scripts/ue_mcp.py`（MCP を HTTP で直接呼ぶ）、`scripts/blender/bl_export_groups.py`（書き出し）、`scripts/unreal/`（`ue_port.py`: 材質・取り込み・レベル・配置・歩行、`ue_surfaces.py`: UV なしメッシュの材質と Poly Haven、`ue_vegetation.py`: 植物）。設定は JSON 1 つ（実例: `recipes/temple_gate/unreal/ue_config_example.json`）。実例は寺（`recipes/temple_gate/`）とダム（`recipes/dam_spillway/`）。

## 進め方
1. Blender: 面の向きと物体の変換を確かめる（下記）→ `bl_export_groups.py` で、まとまり（建物・構造物ごと、地面、植栽）ごとに FBX と `export_manifest.json`（中心・寸法・マテリアルの色）。植栽はふつう書き出すだけで UE には入れない（下記）。
2. `ue_port.py <cfg> materials` → `import` → `level` → `place`。取り込んだ寸法が Blender と同じか、出力で確かめる。
3. 材質: 既存アセットを探す → 無ければ `ue_surfaces.py proc`（手続き的）か `tri`（Poly Haven のテクスチャ。ダウンロードは了解を得てから）→ `apply mapping.json`。
4. 植物: ユーザーに Bridge / Fab で植物を追加してもらう → `ue_vegetation.py measure` → `place plants.json`。
5. 歩行: Third Person を追加してもらう → `ue_port.py <cfg> walkable` → `StartPIE` で確かめる。
6. レベルとアセットを保存する。ビューポートの画像（`ue_mcp.capture`）をユーザーに送る。

## 接続とツールの癖
- UE エディタが MCP サーバーを動かしていれば（ModelContextProtocol プラグイン、既定 `http://127.0.0.1:8000/mcp`）、クライアントに unreal-mcp のツールが無くても `ue_mcp.py` で呼べる（`python ue_mcp.py toolsets / describe <Toolset> / call <Toolset> <tool> '<json>'`、Python は `Ue().call(...)`）。まず `netstat` でポート 8000 を確かめる。**ユーザーは作業の途中でエディタ（や Blender）を再起動することがある**。接続が切れたら、勝手に起動し直さず状態を確かめる。Blender は再起動すると共有フォルダの名前が変わる。
- `find_actors` は既定値のある引数も全部渡す（`{"root": null, "name": "", "actor_type": null, "tag": "", "bounds": null, "collision_channels": []}`）。`find_assets` の `asset_type` はクラスパス（`/Script/Engine.StaticMesh`）で、`asset_type: null` なら全種類。
- `CaptureViewport` は `captureTransform` と `annotations: null` を渡す。画像は text の JSON（`returnValue.image.data`）。エディタの世界を撮るので PIE の画面は撮れない。ビューポートの画角は変えられない（横 90° として扱う）。
- `ObjectTools.get_properties` は JSON 文字列を返し、構造体のキーは camelCase。`set_properties` は配列の長さと中身を一度に変えられない（先に要素のコピーで増やし、次に中身を変える）。
- `SkeletalMeshTools.get_bounds` は `origin` / `boxExtent`、`StaticMeshTools.get_bounds` は `min` / `max`。
- `get_actors_in_folder` は存在しないフォルダでエラー。先に `get_folders`。
- `set_nanite_enabled` などの直後は再ビルド中で、`exists` / `save_assets` が「Asset does not exist」を返す。少し待って保存し直す（`ue_port.Port.save`）。
- UE MCP を 2 本以上の処理から同時に呼ばない（応答が入れ違って止まった）。長いバッチの間は待ち、止まったら置けた数から再開する。
- FBX の頂点カラーは取り込まれない（`VertexColorImportOption = Ignore` 固定）。頂点ごとのデータは UV の U に入れる。
- テンプレートのプロジェクトには植物・地面の素材がほぼ無い。`get_plugin_content_paths` の全ルートの総当たりは 10 分以上かかるので、フォルダを絞る。
- Quixel Bridge の中身は埋め込みブラウザで、MCP（SlateInspectorToolset）からは読めず、クリックもできない。素材の選択と追加はユーザーに頼む。
- プロジェクト設定は `ConfigSettingsToolset`（Project / Engine / Rendering など）で読み書きできる。再起動が要る設定は、変えてからユーザーに再起動を頼む。

## 書き出し（Blender）
- **単位**: UE（Interchange）は FBX の数値をそのまま cm として読んだ（6.33 m の車庫が 6.33 cm）。頂点を 100 倍して書き出す。
- **軸**: モデル (x, y, z) m → UE (100x, −100y, 100z) cm。左右は反転しない。非対称なメッシュの `get_bounds` で必ず確かめる。PlayerStart の yaw −90 がモデルの +Y 向き。
- **物体の変換**: 書き出す前に位置・回転・拡大が単位行列か確かめる。ユーザーの手作業で 1 つだけ数 m 動いていて、UE でずれた。
- **面の向き（UE は裏面を描かない）**: Blender は両面を描くので、裏返りに気づかない。時計回りの多角形の板は上面が下を向き、UE では底面が地面と Z ファイティングした。球状の部品は面が全部内向きだった。生成関数で向きを保証し、書き出す前に敷地を 1 m 格子で真上から `scene.ray_cast` して、**最初に当たる面の法線が上を向いていること**を確かめる。`bl_coplanar.py` は同じ向きの重なりしか見ないので、裏返りはこの検査で見る。
- まとまりは「建物・構造物ごと 1 メッシュ、原点は中心の地面」。UE で動かす・複製する・差し替える単位になる。

## UE での取り込みと配置（`ue_port.py`）
- `import_file`（`import_materials=False`）のスロット名は Blender のマテリアル名のまま。親マテリアル＋スロット名ごとの MaterialInstance（`MI_<名前>`）を割り当てる。
- **Nanite は全部のメッシュで有効にする**（三角形の少ないものも）。Nanite でない大きなメッシュ（数百 m の地面）は、PIE で `[VSM] Non-Nanite Marking Job Queue overflow` を出した。平らな地面は `CastShadow=False`（config の `no_shadow`）。警告が消えたかは `LogsToolset.GetLogEntries`（pattern `Non-Nanite Marking`）の行数が PIE の前後で増えないことで見る。
- 当たり判定は `BodySetup.CollisionTraceFlag = CTF_UseComplexAsSimple`。`SceneTools.trace_world` を真上から撃って確かめる。
- 新しいレベルは `/Engine/Maps/Templates/Template_Default` を `duplicate` して `load_level`（未保存の Untitled を開いていると拒否される。ユーザーに先に伝える）。テンプレートの床（上面 z = −0.5 cm）は地面と重なるので消す。
- 全体を 1 つのアウトライナーのフォルダにまとめ、最後にレベルを保存する。

## 材質（UV の無いメッシュ）
- **学習写真をテクスチャに焼き込まない**: 試したが、斜めの面の伸び・軒の縁の空・写り込んだ車や木で見栄えが悪いと言われ、やめた。既存アセット → 手続き的マテリアル → Poly Haven の順に考える。
- **手続き的**（`ue_surfaces.py proc`）: Custom HLSL 1 つで、ワールド座標から模様を作る。ノイズ、木目、ずらし張りの敷石（目地）、瓦の段の 4 種類。
- **Poly Haven**（`polyhaven-list --sizes` → 了解 → `polyhaven-get` → `import-tex` → `tri`）: API は `https://api.polyhaven.com/assets?t=textures` と `/files/<id>`。CC0、2K の diff / nor_dx / rough の jpg で 1 種 3〜15 MB。三面投影（`TileCm`、`Tint`）、法線はワールド空間（`bTangentSpaceNormal=False`、whiteout ブレンド、nor_dx は G を反転）、法線・粗さは `SRGB=False`。
- **Custom HLSL では `Texture2DSample()` を使う**。`Tex.Sample()` はパストレーシングのヒットシェーダーでコンパイルできず、マテリアル全体が失敗する。Substrate のプロジェクトは `recipes/dam_spillway/RECIPE.md` の水の注意も見る。
- テクスチャの色はそのまま使えないことが多い（`dark_wood` は朱色寄り、草は枯れ色寄り）。`Tint` で写真の色に寄せるか、輝度だけを模様に使って測った色を掛ける。
- Blender のプレビュー色は地面には明るすぎる（実物のアスファルトは線形で 0.07 程度）。白っぽく見えたら、無限の PostProcessVolume で露出補正を入れる。

## 植物（`ue_vegetation.py`）
- Blender で作った木や生垣は UE では見栄えが悪い（実例での評価）。位置・高さ・樹冠の径だけを使い、本物の植物アセットに置き換える。
- UE 5.8 の Megaplants は、1 種につき形の違う 4 本のスケルタルメッシュ（`_A`〜`_D`）と ProceduralVegetation。Foliage ツールは使えないので、アクターとして置く（数千本なら `ProgrammaticToolset.execute_tool_script` で 150 本ずつ、1 本 0.5 秒）。樹冠の中心は原点からずれていることがあるので戻す。生垣は低木を 0.9 m 間隔で並べる。植物には当たり判定が無い。
- **葉が出ない（枝だけ）**: 葉は Nanite Assemblies の部品。プロジェクト設定 Rendering の `bEnableNaniteFoliage` を true にして、エディタを再起動すると出た（再起動後に部品のビルドが走る）。
- 素材が来るまでの仮置きは PCG サンプルの木（`/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_01〜03`、高さ 9.6 / 12.5 / 15.5 m）を拡大縮小して置ける。

## 歩けるようにする（PIE）
- Third Person のキャラクターはテンプレート次第で無い。ユーザーに Add Feature or Content Pack で追加してもらう（`/Game/ThirdPerson`、`/Game/Characters/Mannequins`）。
- WorldSettings の `DefaultGameMode` に `BP_ThirdPersonGameMode_C`、PlayerStart を地面の上に置く（`ue_port.py walkable`）。
- `StartPIE` / `IsPIERunning` / `StopPIE` で起動を確かめる。PIE のアクターは `find_actors` で `UEDPIE_0_...` のパスで見つかる。キャラクターの z がカプセルの半分の高さ（約 94 cm）なら地面に立っている。

## 長い処理（Blender 側）
- Blender MCP の呼び出しには制限時間がある（数分で時間切れ）。長い処理は `scripts/blender/bl_bake_queue.py` のように `bpy.app.timers` で Blender の中に積み、状態をファイルに書いて外から見守る。止めたいときは、キューが実行するスクリプトのファイル名を変える。
