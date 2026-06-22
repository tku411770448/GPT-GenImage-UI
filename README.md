# GPT GenImage UI

`GPT GenImage UI` is a PySide6 desktop workflow for preparing image-generation
inputs, calling the OpenAI GPT Image API, and exporting generated results as image
datasets.

The launcher opens a single desktop window. `Step 0` is the mode selector inside
that same window:

- `Gen Defect` opens the defect workflow.
- `Gen Food` opens the food workflow.

After a mode is selected, the same top-level window is reused for that mode's
guided workflow. The mode homepage is shown as `Step 1`, followed by the remaining
workflow steps. Project-specific inputs, runs, and state are kept under each mode's
runtime project folder at `modes/<mode>/project/<project_name>/`. Key execution
nodes and any error/crash diagnostics are written to a single shared log file at the
repo root, `log.txt`.

---

## 1. Install

### Windows

```bat
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Required packages are listed in `requirements.txt` and include:

- `PySide6` for the desktop UI
- `openai` and `python-dotenv` for GPT Image API calls
- `pillow`, `numpy`, and `opencv-python` for image and mask processing

---

## 2. Launch

```bash
python launch_ui.py
```

Convenience launchers are also available:

```bat
quick_start_ui_windows.bat
```

```bash
bash quick_start_ui_linux.sh
```

If the launcher reports that `PySide6` or Qt cannot be imported, activate the same
virtual environment where `requirements.txt` was installed and run `python launch_ui.py`
again.

---

## 3. Current Workflow

```mermaid
flowchart TD
    Z[Step 0 Mode Selection\nChoose Gen Defect or Gen Food]
    A[Step 1 Homepage / Project Management\nCreate/open/duplicate/delete project\nSet shared OpenAI API key\nEnter 專案名稱, 生成圖片物件的名稱, 模式]
    B[Step 2 Data Upload\nImport or drag source images]
    C[Step 3 Crop / Use Original\nChoose original images or crop fixed-size inputs]
    D[Step 4 ROI / Target Area\nDraw ROI and Target Area annotations]
    E[Step 5 Prompt\nEdit the 輸入指令 prompt that is sent]
    F[Step 6 Model Parameters\nModel, quality, size, output count, 輸出資料夾名稱]
    G[Step 7 Aggregate\nReview settings before generation]
    H[Step 8 Run Generation\nExecute batch generation and monitor logs]
    I[Step 9 Export\nSelect runs, preview, export images to a chosen path (optional .zip)]

    Z --> A --> B --> C --> D --> E --> F --> G --> H --> I
```

The defect mode shows the full `Step 1` through `Step 9` workflow. The food mode
uses the same single-window mode selector and keeps its own visible workflow, with
food-specific target-area handling. Internally, the mode applications keep older
step indexes for compatibility with existing project state files.

---

## 4. Step Details

### Step 0: Mode Selection

- Choose `Gen Defect` or `Gen Food`.
- The selected mode is loaded into the same window instead of opening a second
  workflow window.

### Step 1: Homepage / Project Management

- The Create Project dialog has three fields: `專案名稱` (project name), `生成圖片物件的名稱`
  (the name of the object to generate), and `模式` (mode).
- `生成圖片物件的名稱` becomes the class name: it is filled into the `{class_name}` prompt
  template variable in Step 5 (Prompt 編輯) for both modes and is used as the internal
  data/config folder name. If left blank it defaults to the project name.
- Save or replace the shared `OPENAI_API_KEY` used by all projects.
- Open, duplicate, or delete existing project cards.
- Duplicating a project copies its settings and uploaded source images but NOT the
  generated outputs (`runs/` and `exports/`). Each project keeps an independent run
  counter, so a duplicate starts fresh at `run1` instead of inheriting the source
  project's runs.
- Homepage project cards use green for defect projects and blue for food projects.
- Cards keep a fixed position: selecting or opening a project never reorders them.
- Selecting or switching a project keeps the page fixed: the project-card scroll
  position is preserved and the page does not jump.
- The currently selected project card is outlined with a darker shade of its own mode
  color (a deeper green for defect, a deeper blue for food) instead of a red border.
- Project names must be unique.
- Reopening a project returns to the mode homepage while preserving completed-step state and
  existing artifacts.

### Step 2: Data Upload

- Import source images through the file picker or drag-and-drop.
- Each newly uploaded image becomes the previewed image immediately: dragging images
  in one at a time always shows the most recently added image in the preview pane (no
  need to click its filename in the list). Dropping a folder previews the last image in
  that folder.
- Uploaded originals are stored directly inside each project's `data/` folder. The
  exact layout differs by mode (see below); there are no `00_raw_images/` or
  per-class subfolders:

```text
# Food: data/ is a flat folder holding the input images directly
modes/food/project/<project_name>/data/

