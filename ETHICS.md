# Ethics — *The Clay Jebena*

## Consent & Likeness
- **Real person's likeness used?**: **No.** All characters ("Emaye" and her granddaughter) are **fictionalized, stylized composite figures** inspired by shared Ethiopian cultural traditions rather than any living or deceased individual's photograph or identity.
- **Real person's voice used?**: **No.** Narration uses a standard prebuilt synthetic voice (`Kore`) from Gemini TTS; no voice cloning or personal voice recordings were used.
- **Consent Record**: Because no real individual's face, name, or voice is depicted, no individual likeness release is required. If real family photos or voice recordings are ever added in a future revision, written informed consent from each depicted/recorded person will be logged here prior to generation.

## Cultural Representation
- Depicts the Ethiopian *buna* ceremony (*jebena*, *cini* cups, fresh grass, frankincense, handwoven *netela*) with dignity, everyday warmth, and documentary-style restraint rather than exoticized clichés.
- Avoids stereotyping or poverty framing; focuses on craft, hospitality, and intergenerational resilience.

## Model Licences & Attribution
| Stage | Model / Tool | Provider / Licence | Notes |
| --- | --- | --- | --- |
| Narration (TTS) | `gemini-2.5-flash-preview-tts` | Google Gemini API Terms of Service | Prebuilt voice (`Kore`); subject to Google Generative AI Prohibited Use Policy |
| Keyframes | `@cf/black-forest-labs/flux-1-schnell` | Black Forest Labs — **Apache 2.0** (via Cloudflare Workers AI) | Commercial & non-commercial use permitted under Apache 2.0 |
| Hero Motion (optional) | `Wan2.2-TI2V-5B` | Alibaba Wan — **Apache 2.0** (run on Kaggle GPU) | Open weights under Apache 2.0 |
| Score (optional) | `ACE-Step 1.5` | ACE-Step — **Apache 2.0** (run on Kaggle GPU) | Open weights under Apache 2.0; FFmpeg procedural ambient bed used as local fallback |
| Assembly & Mix | `FFmpeg` | LGPL / GPL | Local deterministic rendering and EBU R128 loudness normalization |

## AI Disclosure
- **In-video disclosure**: Every rendered export (`outputs/final_16x9.mp4` and `outputs/final_9x16.mp4`) appends a 3-second end card reading: **"Created with AI — The Clay Jebena"**.
- **Distribution disclosure**: Any upload to YouTube, Instagram Reels, or TikTok will enable the platform's "Altered or synthetic content" label and include a plain-language note in the caption listing the AI tools used.

## Data & Privacy
- API keys (`GEMINI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`) are stored exclusively in `.env` (gitignored) and never logged to `runs.jsonl`.
- No private personal photos, addresses, or identifying family records are uploaded to external APIs.
