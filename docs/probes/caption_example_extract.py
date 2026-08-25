"""3B/P0 vs 4B/P0 캡션 예시 추출 — 회의·보고서 **서술용**.

이 스크립트는 모델 선택·튜닝 근거를 만들지 않는다. 저장된 2×2 산출물만 읽고,
사람이 읽을 예시 3건과 전체 분포를 뽑는다. `m5_search`·`m6_evaluate`를 import하지
않는다(저장된 per_query만 읽는다).

**예시 선택 규칙 — 출력을 보기 전에 고정한다.**
  A. 위치 기준   : video_id 사전순 첫 영상 · 그 영상의 파일 순서 첫 질의
  B. 4B 우세 극단: rank_3b - rank_4b 최대. 동률이면 query_id 사전순
  C. 3B 우세 극단: rank_4b - rank_3b 최대. 동률이면 query_id 사전순
내용을 보고 고르지 않는다. B·C는 대표성 없는 극단 사례로만 인용한다.

콘솔이 cp949라 한글이 깨지므로 결과는 UTF-8 파일로만 낸다.
"""
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "docs/probes/_scratch/aihub_2x2_captions/full_2026-08-17"
EVAL = ROOT / "docs/probes/_scratch/aihub_caption_2x2_full_2026-08-17.json"
QUERIES = ROOT / "data_aihub/queries/queries_aihub.jsonl"
OUT = ROOT / "docs/probes/_scratch/caption_examples_2x2.txt"


def main() -> None:
    q = [json.loads(line) for line in
         QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    cap = {"3B": json.loads((CAP / "qwen25_3b__P0.json").read_text(encoding="utf-8")),
           "4B": json.loads((CAP / "qwen3vl_4b__P0.json").read_text(encoding="utf-8"))}
    ev = json.loads(EVAL.read_text(encoding="utf-8"))
    pq = {"3B": {r["query_id"]: r for r in ev["per_query"]["qwen25_3b/P0"]},
          "4B": {r["query_id"]: r for r in ev["per_query"]["qwen3vl_4b/P0"]}}
    byid = {r["query_id"]: r for r in q}

    out = io.StringIO()

    def show(tag: str, qid: str) -> None:
        r = byid[qid]
        v = r["video_id"]
        a, b = pq["3B"][qid], pq["4B"][qid]
        out.write("\n" + "=" * 70 + "\n[%s] %s\n" % (tag, qid))
        out.write("영상 %s (%s) · 후보 구간 %d개\n" % (v, r["type"], a["n_seg"]))
        out.write("질의        : %s\n" % r["text"])
        out.write("정답 구간    : %s  (%.1f~%.1fs)\n"
                  % (r["gt_seg_idx"], r["gt_start"], r["gt_end"]))
        out.write("3B 순위/RR  : %d / %.3f\n" % (a["rank_cap"], a["rr_cap"]))
        out.write("4B 순위/RR  : %d / %.3f\n" % (b["rank_cap"], b["rr_cap"]))
        for g in r["gt_seg_idx"]:
            out.write("\n-- 정답 구간 %d 캡션 --\n" % g)
            for arm in ("3B", "4B"):
                out.write("%s(%3d자): %s\n" % (arm, len(cap[arm][v][g]), cap[arm][v][g]))

    v0 = sorted(cap["3B"])[0]
    show("A 위치기준 — 사전순 첫 영상의 첫 질의",
         next(r["query_id"] for r in q if r["video_id"] == v0))

    diffs = sorted(((pq["3B"][k]["rank_cap"] - pq["4B"][k]["rank_cap"], k)
                    for k in pq["3B"]), key=lambda t: t[1])
    b_gap, b_qid = max(diffs, key=lambda t: t[0])
    c_gap, c_qid = max(diffs, key=lambda t: -t[0])
    show("B 4B 우세 극단 (순위차 %+d)" % b_gap, b_qid)
    show("C 3B 우세 극단 (순위차 %+d)" % c_gap, c_qid)

    n = len(diffs)
    win4 = sum(1 for d, _ in diffs if d > 0)
    win3 = sum(1 for d, _ in diffs if d < 0)
    out.write("\n" + "=" * 70 + "\n[분포] 총 %d질의 · 4B 순위 우세 %d (%.1f%%) · "
              "3B 우세 %d (%.1f%%) · 동일 %d (%.1f%%)\n"
              % (n, win4, 100 * win4 / n, win3, 100 * win3 / n,
                 n - win4 - win3, 100 * (n - win4 - win3) / n))
    lens = {arm: [len(c) for v in cap[arm] for c in cap[arm][v]] for arm in cap}
    out.write("[길이] 평균 글자수  3B %.1f · 4B %.1f  (구간 %d개)\n"
              % (sum(lens["3B"]) / len(lens["3B"]),
                 sum(lens["4B"]) / len(lens["4B"]), len(lens["3B"])))

    OUT.write_text(out.getvalue(), encoding="utf-8")
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
