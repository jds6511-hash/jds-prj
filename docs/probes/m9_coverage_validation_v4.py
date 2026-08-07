"""[coverage judge 4차 — 리포트 분할 판정(OR 결합). dev 전용, test 미접촉]

3차 결론: 프롬프트 문구 조정은 한계다(현행 0.83/재현 0.73, "주된 일만" 지시는 재현
0.33으로 역효과). 구조를 바꾼다 — 리포트를 N줄씩 잘라 각각 판정하고 OR로 합친다.
호출당 건초더미가 작아져 재현이 오르는지, 대신 특이도가 내려가는지 함께 잰다.
"""
import json, random, re, sys
from pathlib import Path
ROOT = Path("/ssd/<SERVER_USER>/jds-prj")
sys.path.insert(0, str(ROOT / "src"))
import torch                                                     # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer     # noqa: E402
import common                                                    # noqa: E402
from m9_report_eval import (_COVERAGE_PROMPT, _clean_caption, _sanitize,
                            _parse_verdict, _parse_ok)           # noqa: E402

VID = "kheritage_grave_excavation"
N = 15

cfg = common.load_config(str(ROOT / "config_server.yaml"))
doc = common.load_segments(common.work_dir(cfg, VID) / "segments.json",
                           require=["subtitle", "caption"], seg_len=cfg["seg_len_sec"])
segs = [s for s in doc["segments"]
        if not common.is_corrupted_caption(s["caption"]) and len(s["caption"]) > 60]


def first_clause(cap):
    parts = re.split(r"[.。]|(?<=습니다)|(?<=이다)", cap.strip())
    return next((x.strip() for x in parts if x and len(x.strip()) >= 15), cap[:60])


def nouns(t):
    return {w for w in re.findall(r"[가-힣]{3,}", t)}


rng = random.Random(cfg["seed"])
inside = rng.sample(segs, 25)
lines = [f'- {first_clause(s["caption"])} [seg#{s["idx"]}]' for s in inside]
synth = "\n".join(lines)
in_nouns, in_ids = nouns(synth), {s["idx"] for s in inside}
outside = [s for s in segs if s["idx"] not in in_ids
           and len(nouns(_clean_caption(s["caption"])) & in_nouns) <= 3]
cases = ([{"gold": True, "seg": s} for s in rng.sample(inside, N)]
         + [{"gold": False, "seg": s} for s in rng.sample(outside, min(N, len(outside)))])
print(f"합성 리포트 {len(synth)}자 / {len(lines)}줄 / 제외 후보 {len(outside)}")

MODEL = cfg["judge_model"]
tok = AutoTokenizer.from_pretrained(MODEL)
mdl = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="auto")


def gen(prompt, mx=128):
    text = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                   tokenize=False, add_generation_prompt=True)
    inp = tok([text], return_tensors="pt").to(mdl.device)
    with torch.inference_mode():
        o = mdl.generate(**inp, max_new_tokens=mx, do_sample=False)
    return tok.decode(o[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip()


def judge_chunked(seg, chunk_lines):
    """리포트를 chunk_lines줄씩 잘라 각각 판정, 하나라도 true면 covered."""
    calls = 0
    for i in range(0, len(lines), chunk_lines):
        part = "\n".join(lines[i:i + chunk_lines])
        p = _COVERAGE_PROMPT.format(idx=seg["idx"], subtitle=_sanitize(seg["subtitle"]),
                                    caption=_sanitize(_clean_caption(seg["caption"])),
                                    report=part)
        calls += 1
        if _parse_verdict(gen(p)):
            return True, calls
    return False, calls


out = {"note": "dev 전용 coverage 분할 판정 측정. test 미접촉.", "video_id": VID,
       "report_lines": len(lines), "n_per_kind": N, "arms": {}}
for name, cl in [("whole", len(lines)), ("chunk8", 8), ("chunk4", 4)]:
    rows, total_calls = [], 0
    for c in cases:
        v, calls = judge_chunked(c["seg"], cl)
        total_calls += calls
        rows.append({"gold": c["gold"], "seg_idx": c["seg"]["idx"], "verdict": v,
                     "cap": _clean_caption(c["seg"]["caption"])[:90]})
    tp = [x for x in rows if x["gold"]]
    tn = [x for x in rows if not x["gold"]]
    a = {"accuracy": round(sum(x["verdict"] == x["gold"] for x in rows) / len(rows), 3),
         "recall_in": round(sum(x["verdict"] for x in tp) / len(tp), 2),
         "specificity_out": round(sum(not x["verdict"] for x in tn) / len(tn), 2),
         "judge_calls": total_calls, "calls_per_case": round(total_calls / len(rows), 1),
         "cases": rows}
    out["arms"][name] = a
    print(f"[{name:8s}] 정확도 {a['accuracy']:.2f} | 포함재현 {a['recall_in']:.2f} "
          f"제외특이도 {a['specificity_out']:.2f} | 호출/건 {a['calls_per_case']}", flush=True)

p = ROOT / "results/_probe_coverage_validation4.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("->", p)
