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
workflow steps. Project-specific inputs, configuration, runs, exports, and logs are
kept under each mode's runtime project folder.

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
    D[Step 4 ROI / Target Area\nDraw ROI and allowed generation areas]
    E[Step 5 Prompt\nChoose final input groups and edit prompt]
    F[Step 6 Model Parameters\nModel, quality, size, output count, run name]
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
- Duplicating a project copies its project state and class workspace artifacts so the
  new card opens with the same existing content.
- Homepage project cards use green for defect projects and blue for food projects.
- Cards keep a fixed position: selecting or opening a project never reorders them.
- The currently selected project card is outlined with a darker shade of its own mode
  color (a deeper green for defect, a deeper blue for food) instead of a red border.
- Project names must be unique.
- Reopening a project returns to the mode homepage while preserving completed-step state and
  existing artifacts.

### Step 2: Data Upload

- Import source images through the file picker or drag-and-drop.
- Uploaded originals are stored under:

```text
modes/defect/project_defect/<project_name>/data/00_raw_images/<class_name>/
modes/food/project_food/<project_name>/data/00_raw_images/<class_name>/
```

### Step 3: Crop / Use Original

- Either use original images directly or crop fixed-size inputs.
- Crop width and height are UI input dimensions for preparing downstream inputs.
- Existing generation runs and exports are preserved when adding more inputs.
- Prepared inputs are stored under:

```text
modes/defect/project_defect/<project_name>/data/01_inputs/<class_name>/images/
modes/food/project_food/<project_name>/data/01_inputs/<class_name>/images/
```

### Step 4: ROI / Target Area

- Draw one or more ROI rectangles for original defect locations.
- Draw Target Area regions where new defects may be generated.
- Target Area supports rectangle and polygon drawing.
- In selection mode, ROI and rectangular Target Area boxes can be resized with corner
  and edge handles.
- Step 3 auto-saves region files and masks after edits.
- ROI masks and Target Area masks are stored under:

```text
modes/defect/project_defect/<project_name>/data/01_inputs/<class_name>/masks/
modes/defect/project_defect/<project_name>/data/01_inputs/<class_name>/target_area_masks/
modes/defect/project_defect/<project_name>/data/01_inputs/<class_name>/regions/
modes/food/project_food/<project_name>/data/01_inputs/<class_name>/target_area_masks/
modes/food/project_food/<project_name>/data/01_inputs/<class_name>/regions/
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

- Choose the final image groups used for generation.
- Use Ctrl/Shift multi-select; the UI limits a batch to at most 16 groups.
- Edit a custom prompt or apply a template.
- The final prompt is no longer combined with ROI / Target Area coordinate text. ROI and Target Area positions are provided visually through a second annotation-reference input image during generation.
- Prompt configuration is stored under:

```text
modes/defect/project_defect/<project_name>/configs/classes/<class_name>/prompt.txt
modes/food/project_food/<project_name>/configs/classes/<class_name>/prompt.txt
```

### Step 6: Model Parameters

Available models:

- `gpt-image-2`
- `gpt-image-1.5`
- `gpt-image-1`
- `gpt-image-1-mini`

The UI validates output size rules before generation. For `gpt-image-2`, output
dimensions must satisfy the current app checks, including 16-pixel multiples, valid
aspect ratio, and supported total pixel range.

### Step 7: Aggregate

- Review the selected project, class, image groups, ROI/Target Area coverage, prompt,
  model, quality, size, output count, and run name.
- The aggregate log is written under the current project logs folder.

### Step 8: Run Generation

- Executes `scripts/batch_from_folders.py`, which calls `scripts/run_gpt_image2.py` with `--workflow reference-guided-edit`.
- Uses the shared API key saved from the mode homepage.
- Sends two images to GPT Image: Image 1 is the clean original; Image 2 is an ROI / Target Area annotation reference.
- Does not send ROI / Target Area coordinates in the prompt and does not use the ROI / Target Area as an OpenAI API mask in this default UI workflow. The stored masks are used only to render Image 2.
- Shows live logs and generation progress.
- Generation outputs are written under (there is no longer a `<class_name>` folder layer):

```text
modes/defect/project_defect/<project_name>/runs/<run_name>/
modes/food/project_food/<project_name>/runs/<run_name>/
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
- The `Export 規劃` panel holds everything: an `匯出範圍` multi-select dropdown, a refresh
  button, a `確認` (Confirm) button, the `Export` button, and a `打包成 .zip` checkbox
  (checked by default). The COCO / YOLO format checkboxes and their export functionality
  have been removed.
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

Runtime artifacts are intentionally ignored by Git:

- `project/`
- `modes/defect/project_defect/`
- `modes/food/project_food/`
- `logs/`
- `configs/`
- `runs/`
- `exports/`
- zip/tar archives
- `.env` and key files

This keeps uploaded images, generated outputs, masks, logs, API keys, and temporary
exports out of source control.

The main source files are:

```text
launch_ui.py                  # UI launcher
ui_gpt_defect/app.py          # Single-window mode selector / mode host
modes/defect/ui_gpt_defect/   # Defect workflow UI
modes/defect/scripts/         # Defect generation/export helpers
modes/defect/tools/           # Defect image/mask editor utilities
modes/food/ui_gpt_defect/     # Food workflow UI
modes/food/scripts/           # Food generation/export helpers
modes/food/tools/             # Food image/mask editor utilities
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
