#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INCLUDE = [
    "AGENTS.md",
    "START_HERE.md",
    "docs",
    "prompts",
    "templates",
    ".agents/skills",
]

def copy_item(src: Path, dst: Path):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def make_zip(source_dir: Path, zip_path: Path):
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            zf.write(path, path.relative_to(source_dir))

def main():
    parser = argparse.ArgumentParser(description="Build a handoff zip for downstream coding agents.")
    parser.add_argument("--project-name", required=True, help="Project slug, e.g. my-app")
    parser.add_argument("--output-dir", default="dist", help="Where to place the build artifacts")
    parser.add_argument("--include-src", action="store_true", help="Also include src/ and tests/ skeletons")
    args = parser.parse_args()

    out_dir = ROOT / args.output_dir
    stage_dir = out_dir / f"{args.project_name}-handoff"
    zip_path = out_dir / f"{args.project_name}-handoff.zip"

    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    includes = list(DEFAULT_INCLUDE)
    if args.include_src:
        includes.extend(["src", "tests"])

    for rel in includes:
        src = ROOT / rel
        if src.exists():
            copy_item(src, stage_dir / rel)

    # Add a minimal manifest so downstream agents know what this bundle is.
    manifest = stage_dir / "HANDOFF_MANIFEST.txt"
    manifest.write_text(
        "\\n".join([
            f"project_name={args.project_name}",
            "purpose=stable handoff for downstream coding agents",
            "required_read_order=START_HERE.md -> docs/01_reality_check.md -> docs/02_end_to_end_workflow.md -> AGENTS.md",
        ]),
        encoding="utf-8",
    )

    if zip_path.exists():
        zip_path.unlink()
    make_zip(stage_dir, zip_path)

    print(f"Built: {zip_path}")

if __name__ == "__main__":
    main()
