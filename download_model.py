"""Downloads the Cohere Transcribe Arabic Q8 model (2.41 GB, Apache-2.0) into models\\.

Source: the model's official GGUF page on Hugging Face
  https://huggingface.co/handy-computer/cohere-transcribe-arabic-07-2026-gguf
The file is checked against the SHA-256 below before it is used.

Already have the model? Put the .gguf file in models\\ (any name), or set COHERE_GGUF to its
full path, and nothing is downloaded. A copy downloaded by the Handy app is found automatically.

Safe to run again: it skips a finished download and resumes an interrupted one.
"""
import glob
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

NAME = "cohere-transcribe-arabic-07-2026-Q8_0.gguf"
SIZE = 2410655136
SHA256 = "910de5c9c57f9fd8a280e1701f9cd96f63768878c1ca9e4ecf23638a5e0fef16"
URL = "https://huggingface.co/handy-computer/cohere-transcribe-arabic-07-2026-gguf/resolve/main/" + NAME

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "models", NAME)
PART = DST + ".part"
CHUNK = 1 << 20


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for buf in iter(lambda: f.read(8 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def existing_model():
    """A model the user already has: COHERE_GGUF, any .gguf in models\\, or the copy the Handy app downloaded."""
    env = os.environ.get("COHERE_GGUF")
    if env and os.path.isfile(env):
        return env
    found = sorted(glob.glob(os.path.join(HERE, "models", "*Q8_0.gguf"))) + sorted(
        glob.glob(os.path.join(HERE, "models", "*.gguf")))
    found += glob.glob(os.path.expandvars(
        r"%USERPROFILE%\.cache\huggingface\hub\models--handy-computer--cohere-transcribe-arabic-07-2026-gguf"
        r"\snapshots\*\*Q8_0.gguf"))
    return next((f for f in found if os.path.getsize(f) > 100_000_000), None)


def main() -> int:
    have_it = existing_model()
    if have_it:
        print(f"Using the model you already have: {have_it}")
        return 0
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    fails = 0
    while True:
        have = os.path.getsize(PART) if os.path.exists(PART) else 0
        if have >= SIZE:
            break
        req = urllib.request.Request(URL, headers={"Range": f"bytes={have}-", "User-Agent": "cohere-arabic-asr-setup"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:
                    raise RuntimeError("server does not support resuming")
                want, last = SIZE - have, time.time()
                with open(PART, "ab") as f:
                    while want > 0:
                        buf = r.read(min(CHUNK, want))
                        if not buf:
                            break
                        f.write(buf)
                        want -= len(buf)
                        have += len(buf)
                        if time.time() - last > 1:
                            last = time.time()
                            print(f"\r  {have / 1e9:.2f} / {SIZE / 1e9:.2f} GB ({100 * have / SIZE:.0f}%)   ",
                                  end="", flush=True)
            fails = 0
        except urllib.error.HTTPError as e:
            fails += 1
            print(f"\n  Download error (HTTP {e.code}), retrying in 5 s... [{fails}]")
        except Exception as e:  # network drop, timeout: resume from where it stopped
            fails += 1
            print(f"\n  Connection problem ({e}), resuming in 5 s... [{fails}]")
        if fails:
            if fails >= 100:
                print("\nDownload did not finish. Run setup.cmd again to continue.")
                return 1
            time.sleep(5)
    print(f"\r  {SIZE / 1e9:.2f} / {SIZE / 1e9:.2f} GB (100%)   \n  Checking the file...")
    if os.path.getsize(PART) != SIZE or sha256(PART) != SHA256:
        os.remove(PART)
        print("  The downloaded file is damaged and was deleted. Run setup.cmd again.")
        return 1
    os.replace(PART, DST)
    print(f"Model ready: {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
