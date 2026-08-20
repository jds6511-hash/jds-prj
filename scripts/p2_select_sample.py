"""P2 표본 선정 — `c = 0.80` · `target_k = 35` · seed 20260820.

결정 문서: `docs/P2_승인1_규모확정_2026-08-20.md` ·
`docs/P2_선정규칙_동률처리_2026-08-20.md`.
사전등록: `부호역전_확증_보충3_P2표집범위` §5 · `보충4_P2표집틀검증` §2.

절차는 넷이다.

    1  `sampling_frame_usable`인 영상만 pool에 넣는다
    2  비-EBS는 **전수**다. 무작위로 깎지 않는다
    3  EBS 쿼터를 계열별 usable 편수 비례로 Hamilton 배분한다.
       remainder 동률은 **`program_id` 오름차순** — 결과와 무관한 정적 규칙
    4  계열 안에서 seed 20260820 단순무작위로 뽑는다

**성능을 보지 않는다.** 캡션·검색 점수·모델명이 이 모듈에 들어오지 않는다.
제목도 보지 않는다 — 제목으로 고르면 그것이 표본 선택 축이 된다.
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED = 20260820
C_CAP = 0.80
TARGET_K = 35
# **결과와 무관한 정적 규칙.** 실측 배분에서는 구속하지 않았지만(잔여 4석에
# 후보 4개) 규칙은 추출보다 먼저 선언한다
TIE_BREAK = "program_id_ascending"
# 기확보 4편. 이미 인덱싱돼 있어 캡션 2 arm 생성만 남는다
FREE_VIDEOS = {"baekmansonghee_jirisan": 183, "jissi_farm": 211,
               "softyeon_ceramics": 192, "pland_costco_hosting": 395}


def ebs_cap(n_non_ebs: int) -> int:
    """`E/(E+N) <= c  <=>  E <= c/(1-c) * N`."""
    return int(C_CAP / (1 - C_CAP) * n_non_ebs + 1e-9)


def hamilton(supply: dict, total: int) -> dict:
    """최대잉여법. **동률은 `program_id` 오름차순으로만 푼다.**

    가중치는 계열별 usable 편수다. 공급을 넘겨 배분하지 않는다.
    """
    pool = sum(supply.values())
    if not pool or total <= 0:
        return {k: 0 for k in supply}
    exact = {k: v * total / pool for k, v in supply.items()}
    q = {k: min(int(v), supply[k]) for k, v in exact.items()}
    left = total - sum(q.values())
    order = sorted(supply, key=lambda k: (-(exact[k] - int(exact[k])), k))
    i = 0
    while left > 0 and i < len(order) * 2:
        k = order[i % len(order)]
        if q[k] < supply[k]:
            q[k] += 1
            left -= 1
        i += 1
    return q


def select(rows: list, free_videos: dict = None, target_k: int = TARGET_K,
           seed: int = SEED) -> dict:
    """`rows`는 staging manifest의 `videos`. usable만 쓴다."""
    free_videos = FREE_VIDEOS if free_videos is None else free_videos
    usable = [r for r in rows if r.get("sampling_frame_usable")]
    ebs = [r for r in usable if r["publisher"] == "ebs"]
    non_ebs = [r for r in usable if r["publisher"] != "ebs"]

    free_rows = [{"source_id": v, "source_url": None, "file_sha256": None,
                  "n_segments": n, "publisher": "free",
                  "program": "free_creator", "pre_indexed": True}
                 for v, n in sorted(free_videos.items())]
    n_non = len(non_ebs) + len(free_rows)
    n_ebs = min(ebs_cap(n_non), len(ebs), max(target_k - n_non, 0))

    supply = {}
    for r in ebs:
        supply[r["program"]] = supply.get(r["program"], 0) + 1
    quota = hamilton(supply, n_ebs)

    rng = random.Random(seed)
    picked, reserve, binding = [], {}, {}
    for fam in sorted(supply):
        cand = sorted((r for r in ebs if r["program"] == fam),
                      key=lambda r: r["source_id"])
        rng.shuffle(cand)
        k = quota[fam]
        picked.extend(cand[:k])
        reserve[fam] = [r["source_id"] for r in cand[k:]]
        if k < len(cand):                 # 전수가 아니면 무작위가 구속한다
            binding[fam] = f"choose {k} of {len(cand)}"

    keep = ("source_id", "source_url", "file_sha256", "n_segments",
            "publisher", "program", "selected_audio_language", "speech_status",
            "local_filename", "duration_sec")
    sel = ([{k: r.get(k) for k in keep if k in r} for r in
            sorted(picked, key=lambda r: (r["program"], r["source_id"]))]
           + [{k: r.get(k) for k in list(keep) + ["pre_indexed"] if k in r}
              for r in sorted(non_ebs, key=lambda r: (r["publisher"],
                                                      r["source_id"]))]
           + free_rows)
    return {
        "seed": seed, "tie_break": TIE_BREAK, "c_cap": C_CAP,
        "target_k": target_k, "achieved_k": len(sel),
        "usable_pool": {"ebs": len(ebs), "non_ebs": n_non},
        "ebs_selected": n_ebs, "ebs_cap_from_c": ebs_cap(n_non),
        "non_ebs_census": True,
        "program_supply": supply, "program_quota": quota,
        "random_choice_binding": binding,
        "binding_note": ("쿼터가 공급과 같은 계열은 전수이므로 무작위가 결과를 "
                         "구속하지 않는다. 구속하는 계열만 위에 적힌다"),
        "reserve_order": reserve,
        "reserve_note": ("교체용이 아니다. 선정 뒤 영상을 바꾸지 않는다 — "
                         "감사를 위해 추출 순서를 남긴다"),
        "selected": sel,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest",
                    default="artifacts/p2_sampling_frame/manifest.json")
    ap.add_argument("--out",
                    default="artifacts/p2_sampling_frame/selected_sample.json")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    man = json.loads(Path(ROOT / a.manifest).read_text(encoding="utf-8"))
    r = select(man["videos"], seed=a.seed)
    r["source_manifest"] = a.manifest
    r["reproduction_gate"] = man["reproduction_gate"]["all_match"]
    r["speech_evidence"] = man["speech_evidence"]
    Path(ROOT / a.out).write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seed: {r['seed']}  tie_break: {r['tie_break']}")
    print(f"usable: ebs {r['usable_pool']['ebs']} / non_ebs "
          f"{r['usable_pool']['non_ebs']}")
    print(f"ebs cap from c: {r['ebs_cap_from_c']}  selected: {r['ebs_selected']}")
    print(f"program quota: {r['program_quota']}")
    print(f"binding random: {r['random_choice_binding']}")
    print(f"achieved_k: {r['achieved_k']} / target {r['target_k']}")
    print(f"saved: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
