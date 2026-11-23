"""Local OpenAI-compatible speech-to-text server for Cohere Transcribe Arabic.

Runs the Q8 GGUF (models/) through the transcribe.cpp engine (runtime/transcribe.dll,
Vulkan GPU with CPU fallback). Anything that speaks the OpenAI audio API points at
http://127.0.0.1:8790/v1; http://127.0.0.1:8790/ has a page to try it in the browser.

Routes
  POST /v1/audio/transcriptions   multipart: file, model (ignored), language (ignored, see below),
                                  response_format = json | text | verbose_json | srt | vtt
  GET  /v1/models                 lists the one model
  GET  /health                    {"status":"ok","loaded":bool}

Decoding always uses Arabic mode: in testing it transcribed pure English as well as
English mode did (0.7% vs 1.7% WER) and Arabic-English mixed speech far better.
The model loads on first request and unloads after IDLE_UNLOAD_S seconds without one,
so it does not hold GPU memory while VoiceStudio's other models need it.

Start: python server.py   (or start-server.cmd)
Env:   PORT (8790), IDLE_UNLOAD_S (300), HANDY_DIR, COHERE_GGUF
"""
import ctypes
import glob
import io
import os
import subprocess
import threading
import time
from math import gcd

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from scipy.signal import resample_poly

PORT = int(os.environ.get("PORT", "8790"))
IDLE_UNLOAD_S = int(os.environ.get("IDLE_UNLOAD_S", "300"))
HERE = os.path.dirname(os.path.abspath(__file__))
# Standalone: the engine (runtime/) and model (models/) live next to this file. Handy's copies are only a fallback.
_LOCAL_RT = os.path.join(HERE, "runtime")
HANDY_DIR = os.environ.get("HANDY_DIR") or (
    _LOCAL_RT if os.path.isfile(os.path.join(_LOCAL_RT, "transcribe.dll")) else os.path.expandvars(r"%LOCALAPPDATA%\Handy"))
GGUF = os.environ.get("COHERE_GGUF") or next(iter(
    glob.glob(os.path.join(HERE, "models", "*Q8_0.gguf"))
    + glob.glob(os.path.expandvars(
        r"%USERPROFILE%\.cache\huggingface\hub\models--handy-computer--cohere-transcribe-arabic-07-2026-gguf"
        r"\snapshots\*\*Q8_0.gguf"))), "")
MODEL_NAME = "cohere-transcribe-arabic"
SR = 16000
MAX_CHUNK_S = 25.0
LANG_OFFSET = 32           # transcribe_run_params.language (append-only field, x64 layout)


class Cohere:
    """Thin ctypes wrapper over transcribe.dll's documented C API; one session, guarded by a lock."""

    def __init__(self):
        os.add_dll_directory(HANDY_DIR)
        L = self.L = ctypes.CDLL(os.path.join(HANDY_DIR, "transcribe.dll"))
        L.transcribe_abi_struct_size.restype = ctypes.c_size_t
        L.transcribe_open.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        L.transcribe_run.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_void_p]
        L.transcribe_full_text.argtypes = [ctypes.c_void_p]
        L.transcribe_full_text.restype = ctypes.c_char_p
        L.transcribe_status_string.restype = ctypes.c_char_p
        L.transcribe_session_free.argtypes = [ctypes.c_void_p]
        size = L.transcribe_abi_struct_size(2)  # TRANSCRIBE_ABI_RUN_PARAMS
        if size < LANG_OFFSET + 8:
            raise RuntimeError(f"unexpected run-params size {size}; transcribe.dll version changed")
        self.params = ctypes.create_string_buffer(size)
        L.transcribe_run_params_init(self.params)
        self.lang = ctypes.create_string_buffer(b"ar")
        ctypes.c_void_p.from_buffer(self.params, LANG_OFFSET).value = ctypes.addressof(self.lang)
        st = L.transcribe_init_backends_default()
        if st:
            raise RuntimeError(L.transcribe_status_string(st).decode())
        self.sess = None
        self.lock = threading.Lock()
        self.last_used = 0.0

    def _ensure_loaded(self):
        if self.sess is None:
            if not os.path.isfile(GGUF):
                raise RuntimeError(f"Cohere GGUF not found: {GGUF!r} (run setup.cmd to download it)")
            s = ctypes.c_void_p()
            st = self.L.transcribe_open(GGUF.encode(), None, None, ctypes.byref(s))
            if st:
                raise RuntimeError(self.L.transcribe_status_string(st).decode())
            self.sess = s

    def transcribe(self, pcm: np.ndarray) -> str:
        with self.lock:
            self._ensure_loaded()
            pcm = np.ascontiguousarray(pcm, dtype=np.float32)
            st = self.L.transcribe_run(self.sess, pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(pcm), self.params)
            if st:
                raise RuntimeError(self.L.transcribe_status_string(st).decode())
            self.last_used = time.time()
            return (self.L.transcribe_full_text(self.sess) or b"").decode("utf-8", "replace").strip()

    def unload_if_idle(self):
        with self.lock:
            if self.sess is not None and time.time() - self.last_used > IDLE_UNLOAD_S:
                self.L.transcribe_session_free(self.sess)
                self.sess = None