# Defect: the clean originals go to data/raw_image/
modes/defect/project/<project_name>/data/raw_image/
```

### Step 3: Crop / Use Original

- Either use original images directly or crop fixed-size inputs.
- Crop width and height are UI input dimensions for preparing downstream inputs.
- Switching between the two source styles only prompts when it would discard existing
  work, and then actually clears the discarded products before continuing:
  - On a brand-new / clean project (no Step 4 inputs yet), pressing 『使用原始圖片』 or
    drawing the first crop runs silently with no confirmation dialog.
  - If cropped inputs already exist and you press 『使用原始圖片』, a dialog warns that the
    cropped inputs and any drawn ROI / Target Area will be cleared before the originals
    are copied in. Existing runs are preserved.
  - If original inputs already exist and you start cropping, a dialog warns that those
    originals and any drawn ROI / Target Area will be cleared before cropping begins;
    cropping only proceeds after you confirm. Existing runs are preserved.
- The right-hand input list (labelled `Step 4 輸入圖像` in both modes) always shows every
  crop together. It is not filtered by which uploaded thumbnail is selected: cropping any
  source adds its crops to the same combined list, and the just-made crop is auto-selected
  (so the middle canvas stays on the image you are cropping). These crops are the inputs
  carried into the next step.
- In the right-hand input list, hovering the list and scrolling the mouse wheel switches
  the selected image without clicking (wheel down = next image, wheel up = previous
  image); the middle crop-frame preview and the crop preview box both update to match.
- The input list has two delete buttons side by side: `刪除選取裁切圖` removes the selected
  inputs, and `刪除所有裁切圖` removes every input together with its ROI / Target Area
  annotations. Existing runs are preserved by both.
- Existing generation runs are preserved when adding more inputs.
- Cropping edits images IN PLACE inside `data/` (food) / `data/raw_image/` (defect);
  it does not create a separate `01_inputs/` tree. Prepared inputs therefore live under:

```text
# Food: cropped/original images stay in the flat data/ folder
modes/food/project/<project_name>/data/

