"""P2 표집틀 검증 — **staging에서 입력을 검증하고 고르는 단계**(승인 ①).

사전등록: `부호역전_확증_보충4_P2표집틀검증_2026-08-20.md` §1.
결정 문서: `docs/P2_승인1_규모확정_2026-08-20.md`.

경계 한 줄.

    승인 ①   staging에서 입력을 검증하고 고른다
    승인 ②   검증된 **그 바이트**를 production 입력으로 승격시킨다

그래서 이 모듈은 `data/videos/`·`work/`에 쓰지 않는다. 다운로드는 staging에만
하고, 승격은 별도 단계다. **"다운로드했으니 실행도 승인된 것"이 아니다.**

**production 함수를 그대로 호출한다.** production duration은 ffprobe 값이 아니라
`m1_preprocess.get_video_info`의 cv2 프레임수/fps다(`m1_preprocess.py:54`가
`ceil(duration / seg_len_sec)`를 assert한다). 별도 파서를 쓰면 그 차이가 판정에
들어온다.

**재현 게이트가 선행이다.** 기확보 4편에 같은 함수를 돌려 `work/*/segments.json`의
`n_segments`와 4/4 정확히 일치해야 신규 파일 판정으로 넘어간다. 불일치면 중단이고
허용 오차를 만들지 않는다.

모델 산출물을 생성·열람하지 않는다 — 길이만 잰다.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import m1_preprocess as M                                        # noqa: E402

SEG_LEN = 5
TARGET_SEGMENTS = (150, 400)
TARGET_K = 35
C_CAP = 0.80
STAGING = ROOT / "artifacts" / "p2_sampling_frame"
OUT_OF_SCOPE = ("lecture_dialog",)
NON_EBS = ("kbs", "other", "free")
# **완성 파일만 받는다.** `<id>.f137.mp4`(병합 전 video-only)나 `<id>.mp4.part`
# (중단된 다운로드)를 glob으로 집으면 음성 없는/잘린 입력이 조용히
# verified_eligible이 된다 — cv2는 그런 파일도 열고 duration을 준다
FINAL_EXT = (".mp4", ".mkv", ".webm")
# 보충4 §1-2. 기확보 4편의 production 실측값 — 게이트 기준
GATE_REF = {"baekmansonghee_jirisan": 183, "jissi_farm": 211,
            "softyeon_ceramics": 192, "pland_costco_hosting": 395}
# **avc1 우선.** production duration을 cv2가 읽고 M2가 프레임을 뽑는다 —
# vp9/av1 컨테이너는 그 경로에서 덜 안전하다. 기존 코퍼스도 avc1 720p·1080p다
FORMAT = ("bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/"
          "bv*[height<=1080]+ba/b[height<=1080]/b")
BOUNDARY_NOTE = ("승인 ① 작업이다 — sampling-frame verification. production 경로로의 "
                 "승격(promotion)과 모델 실행은 승인 ②다. 다운로드가 실행 승인이 "
                 "아니다")


class VerifyError(RuntimeError):
    pass


def probe(path) -> tuple:
    """**production 함수 그대로.** 파일을 한 번만 열고 둘을 같은 값에서 낸다."""
    duration, _fps = M.get_video_info(path)
    return duration, len(M.make_segments(duration, SEG_LEN))


def production_n_segments(path) -> int:
    return probe(path)[1]


def classify_segments(n: int) -> str:
    lo, hi = TARGET_SEGMENTS
    return "verified_eligible" if lo <= n <= hi else "segment_ineligible"


def publisher_of(family: str) -> str:
    return family.split("_")[0]


def in_scope(rows: list) -> list:
    """1차 적격 ∧ 주 표집틀. `lecture_dialog`는 기전이 달라 제외(보충3 §3)."""
    return [r for r in rows
            if str(r.get("eligible")) == "True"
            and r["family"] not in OUT_OF_SCOPE]


def reproduction_gate(video_dir, work_dir, ref: dict = None) -> dict:
    """기확보 4편을 먼저 재현한다. **불일치면 신규 판정으로 넘어가지 않는다.**"""
    ref = GATE_REF if ref is None else ref
    by = {}
    for vid, expected in sorted(ref.items()):
        got = production_n_segments(Path(video_dir) / f"{vid}.mp4")
        by[vid] = {"expected": expected, "got": got, "match": got == expected}
    return {"reference": dict(ref), "by_video": by,
            "all_match": all(v["match"] for v in by.values()),
            "note": "허용 오차 없음. 불일치면 검증기가 production과 다르다"}


def media_info(path) -> dict:
    """**provenance 전용.** 판정에 쓰지 않는다 — eligibility는 n_segments만 본다."""
    import cv2
    c = cv2.VideoCapture(str(path))
    try:
        fourcc = int(c.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
        return {"width": int(c.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": round(c.get(cv2.CAP_PROP_FPS), 3),
                "codec": codec.replace(chr(0), "")}
    finally:
        c.release()


def tool_version() -> str:
    p = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
    return (p.stdout or "").strip()


def ffmpeg_version() -> str:
    """merge 단계가 ffmpeg를 쓴다 — 컨테이너가 그 손을 거친다."""
    try:
        p = subprocess.run(["ffmpeg", "-version"], capture_output=True,
                           text=True, timeout=30)
        return (p.stdout or "").splitlines()[0][:120]
    except Exception as e:
        return f"unavailable: {type(e).__name__}"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def final_file(dest_dir, video_id):
    """**완성 파일만 인정한다.** 중간 산출물·부분 파일을 입력으로 쓰지 않는다."""
    for ext in FINAL_EXT:
        f = Path(dest_dir) / f"{video_id}{ext}"
        if f.exists() and f.stat().st_size > 0:
            return f
    return None


def has_audio(path) -> bool:
    """**provenance 전용.** 병합 실패로 video-only가 남았는지 드러낸다.

    eligibility는 `n_segments`만 본다(보충4 §1). 이 값은 판정에 쓰지 않고,
    승인 ② 전에 STT가 깨질 입력을 미리 드러내기 위해 기록한다.
    """
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=codec_type", "-of",
                            "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60)
        return "audio" in (r.stdout or "")
    except Exception:
        return False


def download(video_id: str, dest_dir) -> tuple:
    """staging에만 내려받는다. **이미 있으면 재다운로드하지 않는다.**

    세 번째 반환값은 취득 경로다 — `downloaded`면 이번 실행 조건
    (`yt_dlp_version` · `download_format`)이 그 파일에 적용되고, `pre_existing`
    이면 이번 실행이 그 조건을 관측하지 않았다는 뜻이다.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    done = final_file(dest_dir, video_id)
    if done is not None:
        return done, None, "pre_existing"
    cmd = ["yt-dlp", "--no-warnings", "-f", FORMAT,
           "--merge-output-format", "mp4",
           "-o", str(dest_dir / f"{video_id}.%(ext)s"),
           f"https://www.youtube.com/watch?v={video_id}"]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    got = final_file(dest_dir, video_id)
    if p.returncode != 0 or got is None:
        err = (p.stderr or "").strip().splitlines()
        leftovers = sorted(x.name for x in dest_dir.glob(f"{video_id}.*"))
        msg = (err[-1][:200] if err else "no complete output")
        if leftovers and p.returncode == 0:
            msg = f"incomplete artifacts only: {leftovers[:3]}"
        return None, msg, "download_failed"
    return got, None, "downloaded"


