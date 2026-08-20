"""P2 선정 35편의 provenance가 **완결됐는지** 검사한다. 승인 ② 선행 게이트.

`src/provenance.py`가 "기록할 수 있다"를 보장하고, 이 validator가 **실제로 기록이
완결됐는지**를 보장한다. schema만 있고 검사가 없으면 한두 편 누락된 채 FULL이
진행된다.

검사 항목.

```
1  선정 35편 전건이 레지스트리에 있거나(신규) 면제 목록에 있다(기확보)
2  신규 편의 `file_sha256`이 staging manifest 값과 일치한다
3  `source_id`가 선정 집합 안에서 유일하다
4  필드 누락이 없다
5  (선택) 인덱싱된 영상의 segments.json·meta.json이 같은 값을 들고 있다
```

**전부 fail-closed다.** 하나라도 어긋나면 exit 1이고, 그 상태로 M1을 돌리지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import provenance as P                                           # noqa: E402


def _check_indexed(wdir: Path, entry: dict, problems: list, vid: str) -> dict:
    """인덱싱된 영상이 같은 값을 들고 있는지. 중간 단계가 덮어썼는지 잡는다."""
    out = {}
    for name, key in (("segments.json", "segments"), ("meta.json", "meta")):
        p = wdir / name
        if not p.exists():
            out[key] = "absent"
            continue
        prov = (json.loads(p.read_text(encoding="utf-8")) or {}).get(
            "provenance")
        if prov is None:
            out[key] = "no_provenance"
            problems.append(f"{vid}: {name}에 provenance가 없다")
            continue
        same = all(prov.get(f) == entry.get(f) for f in P.PROV_FIELDS)
        out[key] = "match" if same else "MISMATCH"
        if not same:
            problems.append(f"{vid}: {name} provenance가 레지스트리와 다르다")
    return out


def validate(selected: list, reg: dict, staging: dict = None,
             work_dir=None) -> dict:
    videos = reg.get("videos") or {}
    exempt = reg.get("legacy_exempt") or {}
    stage_hash = {v["source_id"]: v.get("file_sha256")
                  for v in (staging or {}).get("videos", [])}
    problems, rows = [], []
    seen_sid = {}
    for r in selected:
        vid = r["source_id"]
        pre = bool(r.get("pre_indexed"))
        row = {"video_id": vid, "pre_indexed": pre, "status": None}
        entry = videos.get(vid)
        if entry is None:
            row["status"] = "legacy_exempt" if vid in exempt else "MISSING"
            if row["status"] == "MISSING":
                problems.append(f"{vid}: 레지스트리·면제 목록 어디에도 없다")
            elif not pre:
                problems.append(
                    f"{vid}: 신규 영상인데 면제로 처리돼 있다 — 신규는 기록 필수")
            rows.append(row)
            continue
        row["status"] = "recorded"
        miss = [f for f in P.PROV_FIELDS if not entry.get(f)]
        if miss:
            problems.append(f"{vid}: 필드 누락 {miss}")
        sid = entry.get("source_id")
        if sid in seen_sid:
            problems.append(f"source_id 중복 {sid}: {seen_sid[sid]} vs {vid}")
        seen_sid[sid] = vid
        want = stage_hash.get(vid)
        if want and entry.get("file_sha256") != want:
            problems.append(
                f"{vid}: file_sha256이 staging과 다르다 — 등록 "
                f"{str(entry.get('file_sha256'))[:12]} vs staging {want[:12]}")
        row["sha256_matches_staging"] = (None if not want
                                         else entry.get("file_sha256") == want)
        if work_dir:
            row.update(_check_indexed(Path(work_dir) / vid, entry, problems,
                                      vid))
        rows.append(row)

    dup = P.duplicate_source_ids(reg)
    if dup:
        problems.append(f"레지스트리 전역 source_id 중복: {dup}")
    return {
        "n_selected": len(selected),
        "recorded": sum(1 for r in rows if r["status"] == "recorded"),
        "legacy_exempt": sum(1 for r in rows if r["status"] == "legacy_exempt"),
        "missing": sum(1 for r in rows if r["status"] == "MISSING"),
        "sha256_checked": sum(1 for r in rows
                              if r.get("sha256_matches_staging") is True),
        "problems": problems, "ok": not problems, "rows": rows,
        "id_level_dedup": reg.get("id_level_dedup"),
        "note": ("provenance는 기록 전용이다 — 지표·eligibility 계산에 쓰지 "
                 "않는다"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", default="docs/P2_선정표본_2026-08-20.json")
    ap.add_argument("--staging",
                    default="artifacts/p2_sampling_frame/manifest.json")
    ap.add_argument("--work", help="인덱싱 후 segments/meta 대조")
    ap.add_argument("--out")
    a = ap.parse_args()
    sel = json.loads(Path(ROOT / a.selected).read_text(encoding="utf-8"))
    reg = P.load_registry(P.registry_path(ROOT))
    sp = Path(ROOT / a.staging)
    staging = (json.loads(sp.read_text(encoding="utf-8")) if sp.exists()
               else None)
    r = validate(sel["selected"], reg, staging, a.work)
    if a.out:
        Path(ROOT / a.out).write_text(
            json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"selected: {r['n_selected']}  recorded: {r['recorded']}  "
          f"legacy_exempt: {r['legacy_exempt']}  missing: {r['missing']}")
    print(f"sha256 matched vs staging: {r['sha256_checked']}")
    print(f"ok: {r['ok']}")
    for p in r["problems"][:10]:
        print(f"  PROBLEM: {p}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
