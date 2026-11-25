"""Builds notebooks/kaggle_gpu_batch.ipynb (run once; output is committed)."""
import json
from pathlib import Path

cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                               "outputs": [], "source": s.strip("\n")})

md("""
# The Heritage Short — Kaggle GPU batch

Runs the GPU-heavy stages that can't run locally:

1. **Wan 2.2 TI2V-5B**: image+text → video for every shot with `motion_mode == "wan"`, starting from that shot's keyframe.
2. **ACE-Step 1.5**: 3 score candidates from `music_cue`.

**Inputs:** attach a Kaggle Dataset containing `storyboard.json` and `outputs/keyframes/*.png`.
**Outputs** (in `/kaggle/working/out/`):
- `shots/<shot_id>_wan.mp4` → copy to `outputs/shots/` locally
- `music/score_candidate_{1,2,3}.wav` → pick one, save as `outputs/music/score.wav`
- `kaggle_runs.jsonl` → merge locally with `make merge-kaggle LOG=path/to/kaggle_runs.jsonl`

**Accelerator:** GPU P100 or T4. TI2V-5B is officially a 720p model (`1280*704`); on 16 GB cards keep
offload + T5-on-CPU enabled. `480p` draft mode is faster but outside the officially tuned resolution.
""")

md("## 1. Config")
code("""
from pathlib import Path

INPUT_DIR   = Path("/kaggle/input/heritage-short")   # <- your dataset slug
WORK        = Path("/kaggle/working")
OUT         = WORK / "out"
RESOLUTION  = "480p"            # "480p" draft | "720p" final
ONLY_SHOTS  = None              # e.g. {"shot_02", "shot_07"}; None = all wan shots
RUN_WAN     = True
RUN_MUSIC   = True
N_SCORES    = 3
WAN_STEPS   = {"480p": 30, "720p": 50}[RESOLUTION]
WAN_SIZE    = {"480p": "832*480", "720p": "1280*704"}[RESOLUTION]
WAN_FPS     = 24                # TI2V-5B native frame rate
WAN_MAX_FRAMES = 121            # ~5 s; must be 4n+1
GPU_LOG     = OUT / "kaggle_runs.jsonl"
for d in (OUT / "shots", OUT / "music"):
    d.mkdir(parents=True, exist_ok=True)
""")

md("## 2. Logging helpers (same schema + hashing as `pipeline/utils.py`)")
code("""
import hashlib, json, subprocess, time
from datetime import datetime, timezone

def input_hash(payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()

def gpu_name():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"

GPU = gpu_name()
print("GPU:", GPU)

def log_run(*, stage, shot_id, model, params, seed, latency_ms, status="ok", error=None, **extra):
    rec = {"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "shot_id": shot_id,
           "model": model, "params": params, "seed": seed, "latency_ms": round(latency_ms, 1),
           "gpu_seconds": round(latency_ms / 1000, 1), "estimated_usd": 0.0,  # Kaggle free tier
           "cache_hit": False, "status": status, "error": error, "gpu": GPU, "source": "kaggle", **extra}
    with open(GPU_LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
    return rec

def timed(cmd, cwd=None):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    ms = (time.perf_counter() - t0) * 1000
    if p.returncode != 0:
        print(p.stdout[-2000:], p.stderr[-4000:])
    return p, ms

sb = json.loads((INPUT_DIR / "storyboard.json").read_text())
KF = INPUT_DIR / "outputs" / "keyframes"
print(sb["title"], "-", len(sb["shots"]), "shots")
""")

md("## 3. Wan 2.2 TI2V-5B setup")
code("""
%%bash
set -e
cd /kaggle/working
[ -d Wan2.2 ] || git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git
pip install -q -r Wan2.2/requirements.txt || true   # flash_attn may fail on T4/P100; SDPA fallback is used
pip install -q "huggingface_hub[cli]"
[ -d Wan2.2-TI2V-5B ] || huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir ./Wan2.2-TI2V-5B
""")

