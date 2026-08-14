"""[M8 리포트 품질·절단 진단 — GPU 불필요, 저장된 산출물만 읽는다]

**왜.** 발표 자료에 M8 산출물을 실으면서 실물을 열어보니 "요약"이라 부르기
어려웠다(2026-08-14). 구간 설명을 시간순으로 이어 붙인 형태이고, 한 영상은
전체의 34%만 다룬 채 문장 중간에서 끝나 있었다. 체감으로 넘기지 않고 잰다.

**세 가지를 잰다.**

1. **절단 지점** — map_raw_outputs와 reduce raw_output의 인용 범위를 비교해
   어느 단계에서 끊겼는지 가른다. map이 끝까지 갔는데 reduce가 앞에서 멈췄으면
   절단은 reduce다.
2. **소량 CJK 혼입 노출** — `common.is_corrupted_caption`은 한자·가나가 3글자
   이상이어야 잡는다. 1~2글자는 통과해 인덱스에 남는데, 리포트 모델이 그 지점에서
   언어를 전환하며 생성을 끝내는 것이 실측됐다(panibottle seg 88의 "靠垫" 2글자가
   리포트의 66%를 날렸다). 전 인덱스에서 그런 캡션이 몇 건인지 센다.
3. **요약성 지표** — 압축률·문장당 인용 폭·인용 순차성·문체 반복. 요약이라면
   압축률이 낮고 인용 폭이 넓어야 한다. 프롬프트를 고치기 **전에** 이 지표를
   고정해 둔다(고친 뒤에 정하면 결과를 보고 기준을 맞추게 된다).

**한계.** 표본은 저장된 리포트 4편뿐이고, 전부 같은 모델(Qwen2.5-7B-Instruct)·
같은 분할(60구간·겹침 5)로 만든 것이다. 문체 지표는 이 과제용으로 만든 것이며
요약 품질의 표준 척도가 아니다 — 판정선은 사전등록 문서에 따로 적는다.

재현: python docs/probes/m8_report_quality.py
"""
import json
import re
import sys
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                            # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
CAPDIR = OUT / "m8m9_capture"

CITE = re.compile(r"seg#(\d+)")
CJK = re.compile(r"[一-鿿぀-ヿ]")


def cites(text):
    return [int(x) for x in CITE.findall(text or "")]


def truncation(rep):
    """map/reduce 중 어디서 끊겼는지. 단일 호출 리포트는 map 단계가 없다."""
    partials = rep.get("map_raw_outputs") or []
    raw = rep.get("raw_output", "")
    rc = cites(raw)
    if not partials:
        return {"mode": "single_call", "reduce_max_cite": max(rc) if rc else None}
    mc = [c for p in partials for c in cites(p)]
    per_chunk = []
    for i, p in enumerate(partials):
        c = cites(p)
        per_chunk.append({"chunk": i, "chars": len(p),
                          "cite_min": min(c) if c else None,
                          "cite_max": max(c) if c else None})
    map_max = max(mc) if mc else None
    red_max = max(rc) if rc else None
    lost = None
    if map_max is not None and red_max is not None:
        lost = round(1 - (red_max + 1) / (map_max + 1), 4)
    return {"mode": "map_reduce", "per_chunk": per_chunk,
            "map_max_cite": map_max, "map_unique_cites": len(set(mc)),
            "reduce_max_cite": red_max, "reduce_chars": len(raw),
            "reduce_fraction_lost": lost,
            "stage": ("reduce" if (lost or 0) > 0.1 else "none_or_map"),
            "truncated_tail": rep.get("truncated_tail")}


def summariness(rep, n_seg):
    """요약성 — 압축률·인용 폭·순차성·문체 반복."""
    s = rep["sentences"]
    if not s:
        return {"n_sentences": 0}
    cs = [x["cites"] for x in s if x["cites"]]
    covered = sorted({c for x in s for c in x["cites"]})
    firsts = [min(c) for c in cs]
    mono = sum(1 for a, b in zip(firsts, firsts[1:]) if b >= a)
    ends = collections.Counter(
        re.sub(r"\s*\[seg#.*", "", x["text"]).strip()[-6:] for x in s)
    heads = collections.Counter(x["text"].split()[0] for x in s if x["text"].split())
    span = [max(c) - min(c) + 1 for c in cs]
    # 인용 폭이 넓다고 요약은 아니다. 짧은 문장에 번호만 무더기로 붙이는 **몰아쓰기**가
    # 같은 폭을 만든다(yunnamnopo: 본문 20자에 70구간 인용). 본문 글자수를 인용 수로
    # 나눠 가른다 — 진짜로 묶은 문장은 인용당 서술량이 있어야 한다.
    cpc = [len(_body(x["text"])) / len(x["cites"]) for x in s if x["cites"]]
    dump = [x["sent_id"] for x in s
            if len(x["cites"]) >= 10 and len(_body(x["text"])) / len(x["cites"]) < 5]
    return {
        "chars_per_cite_mean": round(sum(cpc) / len(cpc), 2),
        "cite_dump_sentences": len(dump),
        "n_sentences": len(s),
        "n_segments": n_seg,
        "n_covered_segments": len(covered),
        "coverage_of_video": round(len(covered) / n_seg, 4) if n_seg else None,
        "sentences_per_covered_segment": round(len(s) / len(covered), 4) if covered else None,
        "cite_span_mean": round(sum(span) / len(span), 3),
        "monotonic_ratio": round(mono / (len(firsts) - 1), 4) if len(firsts) > 1 else None,
        "top_ending": ends.most_common(1)[0][0],
        "top_ending_ratio": round(ends.most_common(1)[0][1] / len(s), 4),
        "top_head_word": heads.most_common(1)[0][0] if heads else None,
        "top_head_ratio": round(heads.most_common(1)[0][1] / len(s), 4) if heads else None,
        "n_polite": sum(1 for x in s if _ends_polite(x["text"])),
        "n_plain": sum(1 for x in s if _ends_plain(x["text"])),
    }


