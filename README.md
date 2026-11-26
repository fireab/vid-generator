# The Heritage Short (*The Clay Jebena*)

A reproducible, config-driven AI short-film pipeline in Python that turns a single validated `storyboard.json` into broadcast-ready **16:9 widescreen** and **9:16 vertical** short films — complete with voiceover narration, consistent AI-generated keyframes, camera motion, ducked & loudness-normalized audio, synced English subtitles, and an AI disclosure end card.

---

## Table of Contents

- [Overview](#overview)
- [Pipeline Stages](#pipeline-stages)
- [Key Engineering Features](#key-engineering-features)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Quickstart](#quickstart)
- [Make Targets](#make-targets)
- [Outputs](#outputs)
- [Optional Kaggle GPU Workflow (Wan 2.2 + ACE-Step 1.5)](#optional-kaggle-gpu-workflow-wan-22--ace-step-15)
- [Customizing the Story](#customizing-the-story)
- [Repository Structure](#repository-structure)
- [Project Documentation](#project-documentation)

---

## Overview

Everything in the film is driven from [`storyboard.json`](storyboard.json) and enforced by [`schema/storyboard.schema.json`](schema/storyboard.schema.json). The current production story is ***The Clay Jebena*** (9 shots, ~71 seconds including a 3-second AI disclosure end card), depicting an Ethiopian grandmother passing down her black clay *jebena* and morning *buna* ceremony to her granddaughter.

The pipeline supports two build modes:
- **Radio Cut (`make radio`)**: Audio-only narration over a black 16:9 canvas (`outputs/radio_cut.mp4`) for fast pacing and voice review (User Test #1) before spending time on visuals.
- **Full Film (`make film`)**: End-to-end production export generating both `outputs/final_16x9.mp4` (`1920x1080`) and `outputs/final_9x16.mp4` (`1080x1920`) with burned-in subtitles, ducked background music, and `-14 LUFS` EBU R128 loudness normalization.

---

## Pipeline Stages

```text
storyboard.json
   │
   ▼  (JSON Schema validation)
1. narration  ──► outputs/narration/<shot_id>.wav   (Gemini TTS, auto-fallback to Cloudflare Deepgram Aura-1)
   │
2. keyframes  ──► outputs/keyframes/ref_sheet.png   (Cloudflare Workers AI FLUX.1 schnell)
   │              outputs/keyframes/<shot_id>.png
   │
3. shots      ──► outputs/shots/<shot_id>.mp4       (Kaggle Wan 2.2 clip if present, else FFmpeg Ken Burns 24fps)
   │
4. music      ──► outputs/music/score.{wav,mp3}     (ACE-Step 1.5 score if present, else FFmpeg ambient bed)
   │
5. assemble   ──► outputs/subtitles.srt             (synced to actual narration audio duration)
                  outputs/final_16x9.mp4            (1920x1080, H.264/AAC, 24fps, -14 LUFS, 3s AI end card)
                  outputs/final_9x16.mp4            (1080x1920, center-cropped, vertical safe-area subtitles)
```

| Stage | Module | Primary Tool / Model | Fallback |
| --- | --- | --- | --- |
| **Validate** | `pipeline/utils.py` | `jsonschema` (Draft 2020-12) | — |
| **Narration** | `pipeline/narration.py`, `pipeline/gemini_tts.py` | Gemini TTS (`gemini-2.5-flash-preview-tts`) | Cloudflare Workers AI (`@cf/deepgram/aura-1`) on daily quota exhaustion |
| **Keyframes** | `pipeline/keyframes.py` | Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) | — |
| **Shots** | `pipeline/shots.py` | Kaggle `Wan2.2-TI2V-5B` (`outputs/shots/<id>_wan.mp4`) | Smoothstep-eased FFmpeg `zoompan` Ken Burns (`1920x1080 @ 24fps`) |
| **Music** | `pipeline/music.py` | Kaggle `ACE-Step 1.5` (`outputs/music/score.{wav,mp3}`) | Procedural FFmpeg ambient drone bed (`placeholder_bed.wav`) |
| **Assemble** | `pipeline/assemble.py` | FFmpeg (`sidechaincompress`, 2-pass `loudnorm`, `ass`, `drawtext`) | — |

---

## Key Engineering Features

- **Deterministic SHA-256 Caching (`outputs/.cache_manifest.json`)**: Before calling any model or rendering any clip, each stage hashes its exact inputs (prompt, model, seed, parameters, or upstream file SHA-256). Editing a single word in one shot's `image_prompt` regenerates **only** that shot's keyframe and clip while reusing every other cached asset.
- **Unified Telemetry (`runs.jsonl`)**: Every model call, cache hit, fallback, and assembly pass appends a structured JSON line with `timestamp`, `stage`, `shot_id`, `model`, `params`, `seed`, `latency_ms`, `gpu_seconds`, `estimated_usd`, `cache_hit`, `status`, and `error`.
- **Resilient Retries & Rate-Limit Handling**: Exponential backoff with jitter honors server `RetryInfo` delays on per-minute `429` limits and fails fast on daily quota exhaustion (`PerDay`), triggering automatic fallback to Cloudflare Deepgram Aura-1 for narration.
- **Visual & Framing Consistency**: Generates a character reference sheet (`ref_sheet.png`), prepends `style_block` and `character_description` to every keyframe prompt, and enforces centered composition so a single `16:9` master center-crops cleanly into `9:16`.
- **Broadcast Audio Mastering**: Frame-accurate shot alignment via `pipeline/media.py`, sidechain music ducking (`threshold=0.02`, `ratio=6`, `attack=300ms`, `release=1500ms`), and 2-pass EBU R128 loudness normalization targeting **`-14.0 LUFS`** and **`-1.0 dBTP`**.
- **Safe-Area Subtitles & AI Disclosure**: Auto-wraps `subtitle_en` to ≤2 lines (~40 chars/line) synced to real spoken audio durations, raises vertical subtitles above Reels/TikTok/Shorts bottom UI (`margin_v=470`), and appends a 3-second `"Created with AI — <Title>"` end card.

---

## Prerequisites

- **Python**: 3.10+ (tested on Python 3.12)
- **FFmpeg & FFprobe**: Built with `libx264`, `aac`, `sidechaincompress`, `loudnorm`, `zoompan`, `drawtext`, and `ass` (`libass`)
- **System Font**: `DejaVu Sans`, `Inter`, `Noto Sans`, or `Liberation Sans` (e.g. `fonts-dejavu` on Ubuntu/Debian)
- **API Credentials**:
  - Google AI Studio (`GEMINI_API_KEY`)
  - Cloudflare Workers AI (`CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`)

---

## Setup

1. **Create the virtual environment and install Python dependencies:**
   ```bash
   make venv
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your credentials:
   ```dotenv
   GEMINI_API_KEY=your-gemini-api-key
   CLOUDFLARE_ACCOUNT_ID=your-cloudflare-account-id
   CLOUDFLARE_API_TOKEN=your-cloudflare-api-token
   ```

   **Optional environment overrides:**
   | Variable | Default | Description |
   | --- | --- | --- |
   | `TTS_BACKEND` | *(auto)* | Set to `cloudflare` to use `@cf/deepgram/aura-1` directly without attempting Gemini TTS first |
   | `CF_TTS_SPEAKER` | `luna` | Deepgram Aura-1 voice name (e.g., `luna`, `stella`, `athena`, `hera`, `asteria`) |
   | `CF_IMAGE_MODEL` | `@cf/black-forest-labs/flux-1-schnell` | Cloudflare Workers AI image model slug |

---

## Quickstart

```bash
# 1. Validate storyboard.json against schema/storyboard.schema.json
make validate

# 2. Run a tiny live check against Gemini text, Gemini TTS, and Cloudflare FLUX
make smoke

# 3. Build the audio-only radio cut for User Test #1 (outputs/radio_cut.mp4)
make radio

# 4. Build the full short film in 16:9 and 9:16 (outputs/final_16x9.mp4, outputs/final_9x16.mp4)
make film
```

You can also run individual shots through the orchestrator directly:
```bash
.venv/bin/python pipeline/run.py --mode film --shots shot_01 shot_02
```

---

## Make Targets

| Target | Command / Behavior |
| --- | --- |
| `make venv` | Create `.venv` and install packages from `requirements.txt` |
| `make validate` | Validate `storyboard.json` against `schema/storyboard.schema.json` |
| `make smoke` | Run 1 tiny live request each to Gemini text, Gemini TTS, and Cloudflare FLUX |
| `make radio` | Run `narration` → `assemble --mode radio` to build `outputs/radio_cut.mp4` |
| `make film` | Run full pipeline (`narration` → `keyframes` → `shots` → `music` → `assemble --mode film`) |
| `make keyframes` | Run only the Cloudflare FLUX keyframe stage |
| `make shots` | Run only the shot video stage (Wan 2.2 conform or Ken Burns) |
| `make music` | Run only the music stage (ACE-Step score check or placeholder ambient bed) |
| `make notebook` | Regenerate `notebooks/kaggle_gpu_batch.ipynb` from `notebooks/build_notebook.py` |
| `make merge-kaggle LOG=<path>` | Merge Kaggle GPU telemetry JSONL into `runs.jsonl` |
| `make clean-cache` | Delete `outputs/.cache_manifest.json` to force full regeneration on next run |

---

## Outputs

All generated media lives under `outputs/`:

| Path | Description |
| --- | --- |
| `outputs/final_16x9.mp4` | Final widescreen film (`1920x1080`, 24fps, H.264/AAC, `-14 LUFS`, burned-in subtitles, 3s end card) |
| `outputs/final_9x16.mp4` | Final vertical film (`1080x1920`, 24fps, center-cropped, vertical safe-area subtitles, 3s end card) |
| `outputs/subtitles.srt` | Synced English subtitles (≤2 lines, ~40 chars/line) |
| `outputs/radio_cut.mp4` | Audio-only narration cut over black 16:9 for User Test #1 |
| `outputs/narration/<shot_id>.wav` | Per-shot 24 kHz mono 16-bit PCM voiceover files |
| `outputs/keyframes/ref_sheet.png` | Character & style reference sheet |
| `outputs/keyframes/<shot_id>.png` | Per-shot FLUX keyframes |
| `outputs/shots/<shot_id>.mp4` | Per-shot `1920x1080 @ 24fps` animated clips |
| `outputs/music/placeholder_bed.wav` | Procedural ambient score fallback (replaced automatically if `score.wav` or `score.mp3` is present) |
| `outputs/.cache_manifest.json` | SHA-256 input-hash cache index |

---

## Optional Kaggle GPU Workflow (Wan 2.2 + ACE-Step 1.5)

To upgrade hero shots (`"motion_mode": "wan"`) with **Wan 2.2 TI2V-5B** and replace the ambient bed with an **ACE-Step 1.5** score:

1. Upload [`notebooks/kaggle_gpu_batch.ipynb`](notebooks/kaggle_gpu_batch.ipynb), `storyboard.json`, and `outputs/keyframes/` to a Kaggle GPU notebook.
2. Run the notebook to generate hero clips (`<shot_id>_wan.mp4`), 3 score candidates, and a `kaggle_runs.jsonl` GPU log.
3. Place downloaded clips into `outputs/shots/<shot_id>_wan.mp4` and your chosen score at `outputs/music/score.wav` (or `score.mp3`).
4. Merge GPU telemetry and re-export the film:
   ```bash
   make merge-kaggle LOG=kaggle_runs.jsonl
   make film
   ```
   Cached narration and keyframes are automatically skipped; only the upgraded shots and final assembly re-run.

---

## Customizing the Story

1. Edit [`storyboard.json`](storyboard.json) with your own `title`, `style_block`, `character_description`, `language`, `tts_voice`, `tts_style`, `music_cue`, and `shots`.
2. Update [`DESIGN.md`](DESIGN.md) and [`ETHICS.md`](ETHICS.md) (especially the consent record if any real person's likeness or voice is used).
3. Run `make validate` followed by `make film`. Only shots whose inputs changed will regenerate.

---

## Repository Structure

```text
.
├── Makefile                      # Workflow targets (venv, validate, smoke, radio, film, etc.)
├── requirements.txt              # Python dependencies
├── .env.example                  # Required API key placeholders
├── storyboard.json               # Single source of truth for the film
├── schema/
│   └── storyboard.schema.json    # JSON Schema (Draft 2020-12) for storyboard validation
├── pipeline/
│   ├── run.py                    # End-to-end orchestrator
│   ├── utils.py                  # Schema validator, SHA-256 cache, retry wrapper, runs.jsonl logger
│   ├── media.py                  # Shared FFmpeg/FFprobe helpers & frame-accurate shot timing
│   ├── gemini_tts.py             # Gemini TTS client (v1beta), diagnostics & plain-text fallback
│   ├── smoke_test.py             # Live API connectivity checks
│   ├── narration.py              # Voiceover generation (Gemini TTS + Cloudflare Aura-1 fallback)
│   ├── keyframes.py              # Reference sheet + per-shot FLUX keyframe generation
│   ├── shots.py                  # Wan 2.2 clip conformance + eased Ken Burns motion
│   ├── music.py                  # ACE-Step score loader + FFmpeg ambient bed fallback
│   ├── assemble.py               # Audio mixing, ducking, 2-pass loudnorm, subs, end card, 16:9 & 9:16 exports
│   └── merge_kaggle_log.py       # Merge Kaggle GPU telemetry into runs.jsonl
├── notebooks/
│   ├── build_notebook.py         # Generator script for the Kaggle notebook
│   └── kaggle_gpu_batch.ipynb    # Batch Wan 2.2 + ACE-Step 1.5 notebook
├── outputs/                      # Generated audio, keyframes, clips, subtitles, and final MP4s
├── runs.jsonl                    # Append-only structured execution log
└── *.md                          # Project documentation (README, DESIGN, ETHICS, ARCHITECTURE, COSTS, EXPERIMENTS, FAILURES)
```

---

## Project Documentation

- [`DESIGN.md`](DESIGN.md) — Audience, creative intent, visual/audio direction, shot rationale, and User Test #1 & #2 checklists
- [`ETHICS.md`](ETHICS.md) — Consent & likeness record, cultural representation guidelines, model licences, and AI disclosure plan
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — System design notes
- [`EXPERIMENTS.md`](EXPERIMENTS.md) — Prompt, voice, and parameter experiments
- [`FAILURES.md`](FAILURES.md) — Failure log and mitigations
- [`COSTS.md`](COSTS.md) — Cost and GPU-second tracking
