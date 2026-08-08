import os

os.environ["COQUI_TOS_AGREED"] = "1"

from TTS.api import TTS  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(BASE, "media")
MANIFEST = os.path.join(BASE, "build", "audio_manifest.txt")

SPEAKER = "Claribel Dervla"
LANGUAGE = "en"


def main():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    total = len(lines)

    os.makedirs(MEDIA_DIR, exist_ok=True)
    pending = []
    for line in lines:
        fname, text = line.split("\t", 1)
        out_path = os.path.join(MEDIA_DIR, fname)
        if os.path.exists(out_path):
            continue
        pending.append((fname, text, out_path))

    print(f"{len(pending)}/{total} audio files to generate.")
    if not pending:
        return

    print("Loading XTTS v2 model (one-time load)...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")

    for i, (fname, text, out_path) in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] generating: {fname} -- {text}")
        try:
            tts.tts_to_file(text=text, speaker=SPEAKER, language=LANGUAGE, file_path=out_path)
        except Exception as e:
            print(f"  FAILED: {fname}: {e}")


if __name__ == "__main__":
    main()