# Defect: cropped/original clean images stay in data/raw_image/
modes/defect/project/<project_name>/data/raw_image/
```

### Step 4: ROI / Target Area

- Draw one or more ROI rectangles for original defect locations.
- Draw Target Area regions where new defects may be generated.
- Target Area supports rectangle and polygon drawing.
- In selection mode, ROI and rectangular Target Area boxes can be resized with corner
  and edge handles.
- This step auto-saves after edits. The ROI / Target Area geometry is stored in
  `project_state.json` (a `regions` map keyed by image stem); there are no separate
  `regions/`, `masks/`, or `target_area_masks/` files.
- For defect mode, saving also writes an annotation reference image into
  `data/reference_image/`: a copy of the raw image with the ROI drawn as a
  semi-transparent MAGENTA fill and the Target Area as a semi-transparent CYAN fill.
  The reference is paired one-to-one with its raw image by file stem and becomes
  Image 2 during generation:

```text
modes/defect/project/<project_name>/data/raw_image/        # Image 1: clean originals
modes/defect/project/<project_name>/data/reference_image/  # Image 2: ROI/Target Area annotation
```

Useful shortcuts in this step include:

- `R`: draw ROI
- `S`: select ROI
- `T`: draw rectangular Target Area
- `L`: draw polygon Target Area
- `Y`: select Target Area
- `A` / `D`: delete all / selected ROI
- `G` / `H`: delete all / selected Target Area
- `Up` / `Down`: switch image

### Step 5: Prompt

- The original `Prompt 編輯` layout is kept: the `引用組別` (group multi-select, with
  an `ALL` option), the `Prompt 來源設定` (custom / template mode + `套用模板到輸入指令`),
  and the `輸入指令` (prompt input) section. Their interaction logic is unchanged.
- Only the `實際傳送指令` (read-only preview) section has been removed; the `輸入指令`
  section now spans the full width below and uses an enlarged font.
- Use Ctrl/Shift multi-select in `引用組別`; a batch is limited to at most 16 groups.
  The chosen groups are the final inputs sent to generation (passed to the backend
  inline via `--selected-stems`; no stems file is written to disk).
- The prompt that is sent equals the `輸入指令` text exactly. It is no longer combined
  with ROI / Target Area coordinate text; for defect mode those positions are provided
  visually through the annotation-reference image (Image 2) during generation.
- The prompt actually sent for a run is recorded as `runs/<run_name>/prompt.txt`.

### Step 6: Model Parameters

Available models:

- `gpt-image-2`
- `gpt-image-1.5`
- `gpt-image-1`
- `gpt-image-1-mini`

The UI validates output size rules before generation. For `gpt-image-2`, output
dimensions must satisfy the current app checks, including 16-pixel multiples, valid
aspect ratio, and supported total pixel range.

The field that sets the output folder name is now labelled `輸出資料夾名稱` in the UI
(it was previously labelled `Run name`). It still controls the output folder name
under `runs/<run_name>/`; the internal state key is unchanged.

OpenAI pricing used for cost estimation is fetched live, with a built-in default
fallback; nothing is cached to disk.

### Step 7: Aggregate

- Review the selected project, class, ROI/Target Area coverage, prompt, model,
  quality, size, output count, and `輸出資料夾名稱`.
- The aggregate summary is stored inside the project's `project_state.json` (an
  `aggregate_summary` field). There is no per-project `logs/` folder.
- `project_state.json` also keeps a `run_history` field that accumulates EVERY run's
  record and final status (success / paused / failed / no-output), not just the most
  recent one. Records are separated by a fixed banner
  (`<<================================================>>`) so the full history stays
  readable. A record is appended each time a generation finishes.

### Step 8: Run Generation

- Both modes execute `scripts/batch_from_folders.py`, which calls
  `scripts/run_gpt_image2.py`:
  - Defect uses `--workflow reference-guided-edit`: the backend makes one OpenAI
    Image Edit API call per matched tuple of (raw image + its reference image +
    prompt). Image 1 is the clean original; Image 2 is the ROI / Target Area
    annotation reference. ROI / Target Area coordinates are not sent in the prompt
    and are not used as an OpenAI API mask; the geometry is conveyed only by Image 2.
  - Food uses `--workflow prompt-only-edit`: Image 1 is the input image plus the text
    prompt. There is no mask and no reference image.
- Uses the shared API key saved from the mode homepage.
- Shows live logs and generation progress.
- Graceful pause: the `停止目前程序` button is a PAUSE, not a kill. If an image's API
  call is already in flight, that image is allowed to finish (the API call and its
  cost are not wasted) and the next image is simply not started. While the current
  image is still being received, a `目前生成圖像尚在接收中...` dialog is shown; when that
  image returns and is saved, the dialog auto-closes and a message
  `現在生成至第 <N> 張，還剩 <M> 張尚未生成，已暫停` is shown. (There is no longer a long
  error-log dump on stop.) Mechanism: the UI sends a `STOP` line on the batch
  process's stdin, which it checks between images; no sentinel file is created and
  the process is not killed.
- Generation outputs are written under (there is no longer a `<class_name>` folder layer):

```text
modes/defect/project/<project_name>/runs/<run_name>/
modes/food/project/<project_name>/runs/<run_name>/
```

Each run folder contains only three things; all other intermediate artifacts (masks,
previews, per-call metadata, logs, per-image work folders) are discarded:

```text
runs/<run_name>/Gen_Images/                 # every generated image for this run
runs/<run_name>/generation_summary.xlsx     # per-image table (.csv fallback if openpyxl missing)
runs/<run_name>/prompt.txt                  # the prompt actually sent for this run
```

- `generation_summary.xlsx` has four columns: `原圖像名稱`, `生成圖像名稱`, `Total Token`,
  `Cost($USD)` — one row per generated image. Install `openpyxl` (in `requirements.txt`)
  to get a real `.xlsx`; without it the runner writes an equivalent `generation_summary.csv`.
- Each generated image file is named `<run_name>-<YYYY>-<MM>-<DD>-<HH>-<mm>-<counter>`:
  - The `YYYY-MM-DD-HH-mm` timestamp is the moment the generation step started. It is
    derived once per run (reused on resume by reading existing `Gen_Images` names) and
    stays identical for every image in that run.
  - `<counter>` starts at 1 and increases by one for each generated image, so names never
    repeat and previously generated images are never overwritten.
  - The seed value still drives local placement randomness internally but does not appear
    in the generated image file name.

### Step 9: Export

- Defect mode shows this page as `Step 9`; food mode shows its final export page as
  `Step 8` while keeping compatible internal state indexes.
- The `Export 規劃` panel holds everything: an `匯出範圍` multi-select dropdown, a `打包成 .zip`
  checkbox (checked by default), and the `確認` (Confirm) and `Export` buttons stacked
  vertically (Confirm on top, Export below) in the right column. The COCO / YOLO format
  checkboxes and the standalone refresh button have been removed; the run list refreshes
  automatically when the export step is opened.
- `匯出範圍` is a checkable multi-select dropdown. It lists every run in the project by
  name plus a `全部 runs（包含歷次 runs）` option. Checking `全部 runs` selects all runs and
  disables the individual options (a forbidden cursor is shown while hovering them);
  clicking a run toggles its checkbox.
- `確認` loads the selected runs' generated images into the left preview sidebar. A
  `生成圖像正在 loading...` message is shown while images load and dismisses automatically
  when finished.
- `Export` always opens a folder picker so you choose the destination path (whether or
  not `打包成 .zip` is ticked). It creates a folder named `<project_name>-<timestamp>`
  containing every image from the selected runs. When `打包成 .zip` is ticked, that folder
  is packed into `<project_name>-<timestamp>.zip` instead of being left loose.
- Export no longer writes into the project `exports/` folder; images are copied straight
  to the path you choose.

---

## 5. Project Files and Generated Artifacts

Runtime data lives under each mode's `modes/<mode>/project/` folder and is
intentionally ignored by Git (matched at any depth). Git also ignores:

- `project/` and `**/project/`
- `runs/` and `exports/`
- the single shared `log.txt` plus any stray `logs/` folders
- zip/tar archives
- `.env` and key files

This keeps uploaded images, generated outputs, the shared log, API keys, and
temporary exports out of source control.

A project folder contains EXACTLY these — no `configs/`, `exports/`, `logs/`, or
`_ui_state/`:

```text
modes/<mode>/project/<project_name>/
├── data/                       # input images (layout differs by mode, see Step 2)
├── runs/
│   └── <run_name>/
│       ├── Gen_Images/             # every generated image for this run
│       ├── generation_summary.xlsx # per-image table (.csv fallback if openpyxl missing)
│       └── prompt.txt              # the prompt actually sent for this run
└── project_state.json          # single source of truth for this project
```

`project_state.json` is the single source of truth for a project. It holds completed-step
state, the defect `regions` geometry map (keyed by image stem), and the
`aggregate_summary`. The old per-mode `_ui_state/ui_state.json` and the repo-root
`_launcher_state/launcher_state.json` have been removed and are no longer written.

Logging: key execution nodes (project created/opened, generation start/finish/pause)
and error/crash diagnostics are appended to a single shared `log.txt` at the repo
root. There is no longer a top-level `logs/` folder or per-project `logs/` folders.

There is no `configs/` folder anywhere; OpenAI pricing is fetched live with a built-in
default fallback and nothing is cached to disk.

The main source files are:

```text
launch_ui.py                  # UI launcher + single-window mode host (UnifiedMainWindow)
modes/defect/ui_gpt_defect/   # Defect workflow UI
modes/defect/scripts/         # Defect generation helpers (batch_from_folders, run_gpt_image2, verify_env)
modes/food/ui_gpt_food/       # Food workflow UI
modes/food/scripts/           # Food generation helpers (batch_from_folders, run_gpt_image2, verify_env)
```

---

## 6. Environment and Secrets

The UI stores the shared API key in `.env` as `OPENAI_API_KEY=...`.
The key preview shown in the UI is masked and should not be committed.

To verify Python syntax after code changes:

```bash
python -m compileall .
```

To inspect the current Git state before committing:

```bash
git status
git diff --stat
```
