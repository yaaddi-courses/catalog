"""Re-capture every guide screenshot from the Android emulator/device connected over adb.

Reads guide_shots.json, drives the installed app, and writes each PNG to
tools/site_assets/img/guide/. A step that cannot find its text, or a screen that
does not contain the shot's expect_text (which also proves the app is in English),
stops the run with a non-zero exit: an old image is never silently kept.

Usage: python tools/guide/capture_guide_shots.py [--adb PATH] [--serial emulator-5554] [--only learn-map.png]
"""
import argparse
import json
import os
# adb only, fixed argument lists, never a shell
import subprocess  # nosec B404
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "site_assets" / "img" / "guide"
OCR = RapidOCR()
OUT_WIDTH = 540  # half of 1080: sharp on phones, small on the wire


def default_adb() -> str:
    sdk = os.environ.get("ANDROID_HOME") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    return str(Path(sdk) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))


class Device:
    def __init__(self, adb: str, serial: str | None):
        self.base = [adb] + (["-s", serial] if serial else [])

    def run(self, *args: str, binary: bool = False) -> bytes | str:
        done = subprocess.run([*self.base, *args], capture_output=True, check=True)  # nosec B603
        return done.stdout if binary else done.stdout.decode("utf-8", "replace")

    def read_screen(self) -> list[tuple[str, tuple[int, int]]]:
        """OCR the screen: [(text, center)]. uiautomator is unusable here (the app never goes idle)."""
        result, _ = OCR(np.array(self.screenshot()))
        return [(text, (int(sum(p[0] for p in box) / 4), int(sum(p[1] for p in box) / 4))) for box, text, _ in result or []]

    def find_center(self, text: str, top: bool = False) -> tuple[int, int] | None:
        hits = [c for t, c in self.read_screen() if t.strip().lower() == text.lower()]
        # Default: lowest on screen (the tab bar / a bottom button); top=True: highest.
        return (min if top else max)(hits, key=lambda c: c[1], default=None)

    def has_text(self, text: str) -> bool:
        return any(text.lower() in t.lower() for t, _ in self.read_screen())

    def tap(self, x: int, y: int) -> None:
        self.run("shell", "input", "tap", str(x), str(y))

    def screenshot(self) -> Image.Image:
        return Image.open(BytesIO(self.run("exec-out", "screencap", "-p", binary=True))).convert("RGB")


def do_step(dev: Device, step: dict, size: list[int]) -> None:
    if "tap_text_if" in step:  # optional: get back to a known screen, no failure if already there
        center = dev.find_center(step["tap_text_if"])
        if center:
            dev.tap(*center)
    elif "tap_text" in step:
        center = dev.find_center(step["tap_text"], top=step.get("pick") == "top")
        if center is None:
            raise SystemExit(f"FAIL: text {step['tap_text']!r} not on screen")
        dev.tap(*center)
    elif "tap" in step:
        dev.tap(*step["tap"])
    elif "swipe_up" in step:
        w, h = size
        for _ in range(step["swipe_up"]):
            dev.run("shell", "input", "swipe", str(w // 2), str(int(h * 0.75)), str(w // 2), str(int(h * 0.4)), "500")
            time.sleep(0.8)
    elif "swipe_down" in step:
        w, h = size
        for _ in range(step["swipe_down"]):
            dev.run("shell", "input", "swipe", str(w // 2), str(int(h * 0.3)), str(w // 2), str(int(h * 0.8)), "300")
            time.sleep(0.5)
    elif step.get("back"):
        dev.run("shell", "input", "keyevent", "4")
    elif "wait" in step:
        time.sleep(step["wait"])
    else:
        raise SystemExit(f"FAIL: unknown step {step!r}")
    time.sleep(0.6)


def ensure_root(dev: Device) -> None:
    """Back out of any leftover screen or window until the bottom tab bar is visible."""
    for _ in range(4):
        if dev.find_center("Settings") is not None:
            return
        dev.run("shell", "input", "keyevent", "4")
        time.sleep(1)
    raise SystemExit("FAIL: could not get back to the tab bar")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default=default_adb())
    parser.add_argument("--serial")
    parser.add_argument("--only", action="append", help="capture just this file name (repeatable)")
    args = parser.parse_args()

    manifest = json.loads((HERE / "guide_shots.json").read_text(encoding="utf-8"))
    dev = Device(args.adb, args.serial)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shots = [s for s in manifest["shots"] if not args.only or s["file"] in args.only]
    for shot in shots:
        ensure_root(dev)
        for step in shot["steps"]:
            do_step(dev, step, manifest["device_size"])
        if not dev.has_text(shot["expect_text"]):
            raise SystemExit(f"FAIL: {shot['file']}: expected text {shot['expect_text']!r} not on screen")
        img = dev.screenshot()
        img = img.resize((OUT_WIDTH, round(img.height * OUT_WIDTH / img.width)), Image.LANCZOS)
        img.save(OUT_DIR / shot["file"], optimize=True)
        for step in shot.get("cleanup", []):
            do_step(dev, step, manifest["device_size"])
        print(f"ok  {shot['file']}")
    print(f"captured {len(shots)} screenshot(s) into {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
