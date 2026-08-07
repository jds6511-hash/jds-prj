"""[reduce 퇴화 2차 — 인용 상한 규칙 효과 측정]

1차 결론: repetition_penalty·no_repeat_ngram은 무효(seg 번호는 서로 다른 토큰열).
map 중복줄 병합은 문장 1개 -> 398개로 구조를 살렸으나 한 문장이 여전히 251개(70%)를
인용했다. 원인은 reduce 규칙 1("중복 사건은 하나로 합칠 것")에 **인용 개수 상한이
없다**는 것 — 캡션이 거의 동일한 영상에서 모델이 "전부 같은 사건"으로 이행한다.
"""
import json, re, sys, time
from pathlib import Path
ROOT = Path("/ssd/<SERVER_USER>/jds-prj")
sys.path.insert(0, str(ROOT / "src"))
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from m8_report import parse_citations, drop_truncated_tail, narration

VID = "yunnamnopo_tongyeong"
rep = json.loads((ROOT / f"work/{VID}/report.json").read_text(encoding="utf-8"))
partials = rep["map_raw_outputs"]
NSEG = len(json.loads((ROOT / f"work/{VID}/segments.json").read_text(encoding="utf-8"))["segments"])
CAP = 8


def merge_dup_lines(part: str) -> str:
    rows = []
    for line in part.splitlines():
        t = line.strip()
        if not t.startswith("-"):
            continue
        narr, cites = narration(t), [int(m) for m in re.findall(r"seg\s*#\s*(\d+)", t, re.I)]
        if rows and rows[-1][0] == narr:
            rows[-1][1].extend(cites)
        else:
            rows.append([narr, cites])
    return "\n".join(f"- {n} [{', '.join(f'seg#{c}' for c in sorted(set(cs)))}]" for n, cs in rows)


def reduce_prompt(parts, cap: bool) -> str:
    rules = ["1. 중복 사건은 하나로 합칠 것.",
             "2. 시간 순서([seg#N] 번호 순)로 재정렬할 것.",
             "3. 부분 리포트에 없는 새로운 사실을 절대 추가하지 말 것.",
             "4. 각 문장의 [seg#N] 인용은 부분 리포트의 인용을 그대로 유지할 것."]
    if cap:
        rules.append(
            f"5. **한 문장의 인용은 최대 {CAP}개.** 같은 장면이 더 길게 이어지면 "
            f"하나로 뭉치지 말고 시간 구간을 나눠 여러 문장으로 쓸 것 "
            f"(예: 앞 구간·중간 구간·뒤 구간). 세그먼트 번호만 길게 나열하지 말 것.")
    return ("아래는 같은 영상의 구간별 부분 리포트들입니다. 하나의 최종 리포트로 통합하세요.\n"
            "규칙:\n" + "\n".join(rules) +
            "\n출력 형식은 동일: '- 문장 [seg#N]'. 그 외 텍스트 금지.\n\n부분 리포트:\n"
            + "\n\n---\n\n".join(parts))


MODEL = "Qwen/Qwen2.5-7B-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
mdl = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="auto")


def run(prompt):
    text = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                   tokenize=False, add_generation_prompt=True)
    inp = tok([text], return_tensors="pt").to(mdl.device)
    t0 = time.time()
    with torch.inference_mode():
        out = mdl.generate(**inp, max_new_tokens=16384, do_sample=False)
    return (tok.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip(),
            round(time.time() - t0, 1))


merged = [merge_dup_lines(p) for p in partials]
ARMS = [("cap_only",  reduce_prompt(partials, True)),
        ("cap_merge",  reduce_prompt(merged, True))]
res = {}
for name, prompt in ARMS:
    raw, sec = run(prompt)
    sents, tail = drop_truncated_tail(parse_citations(raw))
    c = [len(s["cites"]) for s in sents] or [0]
    over = sum(1 for x in c if x > CAP)
    res[name] = {"n_sentences": len(sents), "cites_max": max(c),
                 "cites_max_frac": round(max(c) / NSEG, 3),
                 "cites_mean": round(sum(c) / len(c), 2),
                 "over_cap": over, "cited_uniq": len({x for s in sents for x in s["cites"]}),
                 "narration_blank": sum(1 for s in sents if not narration(s["text"])),
                 "degenerate": bool(max(c) > NSEG * 0.5),
                 "sec": sec, "out_chars": len(raw),
                 "truncated_tail": tail[:80] if tail else None, "head": raw[:600]}
    print(f"[{name:10s}] 문장 {len(sents):4d} cites_max {max(c):3d} ({max(c)/NSEG:.0%}) "
          f"상한초과문장 {over:3d} 고유인용 {res[name]['cited_uniq']:3d} {sec}s", flush=True)

p = ROOT / "results/_probe_reduce_citecap.json"
p.write_text(json.dumps({"video_id": VID, "n_segments": NSEG, "cite_cap": CAP,
                         "arms": res}, ensure_ascii=False, indent=2), encoding="utf-8")
print("->", p)