_POLITE = re.compile(r"(니다|세요|어요|아요)\.?$")
_PLAIN = re.compile(r"(다|진다|한다|된다|이다)\.?$")


def _body(t):
    return re.sub(r"\s*\[seg#[^\]]*\]\s*", "", t).strip()


def _ends_polite(t):
    return bool(_POLITE.search(_body(t)))


def _ends_plain(t):
    b = _body(t)
    return bool(_PLAIN.search(b)) and not _POLITE.search(b)


def cjk_exposure():
    """오염 필터를 통과하는 1~2글자 혼입 캡션 수 — 리포트 조기 종료의 씨앗."""
    rows, tot_seg, tot_hit = {}, 0, 0
    for p in sorted((ROOT / "work").glob("*/segments.json")):
        v = p.parent.name
        d = json.loads(p.read_text(encoding="utf-8"))
        segs = d["segments"] if isinstance(d, dict) else d
        hits = [{"idx": s["idx"], "chars": "".join(CJK.findall(s.get("caption") or ""))}
                for s in segs
                if CJK.search(s.get("caption") or "")
                and not common.is_corrupted_caption(s.get("caption") or "")]
        rows[v] = {"n_segments": len(segs), "n_passing_cjk": len(hits), "hits": hits}
        tot_seg += len(segs)
        tot_hit += len(hits)
    return {"total_segments": tot_seg, "total_passing_cjk": tot_hit,
            "rate": round(tot_hit / tot_seg, 4) if tot_seg else None,
            "by_video": rows}


def main():
    OUT.mkdir(exist_ok=True)
    reports = sorted(CAPDIR.glob("report_*.json"))
    if not reports:
        raise SystemExit(f"리포트가 없습니다 — {CAPDIR}에 report_<video>.json을 받아라")

    per_video = {}
    for rp in reports:
        vid = rp.stem[len("report_"):]
        rep = json.loads(rp.read_text(encoding="utf-8"))
        if "sentences" not in rep:          # report_eval.json 등 M9 산출물은 건너뛴다
            continue
        seg_path = ROOT / "work" / vid / "segments.json"
        n_seg = 0
        if seg_path.exists():
            d = json.loads(seg_path.read_text(encoding="utf-8"))
            n_seg = len(d["segments"] if isinstance(d, dict) else d)
        per_video[vid] = {"model": rep.get("model"),
                          "map_chunk_size": rep.get("map_chunk_size"),
                          "truncation": truncation(rep),
                          "summariness": summariness(rep, n_seg)}

    result = {
        "note": __doc__.strip().splitlines()[0],
        "generated_from": "저장된 서버 산출물 report.json (재생성 아님, GPU 미사용)",
        "n_reports": len(per_video),
        "per_video": per_video,
        "cjk_exposure": cjk_exposure(),
    }
    p = OUT / "m8_report_quality.json"
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"리포트 {len(per_video)}편\n")
    print(f"{'영상':<30}{'구간':>5}{'문장':>5}{'커버':>7}{'인용폭':>7}"
          f"{'자/인용':>8}{'몰아':>5}{'순차':>6}{'절단':>11}")
    for v, r in per_video.items():
        s, t = r["summariness"], r["truncation"]
        print(f"{v[:28]:<30}{s['n_segments']:>5}{s['n_sentences']:>5}"
              f"{s['coverage_of_video']:>7.1%}{s['cite_span_mean']:>7.1f}"
              f"{s['chars_per_cite_mean']:>8.1f}{s['cite_dump_sentences']:>5}"
              f"{(s['monotonic_ratio'] or 0):>6.0%}{t.get('stage', '-'):>11}")
    c = result["cjk_exposure"]
    print(f"\n필터 통과 CJK 혼입 캡션: {c['total_passing_cjk']}/{c['total_segments']} "
          f"({c['rate']:.2%})")
    print(f"\n저장: {p}")


if __name__ == "__main__":
    main()
