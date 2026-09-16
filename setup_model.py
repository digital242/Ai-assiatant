"""One-command Vosk model installer for Sumo.

Run this once, from the project root, with your virtualenv active:

    python setup_model.py

It downloads the vosk-model-small-en-us-0.15 model (~40 MB), unzips it into the
``models/`` folder, fixes the common "folder nested inside a folder of the same
name" problem, and verifies the result -- so you don't have to do any of that by
hand. Safe to re-run: if the model is already installed correctly it just says so
and exits.

Works the same on Windows and macOS. Uses only the Python standard library, so
there is nothing extra to install.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODELS_DIR = "models"
TARGET_DIR = os.path.join(MODELS_DIR, MODEL_NAME)
# The three folders that must exist directly inside the model dir for it to work.
REQUIRED_SUBDIRS = ("am", "conf", "graph")


def _looks_valid(path: str) -> bool:
    return os.path.isdir(path) and all(
        os.path.isdir(os.path.join(path, sub)) for sub in REQUIRED_SUBDIRS
    )


def _report_progress(block_num, block_size, total_size):
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    pct = min(100, downloaded * 100 // total_size)
    mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    sys.stdout.write(f"\r  Downloading... {pct:3d}%  ({mb:5.1f} / {total_mb:.1f} MB)")
    sys.stdout.flush()


def main() -> int:
    print(f"Sumo model setup: {MODEL_NAME}\n")

    # 0) Already installed?
    if _looks_valid(TARGET_DIR):
        print(f"[done] Model already installed at: {TARGET_DIR}")
        print("You're all set. Run:  python run.py")
        return 0

    os.makedirs(MODELS_DIR, exist_ok=True)

    # 1) Download to a temp file.
    tmp_zip = os.path.join(tempfile.gettempdir(), f"{MODEL_NAME}.zip")
    print(f"Fetching {MODEL_URL}")
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp_zip, _report_progress)
        print()  # newline after the progress line
    except Exception as exc:  # noqa: BLE001
        print(f"\n[error] Download failed: {exc}")
        print(
            "  Check your internet connection and try again. If it keeps failing,\n"
            "  download this file in a browser and unzip it into the models folder\n"
            f"  manually (see README step 3):\n    {MODEL_URL}"
        )
        return 1

    # 2) Extract into models/ (into a temp subfolder first so we can normalize).
    extract_root = os.path.join(MODELS_DIR, "_extract_tmp")
    if os.path.isdir(extract_root):
        shutil.rmtree(extract_root)
    print("  Unzipping...")
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(extract_root)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Unzip failed: {exc}")
        shutil.rmtree(extract_root, ignore_errors=True)
        return 1
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass

    # 3) Find the actual model folder inside the extraction (handles nesting).
    source = None
    if _looks_valid(extract_root):
        source = extract_root
    else:
        for entry in os.listdir(extract_root):
            candidate = os.path.join(extract_root, entry)
            if _looks_valid(candidate):
                source = candidate
                break

    if source is None:
        print("[error] Couldn't find a valid model inside the download.")
        shutil.rmtree(extract_root, ignore_errors=True)
        return 1

    # 4) Move it into place at models/vosk-model-small-en-us-0.15.
    if os.path.isdir(TARGET_DIR):
        shutil.rmtree(TARGET_DIR)
    shutil.move(source, TARGET_DIR)
    shutil.rmtree(extract_root, ignore_errors=True)

    # 5) Verify.
    if _looks_valid(TARGET_DIR):
        print(f"\n[done] Model installed at: {TARGET_DIR}")
        print("You're all set. Run:  python run.py")
        return 0

    print("[error] Something went wrong -- the installed folder doesn't look right.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
