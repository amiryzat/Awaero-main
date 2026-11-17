"""Offline A/B: run BOTH Moondream and Qwen over the SAME captured frames and
score which reads the ACTIVITY better. This is the test Chapter 4 reports, so it
checks the data first and logs every finding it can.

OFFLINE and SEQUENTIAL on purpose: both models over identical frames, one after
the other, so there is no GPU contention and no timing pressure - a clean
"which understands the scene?" comparison. Live latency is measured separately
by two live runs (live_system.py vs live_system.py qwen).

Both models get the SAME describe prompt and the SAME token budget, so the only
variable is the model. The activity is parsed from each description by
scene_activity.interpret (not by the model picking a label), so both models are
judged by the same rule.

Input : eval_frames/labels.csv  (file,label,time) from the web app Capture tab.
Output: eval_two_models_results.csv   - per frame, per model: description,
                                        prediction, correct, latency (raw record)
        eval_two_models_findings.md   - the written findings for Chapter 4
and a report printed to the terminal.

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
RESULTS_CSV = "eval_two_models_results.csv"
FINDINGS_MD = "eval_two_models_findings.md"
ACTIVITIES = ["STUDYING", "RESTING", "TRANSITIONAL", "UNOCCUPIED"]
MIN_PER_LABEL = 10         # RO-style target; below this a path's % is not trustworthy

PROMPT = "Describe the person in this image and what they are doing."
# Qwen3-VL reasons before it answers and the reasoning consumes num_predict, so
# a small cap returns EMPTY content (classify_passive.py warns of this). Both
# models get an ample, identical budget; Moondream simply stops early.
EVAL_OPTIONS = {"temperature": 0.0, "num_predict": 512}


def engines():
    import moondream_vlm
    import classify_passive
    return [
        ("Moondream", moondream_vlm.MODEL, None),    # not a thinking model
        ("Qwen", classify_passive.MODEL, None),      # default: content comes after its reasoning
    ]


def describe(model, image, think):
    import ollama
    kwargs = dict(model=model,
                  messages=[{"role": "user", "content": PROMPT, "images": [image]}],
                  options=EVAL_OPTIONS)
    if think is not None:
        kwargs["think"] = think
    return ollama.chat(**kwargs)["message"]["content"].strip()


# ---- data integrity ---------------------------------------------------------

def check_data(rows, eval_dir):
    """Validate the manifest BEFORE trusting any accuracy. Returns (ok_rows,
    warnings). A frame must exist, be non-empty and start with the JPEG magic
    bytes; the label must be known; filenames must be unique."""
    ok, warnings, seen = [], [], set()
    counts = {k: 0 for k in LABEL_TO_ACTIVITY}
    for r in rows:
        f, label = r.get("file", ""), r.get("label", "")
        if label not in LABEL_TO_ACTIVITY:
            warnings.append(f"unknown label {label!r} for {f}"); continue
        if f in seen:
            warnings.append(f"duplicate manifest row for {f}"); continue
        seen.add(f)
        path = os.path.join(eval_dir, f)
        try:
            with open(path, "rb") as fh:
                head = fh.read(3)
        except OSError:
            warnings.append(f"missing file: {f}"); continue
        if head[:2] != b"\xff\xd8":
            warnings.append(f"not a JPEG: {f}"); continue
        ok.append(r); counts[label] += 1
    for label, n in counts.items():
        if n == 0:
            warnings.append(f"NO frames for '{label}' - that path cannot be evaluated")
        elif n < MIN_PER_LABEL:
            warnings.append(f"only {n} '{label}' frames (<{MIN_PER_LABEL}); % is weak")
    return ok, warnings, counts


# ---- scoring (pure, unit-tested) --------------------------------------------

def summarise(records, names):
    """records: [{engine, true, pred, latency_s}]. -> per-engine stats incl.
    per-activity recall and the count of unparseable ('?') predictions."""
    out = {}
    for name in names:
        rs = [r for r in records if r["engine"] == name]
        conf = {t: {p: 0 for p in ACTIVITIES + ["?"]} for t in ACTIVITIES}
        for r in rs:
            p = r["pred"] if r["pred"] in ACTIVITIES else "?"
            conf[r["true"]][p] += 1
        correct = sum(r["pred"] == r["true"] for r in rs)
        n = len(rs)
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        per_act = {}
        for t in ACTIVITIES:
            tot = sum(conf[t].values())
            per_act[t] = {"n": tot, "correct": conf[t][t],
                          "pct": round(100 * conf[t][t] / tot, 1) if tot else None}
        out[name] = {
            "n": n, "correct": correct,
            "pct": round(100 * correct / n, 1) if n else 0.0,
            "unparsed": sum(1 for r in rs if r["pred"] not in ACTIVITIES),
            "latency_mean": round(sum(lat) / len(lat), 2) if lat else None,
            "latency_max": round(max(lat), 2) if lat else None,
            "per_activity": per_act, "confusion": conf,
        }
    return out


def agreement(per_frame, names):
    """How often the two engines PREDICT THE SAME activity (right or wrong), and
    the frames where they differ - the interesting cases for the write-up."""
    if len(names) != 2:
        return None, []
    a, b = names
    agree = 0
    disagree = []
    for fr in per_frame:
        pa, pb = fr["preds"].get(a), fr["preds"].get(b)
        if pa == pb:
            agree += 1
        else:
            disagree.append({"file": fr["file"], "true": fr["true"], a: pa, b: pb})
    n = len(per_frame)
    return (round(100 * agree / n, 1) if n else None), disagree


# ---- run + report -----------------------------------------------------------

def run(rows, eng, eval_dir, log=print):
    per_frame = []
    for i, r in enumerate(rows, 1):
        image = open(os.path.join(eval_dir, r["file"]), "rb").read()
        true = LABEL_TO_ACTIVITY[r["label"]]
        fr = {"file": r["file"], "true": true, "preds": {}, "descs": {}, "lats": {}}
        line = f"[{i}/{len(rows)}] {r['file']:<30} true={true:<12}"
        for name, model, think in eng:
            t0 = time.time()
            try:
                desc = describe(model, image, think)
            except Exception as e:
                log(f"\n  {name} failed on {r['file']}: {e}")
                desc = ""
            dt = time.time() - t0
            pred = scene_activity.activity(desc)
            fr["preds"][name], fr["descs"][name], fr["lats"][name] = pred, desc, dt
            line += f" | {name}:{'OK ' if pred == true else 'XX '}{pred:<12}"
        per_frame.append(fr)
        log(line)
    return per_frame


def to_records(per_frame, names):
    return [{"engine": n, "true": fr["true"], "pred": fr["preds"][n],
             "latency_s": fr["lats"][n]} for fr in per_frame for n in names]


def write_results_csv(per_frame, names, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "true", "engine", "pred",
                                          "correct", "latency_s", "description"])
        w.writeheader()
        for fr in per_frame:
            for n in names:
                w.writerow({"file": fr["file"], "true": fr["true"], "engine": n,
                            "pred": fr["preds"][n], "correct": fr["preds"][n] == fr["true"],
                            "latency_s": round(fr["lats"][n], 2),
                            "description": fr["descs"][n]})


def write_findings_md(path, counts, summary, names, agree, disagree, warnings):
    L = []
    L.append("# Two-VLM activity A/B - findings\n")
    L.append(f"_Generated by eval_two_models.py on {time.strftime('%Y-%m-%d %H:%M')}._\n")
    L.append("Both models saw the **same frames**, the **same prompt** "
             f"(`{PROMPT}`) and the same token budget (`{EVAL_OPTIONS}`); the "
             "activity is parsed from each description by the same rule "
             "(`scene_activity.interpret`). Sequential, so no GPU contention.\n")
    L.append("## Dataset\n")
    L.append("| activity | frames |")
    L.append("|---|---|")
    for label, n in counts.items():
        L.append(f"| {label} | {n} |")
    L.append(f"| **total** | **{sum(counts.values())}** |\n")
    if warnings:
        L.append("**Data warnings:**\n")
        for w in warnings:
            L.append(f"- {w}")
        L.append("")
    L.append("## Accuracy\n")
    L.append("| model | overall | " + " | ".join(ACTIVITIES) + " | unparsed | latency mean/max |")
    L.append("|---|---|" + "---|" * len(ACTIVITIES) + "---|---|")
    for name in names:
        s = summary[name]
        cells = []
        for t in ACTIVITIES:
            pa = s["per_activity"][t]
            cells.append(f"{pa['pct']}% ({pa['correct']}/{pa['n']})" if pa["pct"] is not None else "-")
        lat = f"{s['latency_mean']}s / {s['latency_max']}s" if s["latency_mean"] is not None else "-"
        L.append(f"| **{name}** | {s['pct']}% ({s['correct']}/{s['n']}) | "
                 + " | ".join(cells) + f" | {s['unparsed']} | {lat} |")
    L.append("")
    for name in names:
        L.append(f"### {name} confusion (rows = actual, cols = predicted)\n")
        L.append("| actual \\\\ pred | " + " | ".join(a[:5] for a in ACTIVITIES) + " | ? |")
        L.append("|---|" + "---|" * (len(ACTIVITIES) + 1))
        for t in ACTIVITIES:
            row = summary[name]["confusion"][t]
            L.append(f"| {t} | " + " | ".join(str(row[p]) for p in ACTIVITIES) + f" | {row['?']} |")
        L.append("")
    if agree is not None:
        L.append(f"## Model agreement\n\nThe two models predicted the same "
                 f"activity on **{agree}%** of frames.\n")
        if disagree:
            L.append(f"**{len(disagree)} disagreements** (where they differ - inspect these):\n")
            L.append("| frame | true | " + " | ".join(names) + " |")
            L.append("|---|---|" + "---|" * len(names))
            for d in disagree[:40]:
                L.append(f"| {d['file']} | {d['true']} | "
                         + " | ".join(d[n] for n in names) + " |")
            L.append("")
    L.append("## Per-frame detail\n\nSee `eval_two_models_results.csv` for every "
             "frame's description and prediction from each model.\n")
    with open(path, "w") as f:
        f.write("\n".join(L))


def main():
    manifest = os.path.join(EVAL_DIR, "labels.csv")
    if not os.path.exists(manifest):
        raise SystemExit(f"No {manifest}. Capture frames from the web app Capture tab first.")
    rows = list(csv.DictReader(open(manifest)))
    rows, warnings, counts = check_data(rows, EVAL_DIR)
    if warnings:
        print("DATA CHECK:")
        for w in warnings:
            print("  !", w)
        print()
    if not rows:
        raise SystemExit("No valid labelled frames to evaluate.")

    eng = engines()
    names = [n for n, _, _ in eng]
    print(f"{len(rows)} valid frames x {len(eng)} models, sequential. Be patient.\n")
    per_frame = run(rows, eng, EVAL_DIR)

    summary = summarise(to_records(per_frame, names), names)
    agree, disagree = agreement(per_frame, names)

    print("\n================  VLM A/B: activity accuracy  ================")
    for name in names:
        s = summary[name]
        lat = f"{s['latency_mean']}s mean / {s['latency_max']}s max" if s["latency_mean"] is not None else "-"
        print(f"{name:10s}  {s['correct']}/{s['n']} = {s['pct']}%   unparsed {s['unparsed']}   latency {lat}")
    if agree is not None:
        print(f"agreement: {agree}%   disagreements: {len(disagree)}")
    print("=============================================================")

    write_results_csv(per_frame, names, RESULTS_CSV)
    write_findings_md(FINDINGS_MD, counts, summary, names, agree, disagree, warnings)
    print(f"\nWrote {RESULTS_CSV} (per-frame detail) and {FINDINGS_MD} (findings for Ch4).")


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
    assert s["Moondream"]["correct"] == 2 and s["Moondream"]["pct"] == 66.7
    assert s["Moondream"]["latency_mean"] == 1.0 and s["Moondream"]["latency_max"] == 1.2
    assert s["Moondream"]["per_activity"]["RESTING"]["pct"] == 0.0        # missed the one RESTING
    assert s["Moondream"]["per_activity"]["STUDYING"]["pct"] == 100.0
    assert s["Qwen"]["unparsed"] == 1 and s["Qwen"]["confusion"]["UNOCCUPIED"]["?"] == 1
    assert summarise([], ["Moondream"])["Moondream"]["pct"] == 0.0        # no frames: no crash
    # agreement: build two per-frame rows, one agree one disagree
    pf = [
        {"file": "a.jpg", "true": "STUDYING", "preds": {"Moondream": "STUDYING", "Qwen": "STUDYING"}},
        {"file": "b.jpg", "true": "RESTING", "preds": {"Moondream": "STUDYING", "Qwen": "RESTING"}},
    ]
    ag, dis = agreement(pf, ["Moondream", "Qwen"])
    assert ag == 50.0 and len(dis) == 1 and dis[0]["file"] == "b.jpg"
    # check_data: a bad magic byte and a missing file both get flagged
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "studying_1.jpg"), "wb").write(b"\xff\xd8junk")
        open(os.path.join(d, "resting_1.jpg"), "wb").write(b"notjpeg")
        ok, warn, cnt = check_data(
            [{"file": "studying_1.jpg", "label": "studying"},
             {"file": "resting_1.jpg", "label": "resting"},
             {"file": "gone.jpg", "label": "empty"}], d)
        assert len(ok) == 1 and ok[0]["file"] == "studying_1.jpg"
        assert any("not a JPEG" in w for w in warn) and any("missing file" in w for w in warn)
        assert cnt["studying"] == 1 and cnt["resting"] == 0
    print("eval_two_models selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        main()
