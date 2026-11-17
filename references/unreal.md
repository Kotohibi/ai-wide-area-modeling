# Blender のモデルを Unreal Engine へ移す（UE MCP 経由）

道具: `scripts/ue_mcp.py`（MCP を HTTP で直接呼ぶ）、`scripts/blender/bl_export_groups.py`（書き出し）、`scripts/unreal/`（`ue_port.py`: 材質・取り込み・レベル・配置・歩行、`ue_surfaces.py`: UV なしメッシュの材質と Poly Haven、`ue_vegetation.py`: 植物。以上は UE 5.8 のツール名で書いてある）、**UE 5.9 以降用**（エディタの中の Python を使う。どの現場でも使える）: `ue_py.py`（Python を実行）、`ue_viewport_cap.py`（写真と同じ姿勢で撮る）、`ue_walk_check.py`（戸口を実際に歩かせる）、`ue_niagara_fall.py`（花びら・落ち葉・雪）、`ue_camera_seq.py`（カメラ軌道 → Level Sequence → Movie Render Queue。Blender 側は `scripts/blender/bl_camera_json.py`）、`scripts/frames_check.py`（連番の欠け・めり込み・飛び）。設定は JSON 1 つ（実例: `recipes/temple_gate/unreal/ue_config_example.json`）。実例は寺（`recipes/temple_gate/`）とダム（`recipes/dam_spillway/`）。

## 進め方
1. Blender: 面の向きと物体の変換を確かめる（下記）→ `bl_export_groups.py` で、まとまり（建物・構造物ごと、地面、植栽）ごとに FBX と `export_manifest.json`（中心・寸法・マテリアルの色）。植栽はふつう書き出すだけで UE には入れない（下記）。
2. `ue_port.py <cfg> materials` → `import` → `level` → `place`。取り込んだ寸法が Blender と同じか、出力で確かめる。
3. 材質: 既存アセットを探す → 無ければ `ue_surfaces.py proc`（手続き的）か `tri`（Poly Haven のテクスチャ。ダウンロードは了解を得てから）→ `apply mapping.json`。
4. 植物: ユーザーに Bridge / Fab で植物を追加してもらう → `ue_vegetation.py measure` → `place plants.json`。
5. 歩行: Third Person を追加してもらう → `ue_port.py <cfg> walkable` → `StartPIE` で確かめる。
6. レベルとアセットを保存する。ビューポートの画像（`ue_mcp.capture`、5.9 は `ue_viewport_cap.py`）をユーザーに送る。
7. 求められたら: 動く物（`ue_niagara_fall.py`）、カメラワークと動画（`bl_camera_json.py` → `ue_camera_seq.py seq` → `render` → `frames_check.py`）。

**版の見分け方**: `python ue_mcp.py toolsets` に `editor_toolset.toolsets.python_scripting.PythonScriptingTools` があれば 5.9 以降。その場合は「UE 5.9 での違い」を先に読み、取り込み・材質・配置は `ue_py.py` で Python を書く（`ue_port.py` などの `TS` 表は 5.8 の名前）。

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

