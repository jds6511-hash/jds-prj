"""staging 영상을 P2 입력 경로(`data/videos/`)로 승격한다. 승인 ② 1단계.

`p2_staging_verify.py`가 "받은 파일이 적격인지"를, 이 스크립트가 **"검증한 그 바이트가
파이프라인 입력이 되는지"**를 보장한다. 세 값을 대조한다.

```
선정 목록 file_sha256   docs/P2_선정표본_2026-08-20.json
staging manifest        artifacts/p2_sampling_frame/manifest.json
실제 파일 해시          지금 다시 계산한다
```

**staging 원본은 지우지 않는다**(P2 종료까지 보존, 결정 문서 §3-3). 복사다.
**목적지에 다른 파일이 있으면 덮어쓰지 않고 멈춘다** — `M1 --force` 금지와 같은 취지다.
기확보 4편은 legacy_exempt라 해시가 없으므로 **존재만** 확인한다.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import provenance as PV                                           # noqa: E402

SELECTED_REL = "docs/P2_선정표본_2026-08-20.json"
STAGING_REL = "artifacts/p2_sampling_frame"


def promote(selected: list, manifest: dict, staging_root, dest_dir) -> dict:
    stage_by_id = {v["source_id"]: v for v in (manifest.get("videos") or [])}
    staging_videos = Path(staging_root) / "videos"
    dest = Path(dest_dir)
    problems, rows = [], []
    copied = skipped = 0

    for r in selected:
        vid = r["source_id"]
        row = {"video_id": vid, "pre_indexed": bool(r.get("pre_indexed")),
               "status": None, "dest_sha256": None}

        if row["pre_indexed"]:
            # 기확보분은 해시가 없다(legacy_exempt) — 존재만 본다
            hits = [p for p in dest.glob(f"{vid}.*") if p.is_file()]
            row["status"] = "pre_indexed_present" if hits else "pre_indexed_missing"
            if not hits:
                problems.append(f"{vid}: 기확보분이 입력 경로에 없다 — {dest}")
            rows.append(row)
            continue

        want = r.get("file_sha256")
        st = stage_by_id.get(vid)
        if st is None:
            problems.append(f"{vid}: staging manifest에 없다")
            row["status"] = "not_in_manifest"
            rows.append(row)
            continue
        if st.get("file_sha256") != want:
            problems.append(
                f"{vid}: 선정 목록과 manifest의 file_sha256이 다르다 — "
                f"선정 {str(want)[:12]} vs manifest {str(st.get('file_sha256'))[:12]}")
            row["status"] = "hash_disagreement"
            rows.append(row)
            continue

        src = staging_videos / r["local_filename"]
        if not src.is_file():
            problems.append(f"{vid}: staging에 파일이 없다 — {src.name}")
            row["status"] = "staging_missing"
            rows.append(row)
            continue
        got = PV.sha256_file(src)
        if got != want:
            problems.append(
                f"{vid}: staging 해시가 등록값과 다르다 — 실제 {got[:12]} vs "
                f"등록 {str(want)[:12]}. 검증한 바이트와 다른 파일이다")
            row["status"] = "staging_hash_mismatch"
            rows.append(row)
            continue

        target = dest / f"{vid}.mp4"
        if target.exists():
            cur = PV.sha256_file(target)
            if cur == want:
                row["status"] = "already_present"
                row["dest_sha256"] = cur
                skipped += 1
            else:
                problems.append(
                    f"{vid}: 입력 경로에 다른 파일이 이미 있다 — 덮어쓰지 않는다 "
                    f"(기존 {cur[:12]} vs 승격 대상 {want[:12]})")
                row["status"] = "dest_conflict"
                row["dest_sha256"] = cur
            rows.append(row)
            continue

        dest.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".mp4.partial")
        shutil.copyfile(src, tmp)
        tmp.replace(target)
        # **복사 후 다시 계산한다** — 복사 도중 잘렸는지는 이것만 잡는다
        after = PV.sha256_file(target)
        row["dest_sha256"] = after
        if after != want:
            problems.append(
                f"{vid}: 복사 후 해시가 다르다 — {after[:12]} vs {want[:12]}")
            row["status"] = "copy_corrupted"
        else:
            row["status"] = "copied"
            copied += 1
        rows.append(row)

    return {"n_selected": len(selected), "copied": copied, "skipped": skipped,
            "problems": problems, "ok": not problems, "rows": rows,
            "staging_preserved": True,
            "note": "staging 원본은 지우지 않는다 — P2 종료까지 보존한다"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", default=SELECTED_REL)
    ap.add_argument("--staging", default=STAGING_REL)
    ap.add_argument("--dest", default=None, help="기본값은 config paths.data/videos")
    ap.add_argument("--out")
    a = ap.parse_args()

    sel = json.loads((ROOT / a.selected).read_text(encoding="utf-8"))["selected"]
    man = json.loads((ROOT / a.staging / "manifest.json")
                     .read_text(encoding="utf-8"))
    dest = Path(a.dest) if a.dest else ROOT / "data" / "videos"
    r = promote(sel, man, ROOT / a.staging, dest)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"selected: {r['n_selected']}  copied: {r['copied']}  "
          f"already: {r['skipped']}  ok: {r['ok']}")
    for p in r["problems"][:10]:
        print(f"  PROBLEM: {p}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