def decode_audio(data: bytes) -> np.ndarray:
    try:
        wav, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception:
        import imageio_ffmpeg  # m4a, webm, aac ...: decode through ffmpeg from stdin
        p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", "pipe:0", "-f", "f32le",
                            "-ac", "1", "-ar", str(SR), "pipe:1"], input=data, capture_output=True, check=True)
        return np.frombuffer(p.stdout, dtype=np.float32)
    wav = wav.mean(axis=1)
    if sr != SR:
        g = gcd(sr, SR)
        wav = resample_poly(wav, SR // g, sr // g).astype(np.float32)
    return wav


def split(wav: np.ndarray):
    """Chunks of at most MAX_CHUNK_S, cut at the quietest 50 ms frame in the last 5 s of each window."""
    out, start, n, max_len = [], 0, len(wav), int(MAX_CHUNK_S * SR)
    while n - start > max_len:
        lo, hi = start + max_len - 5 * SR, start + max_len
        frames = wav[lo:hi][: (hi - lo) // 800 * 800].reshape(-1, 800)
        cut = lo + int(np.argmin((frames ** 2).mean(axis=1))) * 800 + 400
        out.append((start, cut))
        start = cut
    out.append((start, n))
    return out


app = FastAPI(title="Cohere Arabic ASR (local)")
model = Cohere()


def _idle_loop():
    while True:
        time.sleep(30)
        model.unload_if_idle()


threading.Thread(target=_idle_loop, daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok", "loaded": model.sess is not None, "model": MODEL_NAME}


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "local"}]}


_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Cohere Arabic ASR</title>
<style>body{font:16px system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
code{background:#eee;padding:2px 5px;border-radius:4px}#out{white-space:pre-wrap;font-size:20px;
border:1px solid #ccc;border-radius:8px;padding:12px;min-height:3em;margin-top:12px}</style></head><body>
<h2>Cohere Transcribe Arabic (local)</h2>
<p>Server is running. API base URL: <code>http://127.0.0.1:%PORT%/v1</code><br>
Transcribe endpoint (POST, multipart <code>file</code>): <code>/v1/audio/transcriptions</code></p>
<input type="file" id="f" accept="audio/*,video/*"> <button id="b">Transcribe</button>
<div id="out" dir="auto"></div>
<script>
document.getElementById('b').onclick = async () => {
  const f = document.getElementById('f').files[0], out = document.getElementById('out');
  if (!f) { out.textContent = 'Choose an audio file first.'; return; }
  out.textContent = 'Transcribing...'; const t0 = performance.now();
  const fd = new FormData(); fd.append('file', f);
  try {
    const r = await fetch('/v1/audio/transcriptions', {method: 'POST', body: fd});
    const j = await r.json();
    out.textContent = r.ok ? j.text + '\\n\\n(' + ((performance.now() - t0) / 1000).toFixed(1) + ' s)' : 'Error: ' + j.detail;
  } catch (e) { out.textContent = 'Error: ' + e; }
};
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
@app.get("/v1", response_class=HTMLResponse)
@app.get("/v1/", response_class=HTMLResponse)
def home():
    return _PAGE.replace("%PORT%", str(PORT))


@app.get("/v1/audio/transcriptions")
def transcriptions_help():
    return {"detail": "Send audio with POST (multipart form field 'file'). Open http://127.0.0.1:%d/ to try it in the browser." % PORT}


def _ts(t, sep):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)):03d}"


@app.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model_name: str = Form(MODEL_NAME, alias="model"),
                         language: str = Form(None), response_format: str = Form("json"),
                         prompt: str = Form(None), temperature: float = Form(None)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty audio file")
    try:
        wav = decode_audio(data)
    except Exception as e:
        raise HTTPException(400, f"Could not decode audio: {e}")
    t0 = time.perf_counter()
    segs = []
    for a, b in split(wav):
        if b - a < SR // 10:
            continue
        text = model.transcribe(wav[a:b])
        if text:
            segs.append({"id": len(segs), "start": round(a / SR, 2), "end": round(b / SR, 2), "text": text})
    text = " ".join(s["text"] for s in segs)
    dur = len(wav) / SR
    fmt = (response_format or "json").lower()
    if fmt == "text":
        return PlainTextResponse(text)
    if fmt == "srt":
        return PlainTextResponse("\n".join(f"{i + 1}\n{_ts(s['start'], ',')} --> {_ts(s['end'], ',')}\n{s['text']}\n"
                                           for i, s in enumerate(segs)))
    if fmt == "vtt":
        return PlainTextResponse("WEBVTT\n\n" + "\n".join(f"{_ts(s['start'], '.')} --> {_ts(s['end'], '.')}\n{s['text']}\n"
                                                         for s in segs))
    if fmt == "verbose_json":
        return JSONResponse({"task": "transcribe", "language": "arabic", "duration": round(dur, 2), "text": text,
                             "segments": segs, "processing_time": round(time.perf_counter() - t0, 3)})
    return JSONResponse({"text": text})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