## UE 5.9 での違い（実例: 木造の廃校舎。`ue_port.py` など 5.8 用の道具はそのままでは動かない）
- **ツールセットの名前が変わった**（`EditorToolset.AssetToolset` / `LevelToolset` / `StaticMeshToolset` …）。メタツールは `list_toolsets` / `describe_toolsets`（配列）/ `describe_tools` / `call_tool`。`ue_mcp.py describe` は 5.9 の形にも対応済み。`ue_port.py` の `TS` の表は 5.8 の名前なので使えない。
- **`PythonScriptingTools.execute_python` がある**（`editor_toolset.toolsets.python_scripting.PythonScriptingTools`）。エディタの中で `unreal` の Python をそのまま実行でき、最後の式の値が返る（トップレベルの `await` 可、`await call_tool(名前, **引数)` で他のツールも呼べる）。レベル作成・マテリアル作成・配置・保存はこれで書く方が、ツールを 1 つずつ呼ぶより速く確実（`scripts/unreal/ue_py.py <script.py>`）。最初に `read_me` を読む。禁止事項: 関数の中の import、`time.sleep`、`urllib.request.urlopen` など（スクリプトごと拒否される）。
- エディタが取り込みやシェーダーの処理中は、ツールが **「Not run: … slow task / modal dialog」** で断られる。slow task は数秒おきに再試行する（`ue_py._retry`）。modal dialog はユーザーに閉じてもらう。
- **FBX の単位を正しく読むようになった**。5.8 用に頂点を 100 倍して書き出すと 100 倍の大きさになる（校舎が 4.3 km）。5.9 ではメートルのまま書き出す（`bl_export_groups.py` は `EXPORT["unit_scale"] = 1.0`）。**取り込んだ直後に `get_bounding_box` を Blender の寸法と比べる**のは版に関係なく必須。軸は同じ（モデル (x, y, z) → UE (100x, −100y, 100z)）。非対称な部品の最小・最大を y を反転して比べれば、向きも同時に確かめられる。
- **新しいレベル**: `LevelEditorSubsystem.new_level_from_template(パス, "/Engine/Maps/Templates/Template_Default")`。床は `Floor` というラベルのアクター。
- **レベルを複製して別案を作るとき**: `EditorAssetLibrary.duplicate_asset(レベル)` の直後に `load_level` すると、エディタが Fatal error（World Memory Leaks）で落ちた。`new_level_from_template(新しいパス, 元のレベル)` なら、照明・PostProcessVolume・GameMode・PlayerStart ごと複製して開ける。その後、元のメッシュのアクターを消して別案（復元案など）を置く。
- **ユーザーが Play（PIE）中は、アセットの読み込み・編集が失敗する**（`load_asset` が None）。作業の前に `IsPIERunning` を見て、Play 中なら待つか、ユーザーに止めてもらう（勝手に止めない）。エディタの画面が隠れている・最小化されていると `CaptureEditorViewport` は断られる（`ListEditorViewports` の `bIsVisible`）。前面に出してもらう。
- **撮影**: `SceneCaptureToolset.Capture`（画面外の描画）は時間方向の履歴が無く、Lumen とスカイライトが入らないので影が真っ黒に写る。**エディタのビューポートを使う**: ゲームビュー＋リアルタイムにして `SetCameraTransform` → 数秒待つ → `CaptureEditorViewport`。画角は `set_level_viewport_fov` で広めにして、中央を切り出す（`ue_viewport_cap.py set <比較フォルダ>`: `cmp_set.py` の `cameras.json` の姿勢をそのまま使い、写真・Blender の比較レンダーと並べる。任意の視点は `pose`）。
- **室内が真っ暗なとき**: まず表示フラグ `VisualizeHDR` を入れて撮り、平均 EV100 と EV の下限・上限を読む。実例では、室内は EV −6.4 で、自分で入れた下限 −2 に張り付いて 4 段ぶん暗く写っていた（下限を −10 にして解決）。プロジェクトによっては `r.DefaultFeature.AutoExposure=False` なので、無限の PostProcessVolume でヒストグラム測光（低 30 %〜高 75 %、明るい窓に引きずられない）を入れる。Lumen の設定（HitLighting）を変えても、建物を部品に分けても、露出が原因なら直らない。
- **光の絶対量**: テンプレートの太陽は 6 lux で、屋外が EV 2 前後、室内は EV −7〜−9 になり、露出計の範囲（ヒストグラムの下限 EV −10）からはみ出して室内だけ暗いままになる。太陽を 400 lux 程度に上げると（空は SkyAtmosphere で連動）、屋外も室内も測光の範囲に入る。
- **室内が青白くかすむ**: テンプレートの ExponentialHeightFog は壁に遮られず室内にもかかる。密度を 1/10 以下にし、開始距離を 30 m にすると消えた。スカイライトの青みは `light_color` を少し暖色にして抑える。
- **ガラス（半透明）**: Nanite にせず別メッシュにし、コンポーネントの `visible_in_ray_tracing` / `affect_dynamic_indirect_lighting` / `affect_distance_field_lighting` / `cast_shadow` を切る（窓越しの間接光を遮らせない）。
- **建物は 1 棟 1 メッシュにせず、壁の通り・床・天井・屋根ごとに分ける**（Lumen は面の光をメッシュの外から撮った「カード」で持つので、箱の内側の面は拾いにくい。Epic の推奨）。生成スクリプトが箱を別々に作っていれば、つながった部品ごとに外接箱を取り、薄い向きと位置でまとめるだけで分けられる（実例: 248 部品、取り込みは 1 部品 3 秒）。部品はワールド座標のまま書き出し、全部を原点に置く。※実例では分ける前後の明るさを同じ露出で比べていないので、効果の大きさは未確認。
- **マテリアル**: `MaterialEditingLibrary` で Custom HLSL のマスターを作り、Blender のノードの式を**同じ数値のまま**書き写せる（ワールド座標 → モデルの m に直す: `p = float3(WP.x, -WP.y, WP.z) / 100`）。Blender のノイズ（fBM、正規化）は、12 方向の勾配の Perlin に 0.982 を掛け、振幅で割って 0.5 倍して 0.5 を足すと分布が合い、しきい値（0.50〜0.66 など）をそのまま使える。凹凸は高さの関数を 3 点（p、接線方向に 2 mm ずらした 2 点）で評価して法線を作る（Nanite では Custom の ddx/ddy に頼らない）。両面（Two Sided）にしておくと、Blender で気づかない裏返りがあっても消えない。パラメータは Vector 9 個に詰め、VectorParameter の出力は 4 成分なら `"RGBA"`。瓦は UV を使わず、面の法線から軒方向と流れ方向を作ると UV が要らない。
- **植物は MCP から入れられる**（`FabToolset`: `SearchFabListings`（"megaplants"）→ `InstallFabListing`。Megaplants は無料で、UE_5.8 版が 5.9 に入る。入る先は `/Game/Megaplant_Library/<種>`）。ダウンロードは了解を得てから。**先に** `.uproject` に `ProceduralVegetationEditor`、`DefaultEngine.ini` の `[/Script/Engine.RendererSettings]` に `r.Nanite.Foliage=True` を足して再起動してもらう（どちらもプロジェクトの変更なので了解を得る。元のファイルは控える）。日本向きの種: Japanese Cypress（ヒノキ）、Yoshino Cherry、Japanese Knotweed（イタドリ）、Bracken Fern（ワラビ）、Giant Bamboo、Dry Common Reed（枯れた背の高い草）。実測の容量は 1 種 65〜456 MB（8 種で 2.1 GB）。
- **植物の配置（5.9 の Python）**: 空の `Actor` を置き、`await call_tool("EditorToolset.ActorToolset.AddComponent", owner=actor, componentType=unreal.InstancedSkinnedMeshComponent, name=...)` → `set_skinned_asset_and_update(mesh)` → `add_instances([Transform…], [0]*n, False, False)`。樹種のメッシュごとに 1 コンポーネント（実例: 木 815 本＋下草 1,395 株、警告なし）。高さは `SystemLibrary.line_trace_single` で地形に載せる（軒に当たらないよう、推定の地面の 1.5 m 上から撃ち、当たった相手が地形のときだけ使う）。初めて全メッシュを読み込む寸法測定は 15 分かかった（Nanite の部品のビルド）。Japanese Cypress の F・G は葉のほとんど無い細い木で、多数置くと枯れ木の林に見える（A〜D を使う）。
- **紅葉（Megaplants の色を変える）**: 葉のマスター `MA_Foliage_Trees` の `Seasons` スイッチ・`Season Color 1/2`・`Health Offset` は、変えても見た目が変わらなかった。効いたのは **`BaseColor Tint`**: 種の葉の MI（例 `MI_Tree_Hornbeam_01_Foliage`）を親にした子 MI を作って Tint を入れ、`InstancedSkinnedMeshComponent.set_material(葉のスロット, MI)` で上書きする（Nanite Assemblies の葉にも効く。元のアセットは変えないので、同じ植物を使う他のレベルに影響しない）。実例（神社の秋）: 赤 (0.95, 0.04, 0.02)、橙 (1.0, 0.42, 0.02)、黄 (1.0, 0.56, 0.03)、枯れ色 (0.80, 0.36, 0.08)。緑の葉に掛かるので、G を 0.7 にすると黄緑に見える（黄色は G 0.55 前後）。色ごとに 1 コンポーネント（メッシュ×色）。Yoshino Cherry は満開の花のアセットなので、秋の場面の桜には使えない（花がピンクのまま）。
- **地面**: Blender で写真から決めた草の色は、UE の強い日差しでは明るい黄緑の平らな面に見える。0.6 倍ほどに落とし、細かいノイズと広いむらを掛ける。