def attribute(vid: str, how: str, origin: dict = None) -> dict:
    """**현재 파일이 어떻게 취득됐는가**를 기록한다.

    "이번 실행에서 다운로드했는가"와 구별한다. 재검증 실행에서는 모든 파일이
    `pre_existing`으로 보이지만, 그 파일을 만든 조건은 이미 알고 있을 수 있다.
    **아는 것을 잃지 않고, 모르는 것을 복원하지도 않는다.**
    """
    if how == "downloaded":
        return {"source": "downloaded_in_this_run",
                "acquired_by": "this_run",
                "yt_dlp_version": tool_version(),
                "format_selector": FORMAT, "note": ""}
    known = ((origin or {}).get("acquired_by_map") or {}).get(vid)
    if known:
        return {"source": "pre_existing",
                "acquired_by": known.get("acquired_by"),
                "yt_dlp_version": known.get("yt_dlp_version"),
                "format_selector": known.get("format_selector"),
                "note": "이번 검증 실행에서 다운로드하지 않았다. 조건은 동결 "
                        "origin 기록에서 가져왔다"}
    return {"source": "pre_existing_unknown_acquisition",
            "acquired_by": None, "yt_dlp_version": None,
            "format_selector": None,
            "note": "취득 조건을 관측하지 못했고 origin 기록에도 없다 — "
                    "downloaded로 복원하지 않는다"}


