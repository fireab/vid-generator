# Design — *Gursha (One Plate, One Heart)*

## Audience & Intent
- **Intended Audience**: Ethiopians at home and in the diaspora, plus international viewers curious about Ethiopian culture, watching on phones (`9:16` vertical on Reels/TikTok/Shorts) and YouTube/desktop (`16:9` widescreen).
- **Emotional Intent**: Celebrate how Ethiopian society is built on togetherness—showing that *Gursha* is not just feeding someone, it is how we say **"you belong here."** Viewers should finish the film feeling warmth, pride, and a sense of shared humanity.
- **Runtime & Deliverables**: ~70 seconds across 9 shots (+ 3-second AI disclosure end card = ~73s total), exported as both `outputs/final_16x9.mp4` (`1920x1080`) and `outputs/final_9x16.mp4` (`1080x1920`) with burned-in English subtitles.

## Story & Narrative Arc
1. **Community Foundation (Shots 1–2)**: Opens in a golden-hour Ethiopian neighborhood courtyard where doors stay open and neighbors are family, moving inside as family and friends gather around one shared woven *mesob*.
2. **The Shared Plate (Shots 3–4)**: Overhead view of *injera* and colorful *wot* (*doro*, *misir*, *shiro*, *gomen*)—one plate as an act of trust—while laughter and conversation dissolve the weight of the day.
3. **The Gesture of Gursha (Shots 5–7)**: A hand tears *injera* to scoop rich *wot*; a mother lovingly offers a *Gursha* ("You come before me"); two friends laugh as one playfully insists on an even bigger bite.
4. **Universal Resonance (Shots 8–9)**: Even in a world that pulls people apart, this tradition brings everyone back to one table—closing on hands resting near the shared *mesob* in warm golden light.

## Visual Style & Framing
- **Style Block**: Warm cinematic film still, golden afternoon sunlight in an Ethiopian home, subtle 35mm film grain, rich earthy reds, saffron, terracotta, and warm cream tones, shallow depth of field.
- **Dual-Aspect Framing**: Every shot is composed with the primary action centered and generous margins so a single `16:9` master center-crops cleanly into `9:16` without cutting off faces or hands.

## Characters
- **Canonical Ensemble**: A warm, welcoming Ethiopian family and close friends in their 20s to 60s wearing casual modern clothes mixed with subtle traditional white cotton *netela* scarves, gathered closely around a colorful woven *mesob* basket table with genuine warm smiles.
- All characters are fictionalized and stylized (no real person's likeness or voice).

## Sound, Narration & Subtitles
- **Narration**: Warm, heartfelt, unhurried Amharic (`language: "am"`, voice `Kore`) synced per shot.
- **Music Cue**: Uplifting Ethiopian instrumental score with gentle *krar*, soft *masinko*, and light *kebero* pulse at 76 BPM, sidechain-ducked under narration (`threshold=0.02`, `ratio=6`, `attack=300ms`, `release=1500ms`) and 2-pass normalized to `-14 LUFS` / `-1 dBTP`.
- **Subtitles**: Concise 2-line English subtitles (`<= 40` chars/line) burned into both exports, positioned inside the vertical safe area (`margin_v=470`) on `9:16`.

## Shot List Rationale
| Shot | Dur | Narrative Purpose | Motion Mode |
| --- | --- | --- | --- |
| `shot_01` | 8s | Establish lively Ethiopian neighborhood courtyard & open-door warmth | `ken_burns` |
| `shot_02` | 8s | Show family and friends gathering around one woven *mesob* | `wan` |
| `shot_03` | 7s | Overhead insert of *injera* & colorful *wot* symbolizing shared trust | `ken_burns` |
| `shot_04` | 8s | Capture communal laughter and hands reaching into the shared plate | `wan` |
| `shot_05` | 7s | Close-up transition to tearing *injera* and preparing a *Gursha* | `ken_burns` |
| `shot_06` | 8s | Emotional core: elder/mother offering a loving *Gursha* | `wan` |
| `shot_07` | 8s | Joyful warmth: two friends laughing over a playfully generous *Gursha* | `wan` |
| `shot_08` | 8s | Wide glowing room showing togetherness against modern isolation | `ken_burns` |
| `shot_09` | 8s | Closing image of hands resting by the *mesob* and final thematic payoff | `ken_burns` |

---

## User Test #1 — Radio Cut (`outputs/radio_cut.mp4`)
*Play the audio-only Amharic narration cut for 1–2 listeners before locking visuals.*
- **Tester(s)**: _[TBD]_
- **Date**: _[TBD]_
- **Amharic Flow & Pronunciation Notes**: _[Do all 9 lines sound natural, warm, and unhurried?]_
- **Pacing & Pause Check**: _[Does the 70-second cadence give each beat enough room to breathe?]_
- **Changes Made**: _[Record any wording or duration adjustments after User Test #1]_

## User Test #2 — Near-Final Cut (`outputs/final_16x9.mp4` & `outputs/final_9x16.mp4`)
*Test on both phone (9:16) and laptop/TV (16:9) with sound on and muted.*
- **Tester(s)**: _[TBD]_
- **Date**: _[TBD]_
- **Visual Warmth & Continuity Notes**: _[Do the mesob, injera, and family gathering feel cohesive?]_
- **Subtitle Readability Check**: _[Can non-Amharic viewers follow every beat comfortably in 9:16 and 16:9?]_
- **Audio Mix Check**: _[Is the Amharic voice clear above the ducked krar/masinko score at -14 LUFS?]_
- **Final Adjustments**: _[Record final polish changes before release]_