## 書き出し（Blender）
- **単位**: UE（Interchange）は FBX の数値をそのまま cm として読んだ（6.33 m の車庫が 6.33 cm）。頂点を 100 倍して書き出す。
- **軸**: モデル (x, y, z) m → UE (100x, −100y, 100z) cm。左右は反転しない。非対称なメッシュの `get_bounds` で必ず確かめる。PlayerStart の yaw −90 がモデルの +Y 向き。
- **物体の変換**: 書き出す前に位置・回転・拡大が単位行列か確かめる。ユーザーの手作業で 1 つだけ数 m 動いていて、UE でずれた。
- **面の向きは書き出しのときに直す（実例: 神社の 193 部品のうち 79 部品）**: 両面のマテリアルにしても、裏返った閉じた部品は **Lumen の距離場が内外逆になって真っ黒に写り、当たり判定も素通りする**（石段が黒く、真上からの `line_trace` が石段を抜けて下の地形に当たった。部品だけに `line_trace_component` を撃つと、底面に法線 +z で当たる＝裏返り）。書き出しの bmesh で、閉じた部分は `bmesh.ops.recalc_face_normals`（外向き）、開いた部分（屋根・敷石・地形の板）は向きをそろえてから面積で重み付けた法線の z が負なら全体を反転する（実例 `ue\bl_export_ue.py` の `orient()`。bmesh で作った面は `bm.normal_update()` をしないと法線が 0 のまま）。UE 側でも `BodySetup.double_sided_geometry = True`、地形以外は LOD0 のビルド設定 `generate_distance_field_as_if_two_sided = True`。
  **判定は頂点を溶接した複製で行い、反転だけを元の面に戻す**: 生成スクリプトの Edge Split で箱も管も 1 面ずつの開いた部品になっていて、そのまま判定すると垂直な面（法線 z の和 ≈ 0）の向きが乱数のように反転され、鳥居の片方の柱と梁の正面・石碑・台座が UE で真っ黒になった（`remove_doubles` した複製で判定 → 面ごとの番号で元の面へ。元の面は分かれたままなので角は鋭いまま）。`recalc_face_normals` は**閉じた部分だけ**にかける（開いた部分にかけると、正しかった灯籠の笠が 13 基中 4 基裏返った）。開いた部分は生成スクリプトの向きのまま、法線 z の面積重み付きの和が面積の −20 % より下のとき（はっきり下向きの板）だけ反転する。書き出した全部品を Blender で読み直し、上と 4 方向から格子状に光線を当てて、最初に当たった面の裏表を数える検査（実例 `uel_chk_faces.py`）で確かめる（実例: 文字のメッシュと建物の内側の板以外は 0 %）。**マテリアル側でも防ぐ**: 両面マテリアルでワールド空間の法線を出す（Custom HLSL で `tangent_space_normal=False`）と、裏の画素で頂点の法線が反転されないまま使われて真っ黒になる。入力の `VertexNormalWS` に `TwoSidedSign` を掛けてから Custom ノードへ渡す（上下逆さまの板で確かめた: 掛ける前は真っ黒、掛けた後は正常）。**確認の注意**: `double_sided_geometry` を入れた後の `line_trace` は、当たった面の法線を光線の側へ返すので、向きの検査には使えない。書き出した FBX を Blender で読み直し、柱なら軸からの向きと面の法線の内積で数える。黒い部品は、エンジンの `/Engine/BasicShapes/BasicShapeMaterial` に替えて明るくなれば、メッシュの向きが原因（両面マテリアルでワールド空間の法線を出すと、裏の画素では頂点の法線が反転された値が入る）。
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
- Blender で作った木や生垣は UE では見栄えが悪い（実例での指摘）。位置・高さ・樹冠の径だけを使い、本物の植物アセットに置き換える。
- UE 5.8 の Megaplants は、1 種につき形の違う 4 本のスケルタルメッシュ（`_A`〜`_D`）と ProceduralVegetation。Foliage ツールは使えないので、アクターとして置く（数千本なら `ProgrammaticToolset.execute_tool_script` で 150 本ずつ、1 本 0.5 秒）。樹冠の中心は原点からずれていることがあるので戻す。生垣は低木を 0.9 m 間隔で並べる。植物には当たり判定が無い。
- **葉が出ない（枝だけ）**: 葉は Nanite Assemblies の部品。プロジェクト設定 Rendering の `bEnableNaniteFoliage` を true にして、エディタを再起動すると出た（再起動後に部品のビルドが走る）。
- 素材が来るまでの仮置きは PCG サンプルの木（`/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_01〜03`、高さ 9.6 / 12.5 / 15.5 m）を拡大縮小して置ける。