def hash_check(vid: str, digest: str, origin: dict = None) -> dict:
    prior = ((origin or {}).get("prior_sha256") or {}).get(vid)
    if prior is None:
        return {"prior_sha256": None, "match": None,
                "note": "이 실행이 최초 기록이다 — 두 실행 일치라고 쓰지 않는다"}
    return {"prior_sha256": prior, "match": prior == digest,
            "note": "동결된 이전 실행 해시와 대조"}


def verify_one(row: dict, staging, origin: dict = None) -> dict:
    """한 편. **다운로드 실패와 세그먼트 탈락을 다른 상태로 남긴다.**"""
    vid = row["video_id"]
    out = {"source_id": vid,
           "source_url": f"https://www.youtube.com/watch?v={vid}",
           "publisher": publisher_of(row["family"]),
           "program": row["family"], "domain": row.get("domain", ""),
           "download_status": "ok", "local_filename": None,
           "file_sha256": None, "duration_sec": None, "n_segments": None,
           "verification_status": "verification_unavailable", "error": ""}
    path, err, how = download(vid, Path(staging) / "videos")
    out["acquisition"] = attribute(vid, how, origin)
    if err or path is None:
        out["download_status"] = "failed"
        out["error"] = err or "unknown"
        return out                      # segment_ineligible이 아니다
    out["local_filename"] = path.name
    out["file_sha256"] = sha256_file(path)
    out["sha256_check"] = hash_check(vid, out["file_sha256"], origin)
    try:
        duration, n = probe(path)
        out["duration_sec"] = round(duration, 2)
    except Exception as e:              # 파일이 열리지 않으면 판정 불가다
        out["download_status"] = "ok"
        out["error"] = f"probe failed: {type(e).__name__}"
        return out
    out["n_segments"] = n
    out["verification_status"] = classify_segments(n)
    out["media"] = media_info(path)          # provenance 전용
    out["media"]["has_audio"] = has_audio(path)
    return out


def achieved_k(n_non_ebs: int, n_ebs: int, target: int = TARGET_K) -> int:
    """`c = C_CAP`에서 `E/(E+N) <= c  <=>  E <= c/(1-c) * N`.

    **비-EBS 1편 탈락은 EBS 1편 제거로 메울 수 없다** — `c=0.80`이면 4편이다.
    """
    cap = int(C_CAP / (1 - C_CAP) * n_non_ebs + 1e-9)
    return min(target, n_non_ebs + min(cap, n_ebs))


def counts(manifest_rows: list, free_verified: int = 0) -> dict:
    ok = [r for r in manifest_rows
          if r["verification_status"] == "verified_eligible"]
    ebs = sum(1 for r in ok if r["publisher"] == "ebs")
    non_ebs = sum(1 for r in ok if r["publisher"] in NON_EBS) + free_verified
    return {
        "n_rows": len(manifest_rows),
        "verified_eligible": len(ok),
        "segment_ineligible": sum(
            1 for r in manifest_rows
            if r["verification_status"] == "segment_ineligible"),
        "verification_unavailable": sum(
            1 for r in manifest_rows
            if r["verification_status"] == "verification_unavailable"),
        "ebs_verified": ebs,
        "non_ebs_verified": non_ebs,
        "free_carried": free_verified,
    }