md("## 4. Generate Wan clips")
code("""
WAN_MODEL = "wan2.2-ti2v-5b"

def frames_for(sec):
    n = min(WAN_MAX_FRAMES, max(17, round(sec * WAN_FPS)))
    return 4 * ((n - 1) // 4) + 1   # snap to 4n+1

if RUN_WAN:
    for shot in sb["shots"]:
        sid = shot["id"]
        if shot["motion_mode"] != "wan" or (ONLY_SHOTS and sid not in ONLY_SHOTS):
            continue
        img = KF / f"{sid}.png"
        out = OUT / "shots" / f"{sid}_wan.mp4"
        prompt = (f"{shot['motion_prompt']}. {shot['image_prompt']}. "
                  f"{sb['character_description']}. {sb['style_block']}. Smooth, subtle, cinematic motion.")
        frames = frames_for(shot["duration_sec"])
        params = {"size": WAN_SIZE, "frames": frames, "steps": WAN_STEPS, "prompt": prompt,
                  "resolution": RESOLUTION}
        params["input_hash"] = input_hash({"model": WAN_MODEL, "seed": shot["seed"], **params})
        if not img.exists():
            log_run(stage="shots", shot_id=sid, model=WAN_MODEL, params=params, seed=shot["seed"],
                    latency_ms=0, status="error", error=f"missing keyframe {img.name}")
            continue
        cmd = ["python", "generate.py", "--task", "ti2v-5B", "--size", WAN_SIZE,
               "--ckpt_dir", str(WORK / "Wan2.2-TI2V-5B"), "--offload_model", "True",
               "--convert_model_dtype", "--t5_cpu", "--image", str(img), "--prompt", prompt,
               "--base_seed", str(shot["seed"]), "--frame_num", str(frames),
               "--sample_steps", str(WAN_STEPS), "--save_file", str(out)]
        print(f"[wan] {sid} {WAN_SIZE} {frames}f ...", flush=True)
        p, ms = timed(cmd, cwd=WORK / "Wan2.2")
        ok = p.returncode == 0 and out.exists()
        log_run(stage="shots", shot_id=sid, model=WAN_MODEL, params=params, seed=shot["seed"],
                latency_ms=ms, status="ok" if ok else "error",
                error=None if ok else p.stderr[-500:])
        print(f"  -> {'OK' if ok else 'FAILED'} in {ms/1000:.0f}s")
""")

md("""
## 5. ACE-Step 1.5 setup

> Check the [ACE-Step 1.5 README](https://github.com/ace-step/ACE-Step-1.5) for the current install
> and inference entry point; adjust `ACE_CMD` below if the CLI flags change.
""")
code("""
%%bash
set -e
cd /kaggle/working
[ -d ACE-Step-1.5 ] || git clone --depth 1 https://github.com/ace-step/ACE-Step-1.5.git
cd ACE-Step-1.5 && pip install -q -e . || pip install -q -r requirements.txt
""")

md("## 6. Generate 3 score candidates")
code("""
ACE_MODEL = "ace-step-1.5"
FILM_SEC = sum(s["duration_sec"] for s in sb["shots"]) + 4   # small tail; local stage trims/fades
SEEDS = [11, 22, 33][:N_SCORES]

def ACE_CMD(prompt, seconds, seed, out_path):
    # Template — verify flag names against the ACE-Step 1.5 README for your installed version.
    return ["python", "-m", "acestep.inference", "--prompt", prompt, "--lyrics", "[instrumental]",
            "--duration", str(int(seconds)), "--seed", str(seed), "--output", str(out_path)]

if RUN_MUSIC:
    prompt = f"{sb['music_cue']}, instrumental, film score, no vocals"
    for i, seed in enumerate(SEEDS, 1):
        out = OUT / "music" / f"score_candidate_{i}.wav"
        params = {"prompt": prompt, "duration": FILM_SEC, "candidate": i}
        params["input_hash"] = input_hash({"model": ACE_MODEL, "seed": seed, **params})
        print(f"[ace] candidate {i} seed={seed} ...", flush=True)
        p, ms = timed(ACE_CMD(prompt, FILM_SEC, seed, out), cwd=WORK / "ACE-Step-1.5")
        ok = p.returncode == 0 and out.exists()
        log_run(stage="music", shot_id=f"candidate_{i}", model=ACE_MODEL, params=params, seed=seed,
                latency_ms=ms, status="ok" if ok else "error", error=None if ok else p.stderr[-500:])
        print(f"  -> {'OK' if ok else 'FAILED'} in {ms/1000:.0f}s")
""")

md("## 7. Package outputs")
code("""
import shutil
shutil.make_archive(str(WORK / "heritage_gpu_outputs"), "zip", OUT)
print(open(GPU_LOG).read() if GPU_LOG.exists() else "no log")
print("Download /kaggle/working/heritage_gpu_outputs.zip")
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu"}},
      "nbformat": 4, "nbformat_minor": 5}
for c in nb["cells"]:
    c["source"] = c["source"].splitlines(keepends=True)
out = Path(__file__).resolve().parent / "kaggle_gpu_batch.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
print("wrote", out)