## 歩けるようにする（PIE）
- Third Person のキャラクターはテンプレート次第で無い。ユーザーに Add Feature or Content Pack で追加してもらう（`/Game/ThirdPerson`、`/Game/Characters/Mannequins`）。
- WorldSettings の `DefaultGameMode` に `BP_ThirdPersonGameMode_C`、PlayerStart を地面の上に置く（`ue_port.py walkable`）。
- **古い木造建築は戸口が低い**（鴨居が 5 尺 7 寸 = 1.73 m 前後、実例では床から 1.6〜1.8 m、幅 0.7 m の戸口は枠の内側が 0.6 m 未満）。テンプレートのキャラクター（カプセル高さ 1.8 m、半径 35 cm、段差 45 cm まで）は入れない。テンプレートの素材は変えず、**子ブループリント**を作って小さくする（実例: `BlueprintFactory.parent_class` → CDO の `capsule_component` を半高 77・半径 22、`mesh` の位置と拡大を同じ比率、`character_movement.max_step_height` 60、GameMode の子で `default_pawn_class` を差し替え、WorldSettings の `default_game_mode` に設定）。モデルを作る段階で、戸口の高さ・幅と敷居の段差を表にしておくと判断が早い。
- **PIE に丸い操作パッドが出る**: プロジェクト設定 Input の `bAlwaysShowTouchInterface=True`（`DefaultInput.ini`）が原因。False にするとマウス・キーボード操作になる（**`ConfigSettingsToolset.SetSectionProperties`（Project / Engine / Input、`{"bAlwaysShowTouchInterface": false}`）で変える**。Python で CDO を変えて ini を書き換えるだけでは、起動中のエディタには効かず、パッドが出続けた。確認はテンプレートのコントローラーの `should_use_touch_controls()` が False を返すことと、PIE の画面）。実例ではパッド表示は不要と指摘された。
- **閉じた戸は歩行者を止める**（実例での指摘: 「扉が全部閉まっていて入れない」）。UE 用の書き出しでは引き戸を開けた状態にする（生成スクリプトに「全部開ける」スイッチを作り、.blend は閉じたまま）。確認は全戸口を自動で歩かせる（`ue_walk_check.py <tests.json>`: PIE を 1 回起動し、`pawn.set_actor_location` と `controller.set_control_rotation` で戸口の 1 m 手前へ移して `ApplyInput`、壁の線を 0.5 m 以上越えたら合格。2 枚・4 枚の引き戸は開口の半分に寄るので、空いている側の中央を通す。家具の上に出た場合に備えて反対側からも試す）。
- **歩行の確認は実際に歩かせる**（UE 5.9）: `StartPIE`（`options.startTransform` で任意の位置から）→ `InputToolset.ApplyInput`（`/Game/Input/Actions/IA_Move` に (0, 1, 0) を数秒）→ `GameplayStatics.get_player_pawn(get_game_world(), 0)` の位置と z（床の高さ＋カプセルの半高か）を読む。戸口ごとに外から中へ歩かせ、止まった位置で通れたかを判定する（`ue_walk_check.py`。戸口の一覧はモデルのパラメータから作る）。ゲーム画面は `CaptureGameViewport`（`world` = ListWorlds の PIE、`maxResolution` 必須）。
- `StartPIE` / `IsPIERunning` / `StopPIE` で起動を確かめる。PIE のアクターは `find_actors` で `UEDPIE_0_...` のパスで見つかる。キャラクターの z がカプセルの半分の高さ（約 94 cm）なら地面に立っている。

