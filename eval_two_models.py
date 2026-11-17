"""Offline A/B: run BOTH Moondream and Qwen over the SAME captured frames and
score which reads the ACTIVITY better.

This is the test that decides the architecture (see docs/RESUME.md). It is
OFFLINE and SEQUENTIAL on purpose: both models over identical frames, one after
the other, so there is no GPU contention and no timing pressure - a clean
"which understands the scene?" comparison. Live latency is measured separately
by two live runs (live_system.py vs live_system.py qwen).

Both models get the SAME describe prompt and the SAME token budget, so the only
variable is the model. The activity is parsed from each description by
scene_activity.interpret.

Input : eval_frames/labels.csv  (file,label,time) from the web app Capture tab.
Output: a per-model accuracy + confusion table, and eval_two_models_results.csv.

    python eval_two_models.py            # run both over eval_frames/
    python eval_two_models.py selftest   # scoring logic only, no models
"""

import csv
import os
import sys
import time

import scene_activity
from scene_activity import LABEL_TO_ACTIVITY

EVAL_DIR = "eval_frames"
RESULTS = "eval_two_models_results.csv"
ACTIVITIES = ["STUDYING", "RESTING", "TRANSITIONAL", "UNOCCUPIED"]

# Same prompt + token budget for both, so the model is the only variable. A
# description task needs more than the one-letter production cap, hence a local
# budget rather than reusing either model's deployed OPTIONS.
PROMPT = "Describe the person in this image and what they are doing."
EVAL_OPTIONS = {"temperature": 0.0, "num_predict": 96}


def engines():
    """(name, model, think) for each engine. Imported lazily so `selftest` and
    --help do not require ollama or the model configs to be importable."""
    import moondream_vlm
    import classify_passive
    return [
        ("Moondream", moondream_vlm.MODEL, None),    # not a thinking model
        ("Qwen", classify_passive.MODEL, False),     # thinking off: plain description
    ]


def describe(model, image, think):
    import ollama
    kwargs = dict(model=model,
                  messages=[{"role": "user", "content": PROMPT, "images": [image]}],
                  options=EVAL_OPTIONS)
    if think is not None:
        kwargs["think"] = think
    return ollama.chat(**kwargs)["message"]["content"].strip()


def summarise(records, names):
    """records: [{engine, true, pred, latency_s}]. Pure, model-free, so it is the
    unit under selftest. -> {engine: {n, correct, pct, latency_mean, confusion}}."""
    out = {}
    for name in names:
        rs = [r for r in records if r["engine"] == name]
        conf = {t: {p: 0 for p in ACTIVITIES + ["?"]} for t in ACTIVITIES}
        correct = 0
        for r in rs:
            p = r["pred"] if r["pred"] in ACTIVITIES else "?"
            conf[r["true"]][p] += 1
            correct += (r["pred"] == r["true"])
        n = len(rs)
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        out[name] = {
            "n": n,
            "correct": correct,
            "pct": round(100 * correct / n, 1) if n else 0.0,
            "latency_mean": round(sum(lat) / len(lat), 2) if lat else None,
            "confusion": conf,
        }
    return out


def _print_report(summary, names):
    print("\n==================  VLM A/B: activity accuracy  ==================")
    for name in names:
        s = summary[name]
        lat = f"{s['latency_mean']}s mean" if s["latency_mean"] is not None else "-"
        print(f"\n{name:10s}  {s['correct']}/{s['n']} = {s['pct']}%   latency {lat}")
        print(f"  {'actual \\\\ pred':<16}" + "".join(f"{a[:5]:>7}" for a in ACTIVITIES) + f"{'?':>7}")
        for t in ACTIVITIES:
            row = summary[name]["confusion"][t]
            print(f"  {t:<16}" + "".join(f"{row[p]:>7}" for p in ACTIVITIES) + f"{row['?']:>7}")
    print("\n=================================================================")


def main():
    manifest = os.path.join(EVAL_DIR, "labels.csv")
    if not os.path.exists(manifest):
        raise SystemExit(f"No {manifest}. Capture frames from the web app Capture tab first.")
    rows = [r for r in csv.DictReader(open(manifest)) if r.get("label") in LABEL_TO_ACTIVITY]
    if not rows:
        raise SystemExit("No labelled frames yet.")
    eng = engines()
    names = [n for n, _, _ in eng]
    print(f"{len(rows)} frames, {len(eng)} models. This runs sequentially; be patient.\n")

    records, detail = [], []
    for i, r in enumerate(rows, 1):
        path = os.path.join(EVAL_DIR, r["file"])
        try:
            image = open(path, "rb").read()
        except OSError:
            print(f"  skip (missing): {r['file']}")
            continue
        true = LABEL_TO_ACTIVITY[r["label"]]
        line = f"[{i}/{len(rows)}] {r['file']:<34} true={true:<12}"
        for name, model, think in eng:
            t0 = time.time()
            try:
                desc = describe(model, image, think)
            except Exception as e:
                print(f"\n  {name} failed on {r['file']}: {e}")
                desc = ""
            dt = time.time() - t0
            pred = scene_activity.activity(desc)
            hit = "OK " if pred == true else "XX "
            line += f" | {name}:{hit}{pred:<12}"
            records.append({"engine": name, "true": true, "pred": pred, "latency_s": dt})
            detail.append({"file": r["file"], "true": true, "engine": name,
                           "pred": pred, "correct": pred == true,
                           "latency_s": round(dt, 2), "description": desc})
        print(line)

    summary = summarise(records, names)
    _print_report(summary, names)

    with open(RESULTS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "true", "engine", "pred",
                                          "correct", "latency_s", "description"])
        w.writeheader()
        w.writerows(detail)
    print(f"\nWrote {RESULTS} ({len(detail)} rows). Winner = higher accuracy on your scene set.")


def _selftest():
    recs = [
        {"engine": "Moondream", "true": "STUDYING", "pred": "STUDYING", "latency_s": 1.0},
        {"engine": "Moondream", "true": "RESTING", "pred": "STUDYING", "latency_s": 1.2},
        {"engine": "Moondream", "true": "UNOCCUPIED", "pred": "UNOCCUPIED", "latency_s": 0.8},
        {"engine": "Qwen", "true": "STUDYING", "pred": "STUDYING", "latency_s": 12.0},
        {"engine": "Qwen", "true": "RESTING", "pred": "RESTING", "latency_s": 13.0},
        {"engine": "Qwen", "true": "UNOCCUPIED", "pred": "?", "latency_s": 11.0},
    ]
    s = summarise(recs, ["Moondream", "Qwen"])
    assert s["Moondream"]["n"] == 3 and s["Moondream"]["correct"] == 2
    assert s["Moondream"]["pct"] == 66.7 and s["Moondream"]["latency_mean"] == 1.0
    assert s["Qwen"]["correct"] == 2 and s["Qwen"]["pct"] == 66.7
    # a wrong prediction lands in the right confusion cell
    assert s["Moondream"]["confusion"]["RESTING"]["STUDYING"] == 1
    assert s["Qwen"]["confusion"]["UNOCCUPIED"]["?"] == 1          # unparseable -> ?
    assert summarise([], ["Moondream"])["Moondream"]["pct"] == 0.0  # no frames: no crash
    print("eval_two_models selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        main()