def run(rows: list, staging, video_dir, work_dir, ref: dict = None,
        limit: int = None, free_verified: int = 0, origin: dict = None) -> dict:
    staging = Path(staging)
    staging.mkdir(parents=True, exist_ok=True)
    gate = reproduction_gate(video_dir, work_dir, ref)
    if not gate["all_match"]:
        raise VerifyError(
            f"재현 게이트 FAIL: {gate['by_video']} — 검증기가 production과 다르다. "
            "신규 파일 판정으로 넘어가지 않는다")
    todo = in_scope(rows)[:limit] if limit else in_scope(rows)
    out_rows = [verify_one(r, staging, origin) for r in todo]
    c = counts(out_rows, free_verified)
    man = {
        "stage": "p2_sampling_frame_verification",
        "approval_stage": "approval_1_sampling_frame_verification",
        "boundary_note": BOUNDARY_NOTE,
        "prereg": ("docs/preregistration/부호역전_확증_보충4_P2표집틀검증_"
                   "2026-08-20.md"),
        "decision_doc": "docs/P2_승인1_규모확정_2026-08-20.md",
        "reproduction_gate": gate,
        "bounds": {"seg_len_sec": SEG_LEN,
                   "target_segments": list(TARGET_SEGMENTS)},
        "c_cap": C_CAP, "target_k": TARGET_K,
        "download_format": FORMAT,
        "yt_dlp_version": tool_version(),
        "ffmpeg_version": ffmpeg_version(),
        "counts": c,
        "acquisition_origin_supplied": bool(origin),
        "sha256_mismatches": [r["source_id"] for r in out_rows
                              if (r.get("sha256_check") or {}).get("match")
                              is False],
        "unknown_acquisition": [
            r["source_id"] for r in out_rows
            if r["acquisition"]["source"] == "pre_existing_unknown_acquisition"],
        "no_audio": [r["source_id"] for r in out_rows
                     if r.get("media", {}).get("has_audio") is False],
        "achieved_k": achieved_k(c["non_ebs_verified"], c["ebs_verified"]),
        "achieved_k_formula": "min(target_k, N + min(floor(c/(1-c)*N), E))",
        "videos": out_rows,
    }
    (staging / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="docs/probes/_scratch/p2_video_pool.csv")
    ap.add_argument("--staging", default=str(STAGING))
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--limit", type=int, help="canary: first N only")
    ap.add_argument("--gate-only", action="store_true")
    ap.add_argument("--origin", help="frozen acquisition origin JSON")
    ap.add_argument("--free-verified", type=int, default=0,
                    help="already-indexed FREE videos counted as non-EBS")
    a = ap.parse_args()
    import common
    cfg = common.load_config(ROOT / a.config)
    vdir = Path(cfg["paths"]["data"]) / "videos"
    wdir = Path(cfg["paths"]["work"])
    if a.gate_only:
        g = reproduction_gate(vdir, wdir)
        print(json.dumps(g, ensure_ascii=False, indent=2))
        return 0 if g["all_match"] else 1
    rows = list(csv.DictReader(
        Path(ROOT / a.pool).read_text(encoding="utf-8-sig").splitlines()))
    origin = (json.loads(Path(a.origin).read_text(encoding="utf-8"))
              if a.origin else None)
    man = run(rows, a.staging, vdir, wdir, limit=a.limit,
              free_verified=a.free_verified, origin=origin)
    c = man["counts"]
    print(f"gate: {man['reproduction_gate']['all_match']}")
    print(f"rows: {c['n_rows']}  verified: {c['verified_eligible']}")
    print(f"segment_ineligible: {c['segment_ineligible']}  "
          f"unavailable: {c['verification_unavailable']}")
    print(f"ebs: {c['ebs_verified']}  non_ebs: {c['non_ebs_verified']}")
    print(f"target_k: {man['target_k']}  achieved_k: {man['achieved_k']}")
    print(f"sha256 mismatches: {man['sha256_mismatches']}")
    print(f"unknown acquisition: {man['unknown_acquisition']}")
    print(f"no audio: {man['no_audio']}")
    print(f"manifest: {Path(a.staging) / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