## 動く物: 花びら・落ち葉・雪（Niagara、UE 5.9。`ue_niagara_fall.py`）
- `ue_niagara_fall.py <config.json>`: マテリアル（スプライトの UV から花びら・葉・円の形を抜く。両面、少し発光）→ システム → 発生箱ごとのアクター。発生箱は 1 m で、アクターの拡大がそのまま箱の大きさになる（木 1 本に 1 つ、樹冠の大きさに合わせる）。
- **Niagara は MCP から組める**（UE 5.9 `NiagaraToolsets.NiagaraToolset_System`）: `CreateNiagaraSystem`（雛形はシステムのみ。エミッタの雛形は `AddEmitter` で足し、元のエミッタを `RemoveEmitter`）→ `GetEmitterInputValues` で入力名と型を読む → `SetStackInputData`（`{"struct": {"refPath": "/Script/Niagara.NiagaraFloat"}, "value": {"value": 7}}` の形）→ `SetRendererData`（`propertyValues` は JSON 文字列。`Material`）→ `GetStackIssues` のエラーは `ApplyStackIssueFix`。花びら・落ち葉は HangingParticulates（箱の中に発生、WindForce と AerodynamicDrag）が近く、Wind Speed の z を負にすると抗力で終端速度に落ち着いてゆっくり落ちる。発生の箱を 1 m にして `UseOwnerScale` のままにすると、アクターの拡大で木ごとの樹冠の大きさに合わせられる。スプライトのマテリアルは `set_material_usage(MATUSAGE_NIAGARA_SPRITES)`、陰で黒く見えるので発光を少し足す。
- **Niagara の Wind Force**: `Wind Speed` は風の速度、**`Scale` は乱流（Curl Noise）の強さ**で、力の倍率ではない。6 にすると花びらが突風のように振り回される。「しとしとと落ちる」には Wind Speed を落下だけ（横 0.03 m/s、下 0.4 m/s）、Scale 0.5〜2、Frequency 2。値が効かないと思ったら `GetEmitterInputValues` で全モジュールの入力を読む。
- **量と速さは見る人の感じ方で決まる**（実例: 「桜吹雪が多すぎ、散るぐらいで」「しとしとと落ちる感じ」）。最初は控えめ（木 1 本あたり毎秒 10 枚前後、落下 0.4 m/s、横風ほぼ 0）にして、つまみ（発生数・風速・乱流）の名前と今の値を報告に書く。動きは静止画では確かめられない: 動画か PIE で見てもらうまで「未確認」と書く。
- 粒は地面に当たらず、寿命で消える（寿命 ≧ 高さ ÷ 落下速度）。積もらせたいなら別に作る。

