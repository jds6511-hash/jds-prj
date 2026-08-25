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

캡션이 실제로 어느 화면을 보고 쓰였는지 확인할 수 있게 대표 프레임도 함께 모은다.
**출력 위치는 `_scratch/`이며 .gitignore로 미추적이다** — AI Hub 원본 프레임을
공개 저장소에 올리지 않기 위해서다(재배포 권한 미확인). 필요하면 각자 실행한다.
"""
import io
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "docs/probes/_scratch/aihub_2x2_captions/full_2026-08-17"
EVAL = ROOT / "docs/probes/_scratch/aihub_caption_2x2_full_2026-08-17.json"
QUERIES = ROOT / "data_aihub/queries/queries_aihub.jsonl"
WORK = ROOT / "work_aihub"
OUT = ROOT / "docs/probes/_scratch/caption_examples_2x2.txt"
FRAME_DIR = ROOT / "docs/probes/_scratch/caption_examples_frames"


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
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    md = io.StringIO()
    md.write("# 캡션 예시 — 정답 구간 대표 프레임\n\n"
             "`docs/probes/caption_example_extract.py`가 생성한다. **미추적 폴더**다 —\n"
             "AI Hub 원본 프레임은 재배포 권한이 확인되지 않아 저장소에 올리지 않는다.\n\n"
             "프레임은 캡션 생성에 실제로 쓰인 `segments.json:rep_frame`을 그대로 복사한 것이다.\n")

    def show(tag: str, qid: str, slug: str) -> None:
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
        md.write("\n---\n\n## %s\n\n```\n질의      %s\n영상      %s (%s) · 후보 구간 %d개\n"
                 "정답 구간  %s  (%.1f~%.1fs)\n3B 순위   %2d위 / RR %.3f\n4B 순위   %2d위 / RR %.3f\n```\n"
                 % (tag, r["text"], v, r["type"], a["n_seg"], r["gt_seg_idx"],
                    r["gt_start"], r["gt_end"], a["rank_cap"], a["rr_cap"],
                    b["rank_cap"], b["rr_cap"]))
        segs = json.loads((WORK / v / "segments.json").read_text(encoding="utf-8"))["segments"]
        for g in r["gt_seg_idx"]:
            out.write("\n-- 정답 구간 %d 캡션 --\n" % g)
            for arm in ("3B", "4B"):
                out.write("%s(%3d자): %s\n" % (arm, len(cap[arm][v][g]), cap[arm][v][g]))
            src = WORK / v / segs[g]["rep_frame"]
            dst = FRAME_DIR / ("%s__%s_seg%02d.jpg" % (slug, v, g))
            shutil.copyfile(src, dst)
            md.write("\n![%s](%s)\n\n| 모델 | 캡션 |\n|---|---|\n" % (dst.name, dst.name))
            for arm in ("3B", "4B"):
                md.write("| **%s** (%d자) | %s |\n"
                         % (arm, len(cap[arm][v][g]), cap[arm][v][g].replace("|", "\\|")))

    v0 = sorted(cap["3B"])[0]
    show("A 위치기준 — 사전순 첫 영상의 첫 질의",
         next(r["query_id"] for r in q if r["video_id"] == v0), "A_위치기준")

    diffs = sorted(((pq["3B"][k]["rank_cap"] - pq["4B"][k]["rank_cap"], k)
                    for k in pq["3B"]), key=lambda t: t[1])
    b_gap, b_qid = max(diffs, key=lambda t: t[0])
    c_gap, c_qid = max(diffs, key=lambda t: -t[0])
    show("B 4B 우세 극단 (순위차 %+d)" % b_gap, b_qid, "B_4B우세")
    show("C 3B 우세 극단 (순위차 %+d)" % c_gap, c_qid, "C_3B우세")

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

    md.write("\n---\n\n```\n총 %d질의 · 4B 순위 우세 %d (%.1f%%) · 3B 우세 %d (%.1f%%) · "
             "동일 %d (%.1f%%)\n평균 글자수  3B %.1f · 4B %.1f  (구간 %d개)\n```\n"
             % (n, win4, 100 * win4 / n, win3, 100 * win3 / n,
                n - win4 - win3, 100 * (n - win4 - win3) / n,
                sum(lens["3B"]) / len(lens["3B"]),
                sum(lens["4B"]) / len(lens["4B"]), len(lens["3B"])))
    (FRAME_DIR / "README.md").write_text(md.getvalue(), encoding="utf-8")
    OUT.write_text(out.getvalue(), encoding="utf-8")
    print("wrote %s" % OUT)
    print("wrote %s (frames + README.md)" % FRAME_DIR)


if __name__ == "__main__":
    main()
