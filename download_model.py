"""Downloads the Cohere Transcribe Arabic Q8 model (2.41 GB, Apache-2.0) into models\\.

The model is stored in this repository's GitHub release as 2 parts (GitHub allows at most
2 GB per file). They are downloaded straight into one file, checked against the SHA-256
below, and renamed when complete. If GitHub is unavailable it continues from the model's
official Hugging Face page instead (same bytes, same checksum).

Safe to run again: it skips a finished download and resumes an interrupted one.
  python download_model.py          GitHub release, Hugging Face as fallback
  python download_model.py --hf     Hugging Face only
"""
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

NAME = "cohere-transcribe-arabic-07-2026-Q8_0.gguf"
SIZE = 2410655136
SHA256 = "910de5c9c57f9fd8a280e1701f9cd96f63768878c1ca9e4ecf23638a5e0fef16"
GH = "https://github.com/mooo-9/cohere-arabic-asr/releases/download/model-v1/"
PARTS = [(GH + NAME + ".001", 1205327568), (GH + NAME + ".002", 1205327568)]
HF = "https://huggingface.co/handy-computer/cohere-transcribe-arabic-07-2026-gguf/resolve/main/" + NAME

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "models", NAME)
PART = DST + ".part"
CHUNK = 1 << 20


def source(have: int, use_hf: bool):
    """URL to fetch next, the offset inside it, and how many bytes that source covers from there."""
    if use_hf:
        return HF, have, SIZE - have
    start = 0
    for url, n in PARTS:
        if have < start + n:
            return url, have - start, start + n - have
        start += n
    raise ValueError("already complete")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for buf in iter(lambda: f.read(8 << 20), b""):
            h.update(buf)
    return h.hexdigest()


def main() -> int:
    if os.path.isfile(DST) and os.path.getsize(DST) == SIZE:
        print(f"Model already downloaded: {DST}")
        return 0
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    use_hf, fails = "--hf" in sys.argv, 0
    print("  from " + ("Hugging Face" if use_hf else "GitHub release"))
    while True:
        have = os.path.getsize(PART) if os.path.exists(PART) else 0
        if have >= SIZE:
            break
        url, offset, want = source(have, use_hf)
        req = urllib.request.Request(url, headers={"Range": f"bytes={offset}-", "User-Agent": "cohere-arabic-asr-setup"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if offset and r.status != 206:
                    raise RuntimeError("server does not support resuming")
                last = time.time()
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
            if e.code in (403, 404) and not use_hf:
                print(f"\n  GitHub copy not available (HTTP {e.code}); continuing from Hugging Face.")
                use_hf = True
                continue
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