## カメラワークと動画（UE 5.9。`bl_camera_json.py` → `ue_camera_seq.py` → `frames_check.py`）
- **カメラは「コマごとの位置と注視点」の JSON にして渡す**（`bl_camera_json.py`、または経路を作るスクリプトから直接）。こうすると Blender を開いていなくても UE に移せ、Blender と UE で同じコマ番号・同じ画角の連番ができる（並べる・ワイプで切り替える編集がそのままできる）。
- **シーケンスの作り方**（`ue_camera_seq.py seq`）: `LevelSequenceFactoryNew` でシーケンスを作り、`add_spawnable_from_class(CineCameraActor)`（スポーン式にすると、同じシーケンスを別案のレベルでも再生できる）→ Transform トラックの `get_all_channels()`（位置 xyz、回転 roll・pitch・yaw、スケール）に 1 コマ 1 キーを線形補間で入れる → カメラカットトラックに `seq.get_binding_id(cam)`。カメラの設定は `cam.get_object_template().get_editor_property("camera_component")` に入れる（`get_cine_camera_component()` は None を返す）。フィルムバックを 36 × 20.25 mm にして Blender と同じ焦点距離にすると水平画角が一致する。`focus_method = DISABLE` にしないと近くがぼける。yaw は 360° の飛びが出ないよう連続にしておく。
- **`ue_camera_seq.py` が扱わないもの**（必要なら書き足す）: 焦点距離が途中で変わるカメラは、焦点距離のトラックをコンポーネントのバインドに付ける（`add_spawnable_from_instance(レベルに一時的に置いた CineCameraActor)` → `add_possessable(actor.get_cine_camera_component())` → `set_parent(カメラ)`。テンプレートのコンポーネントを渡すと無効なバインドになる）。カメラの傾き（ロール）を持ち込むなら、回転を `MathLibrary.make_rot_from_xz(前, 上)`（y を反転したベクトル）で作る。
- **描画**: `MoviePipelineQueueSubsystem` のジョブに Deferred パス・JPG 出力・`MoviePipelineGameOverrideSetting`（入れないと PIE のキャラクターが映る）を足し、`render_queue_with_executor(MoviePipelinePIEExecutor)`。すぐ戻るので `is_rendering()` を外から見て待つ。出力の `zero_pad_frame_numbers`（桁数）、`file_name_format = "f_{frame_number}"` で Blender のコマ番号と同じ名前になる（拡張子は `.jpeg`）。パーティクルが空中に行き渡るよう `engine_warm_up_count` を 20 秒ぶん、Lumen と露出のため `render_warm_up_count` を 100 コマ前後。Blender のコマと重ねて見せるなら `r.MotionBlurQuality 0`（既定のモーションブラーはかなり強い）。実測: 1280×720 で 1,459 コマが約 1 分。
- **動画はビューポートを 1 枚ずつ撮らず、Movie Render Queue で描く**（`ue_camera_seq.py render`）: 時間が固定刻みで進むので、Niagara の粒も、マテリアルで動かす雪や花びらも、植物の揺れも正しい速さになる。1080p でも 1,000 コマ台が 1 分前後で終わる。
- **複数ショットの映像**: カメラのファイルに `cuts`（[開始, 終了) の組）を持たせ、ショットごとにカメラカットのセクションを作る。Movie Render Queue はカットごとにウォームアップして時間方向の履歴を捨てるので、切り替わりで残像や露出の引きずりが出ない。ショットの最後のキーは一定補間にする。試し撮りは 960×540 で全体を出し、各ショットの 0 / 33 / 67 / 100 % のコマを一覧にして構図と突き抜けを見る（1 分で回る）。
- **連番の書き出しは空き容量を先に確かめる**: 1080p の JPEG は 1 フレーム 1〜1.5 MB、1 本 1.5〜2.5 GB。4 季節 × 2 版でドライブが満杯になり、別の書き出しが途中で失敗した。出力先はプロジェクトの `Saved/MovieRenders` など空きのあるドライブにする。Git Bash では `/Game/...` を環境変数で渡すとパスが書き換えられるので、アセット名だけを渡す。
- **描いた連番は編集の前に機械で確かめる**（`frames_check.py <dir> --rename --sheet sheet.jpg`）: 欠けたコマ、ほぼ単色のコマ（カメラが壁・戸・地面の中）、前のコマからの飛び。その後で一覧画像を目で見る。
- **同じ経路を別案（廃墟と復元、季節）で使うなら、経路上の戸口と通過点を経路のファイルに書いておく**。別案の側でその戸を開け、開いている半分の中央を通す。カメラは目の高さより、戸口では鴨居の下を通る高さに下げる。
- **Blender の連番を描き直していないと、UE と並べたときに差が出る**（モデルを直したのに古い Cycles の連番のまま、など）。並べる場面を作る前に、どちらの連番がどの版のモデルかを確かめ、古ければ報告に書く。
- **解説動画に UE 編を足すとき**: 場面は関数（進行 0〜1 → 画像）、文言は対訳表 1 つにまとめておくと、場面の追加・多言語版（環境変数で切り替え、出力名に `_en`）が書き出し直すだけで済む。英語は日本語より長くなるので、全場面のプレビューで見出しと数字の重なりを見てから本番を書き出す。

