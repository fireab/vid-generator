# The Heritage Short — End-to-End Implementation Guide
**Reproducible AI Short-Film Pipeline (*The Clay Jebena* & *Gursha: One Plate, One Heart*)**

---

## Project Links & Final Deliverables

- **GitHub Repository (Public Source Code)**: https://github.com/fireab/vid-generator
- **Generated Final Video #1 (Google Drive)**: https://drive.google.com/file/d/1j8DOiingzx9I0ntDVPxnME0HdJ74z-5-/view?usp=sharing
- **Generated Final Video #2 (Google Drive)**: https://drive.google.com/file/d/1OoWk-UQgCQnC19-nqyLwEF70mdQnhj6U/view?usp=sharing

---

## 1. Executive Summary

**The Heritage Short** is a reproducible, config-driven AI video production pipeline written in Python and FFmpeg. Instead of generating one-off clips manually in web UIs, the entire film is defined declaratively in a single `storyboard.json` file validated against a strict JSON Schema (`schema/storyboard.schema.json`).

From that single configuration file, the pipeline automatically:
1. Synthesizes per-shot voiceover narration (supporting both English and Amharic).
2. Generates a character/style reference sheet and centered per-shot keyframes via Cloudflare Workers AI (`FLUX.1 schnell`).
3. Renders frame-accurate `1920x1080 @ 24fps` motion clips (using Kaggle GPU `Wan 2.2 TI2V-5B` clips when present, or smoothstep-eased FFmpeg `zoompan` Ken Burns motion).
4. Integrates an instrumental background score (`ACE-Step 1.5` or a procedural ambient drone bed), sidechain-ducks the music under the narration, and runs 2-pass EBU R128 loudness normalization to **`-14.0 LUFS`** and **`-1.0 dBTP`**.
5. Generates frame-synced English subtitles (`outputs/subtitles.srt`, max 2 lines, ≤40 characters/line) and a 3-second AI disclosure end card.
6. Exports dual aspect-ratio masters:
   - **`outputs/final_16x9.mp4`** (`1920x1080` horizontal for YouTube / desktop)
   - **`outputs/final_9x16.mp4`** (`1080x1920` vertical center-crop with safe-area subtitles raised above Reels/TikTok/Shorts UI).

---

## 2. System Architecture & Pipeline Flow

```text
storyboard.json
   │
   ├──► 1. Schema Validation (pipeline/utils.py)
   │
   ├──► 2. Narration Stage (pipeline/narration.py)
   │       └─► outputs/narration/<shot_id>.wav (24kHz mono PCM)
   │
   ├──► 3. Keyframes Stage (pipeline/keyframes.py)
   │       └─► outputs/keyframes/ref_sheet.png + <shot_id>.png
   │
   ├──► 4. Shots Stage (pipeline/shots.py)
   │       └─► outputs/shots/<shot_id>.mp4 (1920x1080 @ 24fps, frame-matched to voice)
   │
   ├──► 5. Music Stage (pipeline/music.py)
   │       └─► outputs/music/score.wav or placeholder_bed.wav
   │
   └──► 6. Production Assembly (pipeline/assemble.py)
           ├─► outputs/subtitles.srt
           ├─► outputs/final_16x9.mp4 (1920x1080, -14 LUFS, burned-in subs, 3s end card)
           └─► outputs/final_9x16.mp4 (1080x1920, center-cropped, vertical safe-area subs)
```

### Core Design Principles
- **Single Source of Truth**: Every creative and technical decision (shot duration, reason, narration script, English subtitle, image prompt, motion mode, random seed, voice, and music cue) lives in `storyboard.json`.
- **Deterministic SHA-256 Caching**: Every stage computes a canonical SHA-256 hash of its exact inputs before calling an external API or running FFmpeg. Editing a single shot regenerates **only** that shot.
- **Graceful Degradation**: Every external or GPU-heavy step has an automatic fallback so `make film` never breaks end-to-end.
- **Full Observability**: Every model call, cache hit, fallback, latency, cost estimate, and loudness measurement is appended to `runs.jsonl`.

---

## 3. Step-by-Step Implementation Breakdown

### Phase 1: Foundation, Validation, Caching, Narration & Radio Cut

1. **Strict Storyboard Schema (`schema/storyboard.schema.json`)**:
   - Enforces top-level `title`, `style_block`, `character_description`, `language`, `tts_voice`, `tts_style`, `music_cue`, and `shots`.
   - Enforces per-shot `id`, `reason`, `duration_sec`, `narration_text`, `subtitle_en`, `image_prompt`, `motion_prompt`, `motion_mode` (`"wan"` or `"ken_burns"`), and `seed`.
2. **Shared Utilities (`pipeline/utils.py`)**:
   - `validate_storyboard()`: Validates `storyboard.json` against Draft 2020-12 JSON Schema and checks for duplicate shot IDs.
   - `input_hash()` / `cache_lookup()` / `cache_store()`: Tracks SHA-256 input hashes in `outputs/.cache_manifest.json`.
   - `with_retry()`: Exponential backoff with jitter that honors server `RetryInfo` delays on HTTP 429s and fails fast on daily quota exhaustion.
   - `log_run()`: Appends structured telemetry records to `runs.jsonl`.
3. **API Smoke Test (`pipeline/smoke_test.py`)**:
   - Verifies live connectivity to Gemini text, Gemini TTS, and Cloudflare Workers AI FLUX.
