# Cohere Transcribe Arabic (Q8): local speech-to-text for Windows

This is free, offline speech-to-text for Arabic (Egyptian and other dialects) mixed with English. **English words stay in English letters and Arabic words stay in Arabic letters**, for example:

```
Gimmick هي اللي بتخلّي حد زي "جون سينا" يلعب دور الـRapper،
```

It runs on your own Windows PC. After setup, nothing is sent to the internet.

This repo contains:
- **The engine**: [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) and ggml, in `runtime/`. It uses any GPU through Vulkan and falls back to the CPU.
- **A local server**: speaks the OpenAI speech-to-text API and has a browser page for trying it.
- **One-click setup.**

The model is **not** in this repo: it's 2.41 GB. Use the copy you already have, or let `setup.cmd` download it from its official page: [Cohere Transcribe Arabic 07-2026, Q8_0 GGUF](https://huggingface.co/handy-computer/cohere-transcribe-arabic-07-2026-gguf).

## Needs

- Windows 10 or 11, 64-bit
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/). Tick **"Add python.exe to PATH"** during install.
- About 3 GB of free disk space
- Optional: any GPU with up-to-date drivers. Without one it runs on the CPU, which is slower.

## Setup (once)

1. Click the green **Code** button, then **Download ZIP**, and unzip it somewhere permanent, for example `C:\cohere-arabic-asr`. Or clone it:
   `git clone https://github.com/mooo-9/cohere-arabic-asr`
2. **If you already have the model**, copy your `cohere-transcribe-arabic-07-2026-Q8_0.gguf` into the `models\` folder. Any `.gguf` name works. If you downloaded it through the Handy app, skip this step: it's found automatically.
3. Double-click **`setup.cmd`**. It installs the Python packages and uses your model. If it finds no model, it downloads it from Hugging Face, checks it, and resumes if the download is interrupted.

To keep the model somewhere else instead of copying it, set `COHERE_GGUF` to its full path before starting. In a command window: `set COHERE_GGUF=D:\models\cohere-transcribe-arabic-07-2026-Q8_0.gguf`

## Use

Double-click **`start-server.cmd`**, then open **http://127.0.0.1:8790/** in your browser. Choose an audio file (wav, mp3, m4a, ogg, webm, flac and others) and click **Transcribe**.

The first request takes a few seconds while the model loads; after that it's fast. The model unloads after 5 minutes with no requests, to free GPU memory.

## Use from your own code and apps (OpenAI-compatible API)

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API key | anything |
| Model | anything |

**PowerShell.** Type `curl.exe`, not `curl`, and use the full path to a real audio file:
```powershell
curl.exe -F "file=@C:\path\to\audio.wav" http://127.0.0.1:8790/v1/audio/transcriptions
```

**Python:**
```python
import requests
r = requests.post("http://127.0.0.1:8790/v1/audio/transcriptions",
                  files={"file": open(r"C:\path\to\audio.wav", "rb")})
print(r.json()["text"])
```

**OpenAI library:**
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8790/v1", api_key="local")
print(client.audio.transcriptions.create(model="cohere", file=open("audio.wav", "rb")).text)
```

The optional form field `response_format` can be `json` (the default), `text`, `verbose_json`, `srt` or `vtt`. Long audio is split automatically at quiet points into pieces of up to 25 seconds.

## Start automatically at login (optional)

- `autostart-on.cmd` starts the server hidden at every login, and starts it now. Its output goes to `server.log`.
- `autostart-off.cmd` turns that off.

## Change the port

Run `set PORT=8791` in a command window, then run `start-server.cmd` from that same window.

## Troubleshooting

| Problem | Fix |
|---|---|
| `curl: (26) Failed to open/read local data` | The audio file path is wrong; use its full path. |
| `{"detail":"Not Found"}` | You opened the wrong address; open http://127.0.0.1:8790/ |
| The page doesn't open | The server isn't running; run `start-server.cmd`. |
| `Cohere GGUF not found` | Put the model `.gguf` in `models\`, or run `setup.cmd`. |
| Port already in use | Another copy is running, or set a different `PORT`. |

## Licences

- The model is Apache-2.0 (Cohere Labs) and is not included here.
- transcribe.cpp, ggml and Handy are MIT.

See [LICENSES.txt](LICENSES.txt) for details.