## 長い処理（Blender 側）
- Blender MCP の呼び出しには制限時間がある（数分で時間切れ）。長い処理は `scripts/blender/bl_bake_queue.py` のように `bpy.app.timers` で Blender の中に積み、状態をファイルに書いて外から見守る。止めたいときは、キューが実行するスクリプトのファイル名を変える。

## 季節違いのレベル（実例: 神社の春・夏・秋・冬）
- **元のレベルを複製して、季節ごとに 3 つだけ変える**（メッシュのアセットは共有）: ① 手続き的マテリアルの季節の子インスタンスをアクターのマテリアル上書きに設定、② 植物を季節の対応表で置き直す、③ 太陽の高さ・色温度・空。`EditorLoadingAndSavingUtils.save_map(world, 新しいパス)` は**コピーを書くだけで、開いているレベルは変わらない**（その後 `load_level` で開く）。
- **季節と雪は、マスターの空いているベクトル成分に入れる**（新しい入力ピンを足さず、Custom の HLSL を書き換えるだけで済み、既存のインスタンスは 0 のままで元の見た目）。雪は上向きの面にノイズで載せる。**上向きの判定は頂点法線に頼らない**: 石段や柵は頂点法線が傾いていて雪が半分しか載らなかった。切石・舗装・屋根は `cross(ddx(p), ddy(p))` の面法線、地形や岩は滑らかな頂点法線（面法線だと格子の四角い模様が出る）。
- **Megaplants の季節**: 春の桜は咲いている Yoshino Cherry をそのまま使う。新緑は葉のマテリアルの `BaseColor Tint`（黄緑 0.62/0.95/0.25、0.85/1.0/0.40）。**冬の落葉樹は、葉のスロットを「葉のアトラスの緑の画素を抜いたマスク材質」に差し替える**（`C.r > C.g * 0.95` の画素だけ残す → 小枝だけが残る。完全に隠す材質より木らしい）。夏は色を付けず、下草を 2 倍に。冬はシダとイラクサを置かない。
- **太陽が高い季節は空が紺色に沈む**（露出が明るい地面に合う）。`SkyAtmosphere` の `sky_luminance_factor` を 2〜3 に上げ、その分スカイライトを下げる。
- 道具が消えたときの代わり: 一時フォルダに入れた Python パッケージは OS の掃除で消える。numpy は Blender 同梱の Python にあり、画像の切り抜き・タイル並べは ffmpeg（`crop` / `scale` / `hstack` / `vstack`）でできる。
- **降る雪・舞う花びらは Niagara 無しでも作れる**（UE 5.8 では Python から Niagara のエミッターを組めなかった。5.9 は MCP の Niagara ツールで組める → 「動く物」の節）: 小さな四角形 1.4 万枚のメッシュを 1 つ作り（種の位置と乱数を UV1〜UV3 に入れる）、マテリアルの World Position Offset で各四角形を動かす。`pos = cam + (frac((seed − cam)/箱 + 0.5) − 0.5)·箱` で**カメラに付いてくる箱の中に折り返す**と、どこを歩いても空中が埋まる。落下は `seed.z −= 時間·速度`、揺れは sin、花びらは四角形の向きを時間で回す。雪はカメラに向ける。法線を真上に固定した Lit のマスク材質にすると、向きに関係なく日と空の光を受ける（Unlit の発光は露出に負けて灰色になる）。近すぎる粒（PixelDepth < 90 cm）はマスクで消す。頂点位置を使わないので、アクターを 300 m に拡大して境界だけ広げ、カリングされないようにする（FBX の Y 反転で境界が −Y 側へずれた: `get_actor_bounds` で確かめる）。影・Lumen・距離フィールド・当たり判定は切る。
- **レベルを複製した後でメッシュを作り直したら、配置は開いているレベルにしか効かない**: 各レベルを開いて配置し直し、季節のマテリアル上書きを掛け直す。
- **Megaplants の葉を材質で抜いても、遠くでは葉の塊のまま残る**（冬の枯れ木が、近くだけ枯れて遠くは黒い樹冠だった）。原因は Nanite の形状保持が「Voxelize」になっていること: 15 m ほど先から樹冠はボクセルで描かれ、ボクセルは不透明マスクも World Position Offset も無視する。直し方: メッシュを複製して `nanite_settings.shape_preservation = NONE` にし、`SkeletalMeshEditorSubsystem.set_lod_build_settings(m, 0, get_lod_build_settings(m, 0))` で作り直させる（1 本 20 秒ほど）。元のアセットは変えない。
- **木の雪**: 葉・樹皮の材質を「元のテクスチャ＋上向きの面に雪」の自作マスターに差し替える（頂点法線の z とワールド座標の低周波の模様で混ぜる）。使用中のマテリアルは `delete_asset` できず、その後の `create_asset` が None を返す: 既存のものは `delete_all_material_expressions` で空にして作り直す。
- **曇り空**: `SkyAtmosphere` の Mie 散乱を 100 倍近く（0.35）、異方性 0.45 にすると、太陽が拡散して空が乳白色になる。空の明るさは `sky_luminance_factor`（8）、地面の明るさはスカイライト（4）で別々に合わせ、太陽の `light_source_angle` を 12° にして影を柔らかくする。
- **空が紺色に沈むのを直す本当のつまみ**: スカイライトがリアルタイムキャプチャだと、`sky_luminance_factor` を上げても環境光が一緒に明るくなり、自動露出が打ち消して見た目の空は変わらない。**空の明るさ係数を上げた分だけスカイライトの強さを下げる**（積を一定に。実例: 係数 2→6、スカイライト 20→6.5）。天頂が暗いのは Rayleigh 散乱の倍率（既定 0.0331）を 0.04〜0.055 に上げる。
- **季節ごとの空**: ボリューメトリッククラウドの材質は、エンジンのインスタンス `m_SimpleVolumetricCloud_Inst` の子にする（マスター直下の子インスタンスは雲が描かれなかった）。効くつまみは `Cloud_GlobalCoverage`（−0.2 前後、大きいほど多い）、`Cloud_GlobalDensity`、`Layout_CloudGlobalScale`（小さいほど細かい雲）、コンポーネントの雲底高度と層の厚さ。太陽の `cast_cloud_shadows` を切っておくと、雲が太陽にかかっても直射が消えない。雲の白さは太陽の `cloud_scattered_luminance_scale`。未保存の変更があるレベルからは `load_level` で切り替えられない（先に保存する）。

