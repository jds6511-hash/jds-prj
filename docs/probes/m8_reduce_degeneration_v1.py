"""[reduce 퇴화 재현·해소 측정 — 진단용, 채택 판단은 결과 보고 후]

yunnamnopo_tongyeong의 reduce가 불릿 1개에 seg#0~356을 나열하고 끝났다(퇴화).
map 출력은 report.json에 보존돼 있으므로 map을 다시 돌리지 않고 reduce만 재현한다.
비교 arm: 현행(greedy) / repetition_penalty 2종 / no_repeat_ngram / map 중복줄 병합.
"""
import json, re, sys, time
from pathlib import Path
# 저장소 루트에서 도출한다. 서버 절대경로를 박으면 계정명이 공개 저장소에
# 노출되고, 다른 기계에서 못 돌린다. 다른 프로브와 같은 방식이다.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from m8_report import build_reduce_prompt, parse_citations, drop_truncated_tail, narration

VID = "yunnamnopo_tongyeong"
rep = json.loads((ROOT / f"work/{VID}/report.json").read_text(encoding="utf-8"))
partials = rep["map_raw_outputs"]
NSEG = len(json.loads((ROOT / f"work/{VID}/segments.json").read_text(encoding="utf-8"))["segments"])


def merge_dup_lines(part: str) -> str:
    """서술이 직전 불릿과 완전히 같은 줄을 앞줄에 병합한다(인용은 합쳐 보존).

    캡션이 반복적인 구간이 동일 불릿 8~10줄을 만들고, 그 벽이 reduce를 번호 나열로
    밀어넣는다는 가설을 재려는 것. 인용을 버리면 coverage가 떨어지므로 합친다.
    """
    rows = []              # [narr, [cites...]]
    for line in part.splitlines():
        t = line.strip()
        if not t.startswith("-"):
            continue
        narr = narration(t)
        cites = [int(m) for m in re.findall(r"seg\s*#\s*(\d+)", t, re.IGNORECASE)]
        if rows and rows[-1][0] == narr:
            rows[-1][1].extend(cites)
        else:
            rows.append([narr, cites])
    return "\n".join(
        f"- {narr} [{', '.join(f'seg#{c}' for c in sorted(set(cs)))}]" for narr, cs in rows)


MODEL = "Qwen/Qwen2.5-7B-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
mdl = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.bfloat16, device_map="auto")


def run(prompt, **gen):
    msgs = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inp = tok([text], return_tensors="pt").to(mdl.device)
    t0 = time.time()
    with torch.inference_mode():
        out = mdl.generate(**inp, max_new_tokens=16384, do_sample=False, **gen)
    return (tok.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip(),
            round(time.time() - t0, 1), inp.input_ids.shape[1])


base = build_reduce_prompt(partials)
merged = build_reduce_prompt([merge_dup_lines(p) for p in partials])
nb, nm = len(tok(base).input_ids), len(tok(merged).input_ids)
bul_b = sum(1 for p in partials for l in p.splitlines() if l.strip().startswith("-"))
bul_m = sum(1 for p in partials for l in merge_dup_lines(p).splitlines() if l.strip().startswith("-"))
print(f"[입력] 현행 {nb}토큰/불릿{bul_b} · 중복병합 {nm}토큰/불릿{bul_m}", flush=True)

ARMS = [
    ("current_greedy",     base,   {}),
    ("rep_pen_1.05",       base,   {"repetition_penalty": 1.05}),
    ("rep_pen_1.10",       base,   {"repetition_penalty": 1.10}),
    ("no_repeat_ngram_8",  base,   {"no_repeat_ngram_size": 8}),
    ("merge_dup_greedy",   merged, {}),
]
res = {}
for name, prompt, gen in ARMS:
    raw, sec, ntok = run(prompt, **gen)
    sents, tail = drop_truncated_tail(parse_citations(raw))
    c = [len(s["cites"]) for s in sents] or [0]
    blank = sum(1 for s in sents if not narration(s["text"]))
    res[name] = {"n_sentences": len(sents), "cites_max": max(c),
                 "cites_max_frac": round(max(c) / NSEG, 3),
                 "cites_mean": round(sum(c) / len(c), 2),
                 "narration_blank": blank,
                 "cited_uniq": len({x for s in sents for x in s["cites"]}),
                 "degenerate": bool(max(c) > NSEG * 0.5),
                 "sec": sec, "in_tokens": ntok, "out_chars": len(raw),
                 "truncated_tail": tail[:80] if tail else None,
                 "head": raw[:500]}
    print(f"[{name:18s}] 문장 {len(sents):4d} cites_max {max(c):3d} ({max(c)/NSEG:.0%}) "
          f"고유인용 {res[name]['cited_uniq']:3d} 서술공백 {blank} {sec}s", flush=True)

p = ROOT / "results/_probe_reduce_degeneration.json"
p.write_text(json.dumps({"video_id": VID, "n_segments": NSEG, "model": MODEL,
                         "map_bullets": {"orig": bul_b, "merged": bul_m},
                         "arms": res}, ensure_ascii=False, indent=2), encoding="utf-8")
print("->", p)
