# Design — *The Clay Jebena*

## Audience & Intent
- **Intended Audience**: Family, friends, and members of the Ethiopian diaspora who know the quiet comfort of the traditional *buna* (coffee) ceremony, as well as general audiences interested in cross-generational heritage stories.
- **Emotional Intent**: Leave the viewer feeling **warmth, pride, and gentle nostalgia** — the realization that home travels with us through the small rituals our elders pass down.
- **Format & Runtime**: ~71 seconds total (9 shots = 68s + 3s AI disclosure end card), delivered in both `16:9` (`1920x1080`) for YouTube/desktop and `9:16` (`1080x1920`) for Reels/Shorts/TikTok.

## Story & Intent
*The Clay Jebena* follows a grandmother ("Emaye") in the Ethiopian highlands whose morning coffee ceremony anchors her home and neighborhood. When her granddaughter leaves for a distant city, Emaye wraps her 40-year-old black clay *jebena* in a cotton *netela* and places it in her hands — turning a household heirloom into a portable sense of home.

## Visual Style
- **Look**: 35mm Kodak Portra film aesthetic, warm golden-hour sunlight filtering through smoke, shallow depth of field, terracotta and espresso earth tones, subtle grain.
- **Framing Discipline**: Every prompt uses centered composition with generous headroom and side margins so the same `16:9` master crops cleanly to `9:16` without losing the subject.

## Characters
- **Emaye (fictionalized composite elder)**: Ethiopian grandmother in her 70s, close-cropped silver hair, kind deep-set eyes, weathered hands, wearing a white handwoven cotton *netela* with a subtle gold-and-crimson border.
- Consistency is reinforced by a dedicated reference sheet (`outputs/keyframes/ref_sheet.png`) plus prepending `style_block` + `character_description` to every keyframe prompt.

## Sound & Narration
- **Narration**: Warm, unhurried English voiceover (`en-US`, Gemini TTS `Kore` voice) paced at ~155 words across 68 seconds (~135 WPM) to leave breathing room between beats.
- **Music**: Gentle traditional *krar* / *washint* flute and warm strings (`outputs/music/score.wav` from ACE-Step 1.5, with an FFmpeg ambient bed fallback), sidechain-ducked under narration (`threshold=0.02`, `ratio=6`, `attack=300ms`, `release=1500ms`) and 2-pass normalized to `-14 LUFS` / `-1 dBTP`.
- **Subtitles**: Auto-generated `outputs/subtitles.srt` (max 2 lines, ≤40 chars/line) burned into both exports, with vertical subtitles raised above social-app bottom UI (`margin_v=470`).

## Shot List Rationale
| Shot | Duration | Purpose | Motion Mode |
| --- | --- | --- | --- |
| `shot_01` | 7s | Highland dawn establishing shot; sets sensory quiet | `ken_burns` |
| `shot_02` | 8s | Introduces Emaye roasting coffee beans | `wan` |
| `shot_03` | 7s | Reveals the heirloom black clay *jebena* | `ken_burns` |
| `shot_04` | 8s | Frankincense smoke & neighborhood warmth | `wan` |
| `shot_05` | 8s | Departure tension: packed suitcase in morning shadows | `ken_burns` |
| `shot_06` | 8s | Turning point: Emaye's steady high pour | `wan` |
| `shot_07` | 8s | Emotional peak: passing the wrapped *jebena* | `wan` |
| `shot_08` | 7s | Present day: the same *jebena* steaming in a city apartment | `ken_burns` |
| `shot_09` | 7s | Closing highland dusk horizon & thematic payoff | `ken_burns` |

---

## User Test #1 — Radio Cut (`outputs/radio_cut.mp4`)
*Play the audio-only cut for 1–2 listeners before locking visuals.*
- **Tester(s)**: _[TBD]_
- **Date**: _[TBD]_
- **Pacing & Clarity Notes**: _[Does any line feel rushed or unclear?]_
- **Emotional Beat Check**: _[Which line landed strongest?]_
- **Changes Made**: _[List storyboard edits applied after User Test #1]_

## User Test #2 — Near-Final Cut (`outputs/final_16x9.mp4` & `outputs/final_9x16.mp4`)
*Watch on both laptop (16:9) and phone (9:16) with sound on and muted.*
- **Tester(s)**: _[TBD]_
- **Date**: _[TBD]_
- **Visual Consistency Notes**: _[Does Emaye / the jebena look consistent across shots?]_
- **Subtitle & Safe-Area Check**: _[Readable on phone without overlapping Reels/TikTok UI?]_
- **Audio Mix Check**: _[Voice clear over music? Comfortable loudness?]_
- **Final Adjustments**: _[List polish edits applied before final export]_
