#!/usr/bin/env python3
"""Export generated GPT GenImage outputs as separated YOLO and COCO datasets.

Auto-annotation is intentionally disabled.

Folder layout when both formats are enabled:

<export_root>/
  yolo/
    images/
    labels/            # empty .txt files are written for compatibility
    data.yaml
  coco/
    images/
    annotations/coco.json   # annotations is always []
  export_manifest.json

This exporter only organizes generated images and dataset metadata.  It does
not infer object boxes from Target Area, masks, image differences, placement
records, or any other heuristic.  If labels are needed, annotate them manually
or provide a separate verified annotation pipeline.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def unique_name(base: str, used: set[str]) -> str:
    base = re.sub(r"[\\/:*?\"<>|]+", "_", str(base)).strip() or "image.png"
    if base not in used:
        used.add(base)
        return base
    stem = Path(base).stem
    suffix = Path(base).suffix
    i = 1
    while True:
        candidate = f"{stem}_{i:03d}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def resolve_path(raw: Any, *, base_dirs: list[Path]) -> Path | None:
    if raw is None:
        return None
    s = str(raw).strip().strip('"')
    if not s:
        return None
    normalized = s.replace("\\", "/")
    p = Path(normalized)
    candidates: list[Path] = [p]
    if not p.is_absolute():
        for base in base_dirs:
            candidates.append(base / normalized)
            candidates.append(base / normalized.lstrip("/"))
    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            continue
    return None


def infer_project_dir(runs_root: Path, class_name: str, root: Path) -> Path | None:
    rr = runs_root.resolve()
    # UI uses <project_dir>/runs/<class_name>
    if rr.name == class_name and rr.parent.name == "runs":
        return rr.parent.parent
    # Or <project_dir>/runs/<class>/<run>
    if rr.parent.name == class_name and rr.parent.parent.name == "runs":
        return rr.parent.parent.parent
    # Legacy fallback: repo root itself can contain data/ and runs/.
    if (root / "data" / "01_inputs" / class_name).exists():
        return root
    return None


def meta_group_key(path: Path) -> str:
    meta = read_json(path)
    batch = str(meta.get("batch_run_name") or "").strip()
    if batch:
        return batch
    parent = path.parent.name
    if "_seed" in parent:
        return parent.split("_seed", 1)[0]
    return parent


def meta_matches_run(path: Path, run_name: str) -> bool:
    if not run_name:
        return False
    meta = read_json(path)
    batch = str(meta.get("batch_run_name") or "").strip()
    parent = path.parent.name
    grandparent = path.parent.parent.name if path.parent.parent else ""
    return batch == run_name or parent == run_name or grandparent == run_name or parent.startswith(run_name + "_")


def resolve_output_path(raw: Any, meta_path: Path, root: Path, project_dir: Path | None) -> Path | None:
    bases = [meta_path.parent, root]
    if project_dir is not None:
        bases.append(project_dir)
    path = resolve_path(raw, base_dirs=bases)
    if path and path.suffix.lower() in SUPPORTED_EXTS and path.is_file():
        return path
    return None


def collect_final_outputs(meta: dict[str, Any]) -> list[Any]:
    outputs = meta.get("final_outputs") or meta.get("outputs") or []
    return outputs if isinstance(outputs, list) else []


def export_image_name(meta_path: Path, out_path: Path) -> str:
    group = meta_group_key(meta_path)
    parent = meta_path.parent.name
    # Current UI scheme stores the output file as <child-run-name>.<ext>, so the
    # file base already equals its child-run folder name; don't duplicate it.
    if parent == out_path.stem:
        if group and group != parent:
            return f"{group}_{out_path.name}"
        return out_path.name
    if group and group != parent:
        return f"{group}_{parent}_{out_path.name}"
    return f"{parent}_{out_path.name}"


def main() -> None:
    root = project_root()
    p = argparse.ArgumentParser(description="Export GPT Image class runs without auto annotations.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--class-name", help="Class name for folder/config/output naming")
    group.add_argument("--defect-type", help="Backward-compatible alias for --class-name")
    p.add_argument("--runs-root", type=Path, default=None)
    p.add_argument("--export-root", type=Path, default=None)
    p.add_argument("--latest-only", action="store_true")
    p.add_argument("--run-name", default="", help="Export only the run/batch with this name. UI child runs are grouped by batch_run_name.")
    p.add_argument("--max-images", type=int, default=None, help="Maximum number of final generated images to export.")
    p.add_argument("--copy-images", action="store_true")
    p.add_argument("--coco", action="store_true")
    p.add_argument("--yolo", action="store_true")
    p.add_argument("--class-id", type=int, default=0)
    args = p.parse_args()

    class_name = (args.class_name or args.defect_type).strip()
    runs_root = args.runs_root or root / "runs" / class_name
    if not runs_root.exists():
        raise SystemExit(f"Runs folder not found: {runs_root}")
    project_dir = infer_project_dir(runs_root, class_name, root)

    all_metas = sorted(runs_root.rglob("metadata.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    metas = all_metas
    run_name = str(args.run_name or "").strip()
    if run_name:
        metas = [m for m in all_metas if meta_matches_run(m, run_name)]
    elif args.latest_only and all_metas:
        latest_group = meta_group_key(all_metas[0])
        metas = [m for m in all_metas if meta_group_key(m) == latest_group]

    if not metas:
        raise SystemExit(f"No metadata.json found under: {runs_root}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = ensure_dir(args.export_root or root / "exports" / class_name / timestamp)

    yolo_dir = export_dir / "yolo"
    yolo_images_dir = yolo_dir / "images"
    yolo_labels_dir = yolo_dir / "labels"
    coco_dir = export_dir / "coco"
    coco_images_dir = coco_dir / "images"
    coco_ann_dir = coco_dir / "annotations"
    if args.yolo:
        ensure_dir(yolo_images_dir)
        ensure_dir(yolo_labels_dir)
    if args.coco:
        ensure_dir(coco_images_dir)
        ensure_dir(coco_ann_dir)

    category_id = int(args.class_id)
    categories = [{"id": category_id, "name": class_name, "supercategory": "class"}]
    coco = {
        "info": {
            "description": "GPT GenImage export; auto annotation disabled",
            "date_created": timestamp,
        },
        "images": [],
        "annotations": [],
        "categories": categories,
    }

    image_id = 1
    used_names: set[str] = set()
    copied = 0
    skipped_outputs = 0

    for meta_path in metas:
        if args.max_images is not None and copied >= max(0, int(args.max_images)):
            break
        meta = read_json(meta_path)
        for out in collect_final_outputs(meta):
            if args.max_images is not None and copied >= max(0, int(args.max_images)):
                break
            out_path = resolve_output_path(out, meta_path, root, project_dir)
            if not out_path:
                skipped_outputs += 1
                continue
            try:
                with Image.open(out_path) as img:
                    width, height = img.size
            except Exception:
                skipped_outputs += 1
                continue

            safe_name = unique_name(export_image_name(meta_path, out_path), used_names)

            if args.yolo and args.copy_images:
                shutil.copy2(out_path, yolo_images_dir / safe_name)
            if args.coco and args.copy_images:
                shutil.copy2(out_path, coco_images_dir / safe_name)

            if args.coco:
                coco["images"].append({
                    "id": image_id,
                    "file_name": f"images/{safe_name}",
                    "width": width,
                    "height": height,
                })

            if args.yolo:
                # Auto annotation is disabled, so each generated image receives
                # an empty label file.  The user can manually fill or replace
                # these files with verified object boxes later.
                (yolo_labels_dir / f"{Path(safe_name).stem}.txt").write_text("", encoding="utf-8")

            copied += 1
            image_id += 1

    if args.coco:
        write_json(coco_ann_dir / "coco.json", coco)
    if args.yolo:
        (yolo_dir / "data.yaml").write_text(
            f"path: {yolo_dir.as_posix()}\ntrain: images\nval: images\nnames:\n  {category_id}: {class_name}\n",
            encoding="utf-8",
        )

    manifest = {
        "class_name": class_name,
        "defect_type": class_name,
        "runs_root": str(runs_root),
        "project_dir": str(project_dir) if project_dir else None,
        "metadata_files": [str(m) for m in metas],
        "export_dir": str(export_dir),
        "layout": "separated_yolo_coco",
        "yolo_dir": str(yolo_dir) if args.yolo else None,
        "coco_dir": str(coco_dir) if args.coco else None,
        "images_exported": copied,
        "annotated_images": 0,
        "annotations_exported": 0,
        "skipped_outputs": skipped_outputs,
        "coco": bool(args.coco),
        "yolo": bool(args.yolo),
        "copy_images": bool(args.copy_images),
        "latest_only": bool(args.latest_only),
        "run_name": run_name,
        "max_images": args.max_images,
        "annotation_policy": "auto_annotation_disabled; labels are intentionally empty and coco.annotations is intentionally []",
    }
    write_json(export_dir / "export_manifest.json", manifest)
    print(f"[INFO] images_exported={copied}")
    print("[INFO] auto_annotation=disabled")
    print("[INFO] annotated_images=0")
    print("[INFO] annotations_exported=0")
    print(f"[DONE] export_dir={export_dir}")


if __name__ == "__main__":
    main()
