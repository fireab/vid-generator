# Ethics — *Gursha (One Plate, One Heart)*

## Consent & Likeness
- **Real person's likeness used?**: **No.** All characters in *Gursha (One Plate, One Heart)* are **stylized, fictionalized representations** of an Ethiopian family and neighborhood—no real person's face or physical likeness is used, referenced, or depicted.
- **Real person's voice used?**: **No.** Narration uses synthetic text-to-speech voices only—no real person's voice is used, sampled, or cloned.
- **Consent Record**: Because all visuals and voices are fictionalized synthetic creations with zero real-person PII, face, or voice data, no individual likeness release is required. Should any real person's image or voice recording ever be introduced in a future version, explicit written consent will be obtained and logged here before generation.

## Cultural Representation
- Portrays Ethiopian communal dining (*mesob*, *injera*, *wot*, *netela*, and the tradition of *Gursha*) with warmth, dignity, and everyday authenticity.
- Avoids reductive stereotypes; centers hospitality, mutual care, and cross-generational connection.

## Model Licences & Attribution
| Stage | Model / Tool | Provider / Licence | Usage Notes |
| --- | --- | --- | --- |
| **Narration (TTS)** | `gemini-2.5-flash-preview-tts` | Google Gemini API Terms of Service | Synthetic Amharic voiceover (`Kore` prebuilt voice) |
| **Keyframes** | `@cf/black-forest-labs/flux-1-schnell` | Black Forest Labs — **Apache 2.0** (via Cloudflare Workers AI) | Commercial & non-commercial use permitted under Apache 2.0 |
| **Hero Motion** *(optional)* | `Wan2.2-TI2V-5B` | Alibaba Wan — **Apache 2.0** (run on Kaggle GPU) | Open weights under Apache 2.0; local FFmpeg Ken Burns fallback |
| **Music Score** *(optional)* | `ACE-Step 1.5` | ACE-Step — **MIT Licence** (run on Kaggle GPU) | Open weights under MIT; local FFmpeg procedural ambient bed fallback |
| **Assembly & Mastering** | `FFmpeg` | LGPL / GPL | Local deterministic rendering, subtitle burn-in, and `-14 LUFS` EBU R128 normalization |

## AI Disclosure Plan
- **In-video end card**: Every production export (`outputs/final_16x9.mp4` and `outputs/final_9x16.mp4`) includes a dedicated 3-second closing disclosure card: **"Created with AI — Gursha (One Plate, One Heart)"**.
- **Platform disclosure**: When shared on YouTube, TikTok, Instagram Reels, or messaging platforms, the platform's synthetic/AI-generated media toggle is enabled and the description explicitly credits the AI pipeline models used.

## Data & Privacy
- API credentials (`GEMINI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`) live only in `.env` (gitignored) and are never written to `runs.jsonl` or committed to version control.
- No personal photographs, private voice notes, or identifying family data are transmitted to external APIs.