4. **Multi-Backend Narration (`pipeline/narration.py` & `pipeline/gemini_tts.py`)**:
   - Primary: Gemini TTS (`gemini-2.5-flash-preview-tts` via `v1beta`) with automatic plain-text fallback if styled prompts return empty audio.
   - Automatic Fallbacks on Daily Quota Exhaustion: Cloudflare Workers AI Deepgram Aura-1 (`@cf/deepgram/aura-1`) for English and Microsoft Edge Neural TTS (`am-ET-MekdesNeural`) for Amharic.
5. **Radio Cut (`make radio`)**:
   - Concatenates per-shot narration over a black `16:9` screen into `outputs/radio_cut.mp4` for **User Test #1** before generating visuals.

### Phase 2: Visual Keyframes, Camera Motion & Music Score

1. **Keyframes (`pipeline/keyframes.py`)**:
   - Generates `outputs/keyframes/ref_sheet.png` followed by per-shot keyframes (`outputs/keyframes/<shot_id>.png`) via Cloudflare Workers AI `@cf/black-forest-labs/flux-1-schnell`.
   - Automatically prepends `style_block` and `character_description` and enforces centered composition safe for both `16:9` and `9:16` center crops.
2. **Hybrid Shot Motion (`pipeline/shots.py`)**:
   - Frame-locks each shot to `media.shot_frames()` (`max(duration_sec, narration_duration + 0.3s)` at `24 fps`).
   - Uses Kaggle `Wan2.2-TI2V-5B` clips (`outputs/shots/<shot_id>_wan.mp4`) when available, or falls back to 2x-upscaled Lanczos + smoothstep-eased FFmpeg `zoompan` Ken Burns motion.
3. **Music Score (`pipeline/music.py`) & Kaggle Notebook (`notebooks/kaggle_gpu_batch.ipynb`)**:
   - Uses `outputs/music/score.{wav,mp3}` from `ACE-Step 1.5` when present, or generates a procedural FFmpeg ambient drone bed (`placeholder_bed.wav`).

### Phase 3: Production Audio Mixing, Subtitles, End Card & Dual Exports

Implemented in `pipeline/assemble.py`:
1. **Audio Mixing & Sidechain Ducking**:
   - Concatenates narration at exact shot timings plus 3s end-card tail.
   - Loops/trims music score with fade-in/out and ducks it under narration via FFmpeg `sidechaincompress` (`threshold=0.02`, `ratio=6`, `attack=300ms`, `release=1500ms`).
2. **Two-Pass Loudness Normalization**:
   - Runs 2-pass FFmpeg `loudnorm` targeting **`-14.0 LUFS`** integrated loudness and **`-1.0 dBTP`** true peak.
3. **Subtitles & 3-Second AI Disclosure End Card**:
   - Writes `outputs/subtitles.srt` (max 2 lines, ≤40 chars/line) timed to actual narration durations.
   - Generates a 3-second `"Created with AI — <Film Title>"` disclosure end card.
4. **Dual Aspect Ratio Exports**:
   - `outputs/final_16x9.mp4` (`1920x1080`, H.264, AAC, 24fps, burned-in subtitles).
   - `outputs/final_9x16.mp4` (`1080x1920` center-cropped, burned-in subtitles positioned inside the vertical safe area at `MarginV=470`).

---

## 4. Key Engineering Challenges Resolved

| Issue Encountered | Root Cause | Solution Implemented |
| --- | --- | --- |
| `400 INVALID_ARGUMENT: Unknown name "speechConfig"` | `google-genai` 3.6.1 defaults to API `v1`, while `speechConfig` requires `v1beta`. | Set `http_options={"api_version": "v1beta"}` in `gemini_tts.py`. |
| `AttributeError` on `resp.candidates[0].content.parts` | Styled TTS prompts occasionally triggered `FinishReason.OTHER` with empty content. | Added safe `_extract_pcm()` diagnostics plus automatic plain-text prompt retry. |
| Gemini TTS Free Tier `429 RESOURCE_EXHAUSTED` (3 RPM / 10 RPD) | Free Tier rate/daily caps reached during iterative runs. | Added `RetryInfo` delay parsing for per-minute limits, fast-fail on daily caps, and automatic fallback to Cloudflare Aura-1 (English) and Edge Neural TTS `am-ET-MekdesNeural` (Amharic). |
| Cloudflare FLUX `400 Bad Request` on `/seed` | `flux-1-schnell` endpoint rejects `seed` in JSON body. | Omitted `seed` from `flux-1-schnell` HTTP payload while keeping `seed` in the SHA-256 cache key. |

---

## 5. Ethics, Licensing & AI Disclosure

- **Consent & Likeness**: All characters are stylized, fictionalized composite figures. No real person's face, likeness, or voice is used or cloned.
- **Licences**: FLUX.1 schnell (Apache 2.0), Wan 2.2 (Apache 2.0), ACE-Step 1.5 (MIT), FFmpeg (LGPL/GPL).
- **AI Disclosure**: Burned-in 3-second closing end card (`"Created with AI — ..."`) on all video exports plus platform synthetic-content labels.

---

## 6. Quick Reproduction Commands

```bash
git clone https://github.com/fireab/vid-generator.git
cd vid-generator
make venv
cp .env.example .env   # Add GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
make validate
make smoke
make radio             # Outputs outputs/radio_cut.mp4
make film              # Outputs outputs/final_16x9.mp4, outputs/final_9x16.mp4, outputs/subtitles.srt
```
