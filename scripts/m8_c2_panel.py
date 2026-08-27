"""M8 C2 판정 패널(N=8) — 적격 필터 · 후보 풀 동결 · deterministic 선정.

동결 규칙: `docs/finalization/M8_C2_SOURCING_RULE_2026-08-27.md`
          sha256 cd6dd0ad2e2ffd452d36fdcfdae26d2dec6b151bd12b1f818cae95b1698aa803

**사람이 2편을 고르지 않는다.** 적격 후보 풀을 먼저 동결하고, 그 뒤에 seed 해시로
순서를 정한다. 순서를 본 뒤 풀을 고치면 절차가 성립하지 않으므로 `--verify`가
`candidate_pool_sha256`을 다시 계산해 대조한다.

```
python scripts/m8_c2_panel.py --build  --meta <metadata.jsonl> --out <manifest.json>
python scripts/m8_c2_panel.py --verify --out <manifest.json>
```

`--build`는 네트워크를 쓰지 않는다 — metadata는 미리 뽑아 둔 파일에서 읽는다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import eligibility                                              # noqa: E402

NAMESPACE = "M8-C2-N8-v1"
SEED_COMMIT = "f035073"
FIXED_N = 8
C2_THRESHOLD = 0.70

# 후보 풀 해시를 계산할 때 쓰는 필드. **선정 이후에 붙는 값(selection_key)은 넣지 않는다** —
# 넣으면 "풀을 먼저 동결했다"는 주장이 순환한다.
POOL_FIELDS = ("id", "query", "duration", "channel", "channel_id", "language",
               "upload_date")

# 기존 적격 6편. 이 구성은 신규 선정 결과와 무관하게 유지한다(지시서 §3).
EXISTING_PANEL = ("baekmansonghee_jirisan", "softyeon_ceramics", "jissi_farm",
                  "kbs_banff", "wonyi_gyeongju", "wonyi_geoje")
# 출처를 기록하지 않고 취득해 채널을 모르는 영상 — 추측해 채우지 않는다(규칙 §4-2)
EXISTING_CHANNEL_UNKNOWN = ("baekmansonghee_jirisan", "softyeon_ceramics", "jissi_farm")

# 패널에 절대 들어가면 안 되는 영상. 사유가 서로 다르므로 함께 기록한다.
FORBIDDEN = {
    "gwaktube_soviet_apartment": "SAMPLE_CONSUMED_PILOT",
    "kheritage_grave_excavation": "SAMPLE_CONSUMED_PILOT",
    "_10_000_Every_Day_You_Survive_In_The_Wilderness": "NO_INDEPENDENT_REFERENCE",
    "pland_costco_hosting": "PRIOR_EXPOSURE_RISK",
}

REPLACEMENT_REASONS = (
    "TECH_FILE_UNAVAILABLE", "TECH_DOWNLOAD_FAILURE", "TECH_DECODE_FAILURE",
    "TECH_SEGMENTATION_FAILURE", "TECH_PIPELINE_FAILURE", "RIGHTS_NOT_USABLE",
    "PREDEFINED_AUTOMATIC_QC_FAILURE")


def selection_key(source_id: str) -> str:
    """SHA256(namespace | seed_commit | normalized_video_id).

    `normalized_video_id`는 공백만 제거한 값이다 — **casefold하지 않는다.**
    YouTube ID는 대소문자를 구분하므로 접으면 서로 다른 영상이 같은 키가 될 수 있다
    (규칙 §6에 예외로 명시).
    """
    norm = (source_id or "").strip()
    return hashlib.sha256(
        f"{NAMESPACE}|{SEED_COMMIT}|{norm}".encode("utf-8")).hexdigest()


def pool_sha256(pool: list) -> str:
    """풀 동결 해시. 저장 순서에 의존하지 않도록 id로 정렬해 계산한다."""
    canon = [{k: r.get(k) for k in POOL_FIELDS} for r in pool]
    canon.sort(key=lambda r: r["id"])
    return hashlib.sha256(
        json.dumps(canon, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def project_source_ids() -> set:
    """이 프로젝트가 이미 쓰는 YouTube ID 전부 — E1·E4·E5·E6·E8을 한 번에 막는다."""
    ids = set()
    prov = ROOT / "data/provenance/videos.json"
    if prov.exists():
        d = json.loads(prov.read_text(encoding="utf-8"))
        ids |= {v["source_id"] for v in d.get("videos", {}).values() if v.get("source_id")}
    for rel in ("docs/P2_선정표본_2026-08-20.json",
                "artifacts/p2_sampling_frame/manifest.json"):
        f = ROOT / rel
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for key in ("selected", "videos"):
            for row in (d.get(key) or []):
                if isinstance(row, dict) and row.get("source_id"):
                    ids.add(row["source_id"])
    vdir = ROOT / "data/videos"
    if vdir.is_dir():
        ids |= {p.stem for p in vdir.glob("*.mp4")}          # 파일명이 곧 ID인 기확보분
    return ids


def eligibility_verdict(rec: dict, used_ids: set, existing_channel_ids: set) -> tuple:
    """(적격, 사유코드). 순서는 규칙 §4 그대로 — 앞에서 걸리면 그 사유로 기록한다."""
    if not rec.get("fetch_ok"):
        return False, "E9_METADATA_FETCH_FAILED"
    if rec.get("id") in used_ids:
        return False, "E1_E8_ALREADY_USED_IN_PROJECT"
    if rec.get("is_live") or rec.get("live_status") not in (None, "not_live", "was_live"):
        return False, "E9_LIVE_OR_UPCOMING"
    if (rec.get("age_limit") or 0) > 0:
        return False, "E9_AGE_RESTRICTED"
    if rec.get("availability") not in (None, "public"):
        return False, "E9_NOT_PUBLIC"
    d = rec.get("duration")
    if not d or not (750 <= d <= 2000):
        return False, "E12_DURATION_OUT_OF_BAND"
    lang = (rec.get("language") or "").lower()
    if lang and not lang.startswith("ko"):                   # 명시적 비한국어만 배제
        return False, "E13_EXPLICIT_NON_KOREAN"
    if rec.get("channel_id") and rec["channel_id"] in existing_channel_ids:
        return False, "C2_EXISTING_PANEL_CHANNEL"
    return True, None


def rank_pool(pool: list) -> list:
    """selection_key 오름차순. 동점은 id로 가른다(해시 충돌 시에도 결정적이도록)."""
    return sorted(pool, key=lambda r: (selection_key(r["id"]), r["id"]))


def pick(pool: list) -> tuple:
    """(primary 2편, reserve). 채널이 겹쳐 건너뛴 후보는 reserve 맨 앞으로 (규칙 §6)."""
    ranked = rank_pool(pool)
    primary, skipped, rest = [], [], []
    for r in ranked:
        if not primary:
            primary.append(r)
        elif len(primary) < 2:
            same = (r.get("channel_id") and r["channel_id"] == primary[0].get("channel_id"))
            (skipped if same else primary).append(r)
        else:
            rest.append(r)
    return primary, skipped + rest


def build(meta_path: Path, existing_channels: dict) -> dict:
    rows = [json.loads(l) for l in meta_path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    used = project_source_ids()
    ch_ids = {v for v in existing_channels.values() if v}
    pool, rejected, seen = [], [], set()
    for r in rows:
        if r.get("id") in seen:                              # 규칙 §3 — 첫 등장만
            continue
        seen.add(r.get("id"))
        ok, reason = eligibility_verdict(r, used, ch_ids)
        rec = {k: r.get(k) for k in POOL_FIELDS}
        if ok:
            pool.append(rec)
        else:
            rejected.append({**rec, "reason": reason})
    pool.sort(key=lambda r: r["id"])
    sha = pool_sha256(pool)                                  # ← 정렬 뒤, 선정 전에 확정
    primary, reserve = pick(pool)
    return {
        "candidate_pool": {"sha256": sha, "n": len(pool), "videos": pool},
        "rejected": rejected,
        "selected_new": [{**r, "selection_key": selection_key(r["id"]),
                          "rank": i + 1} for i, r in enumerate(primary)],
        "reserve_order": [{**r, "selection_key": selection_key(r["id"]),
                           "rank": i + 1} for i, r in enumerate(reserve)],
    }


def _n_segments(video_id: str) -> int | None:
    p = ROOT / "work" / video_id / "segments.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["n_segments"]


def assemble(sel: dict, existing_channels: dict, new_video_ids: dict,
             jissi_verdict: dict) -> dict:
    """선정 결과 + 고정 사실을 합쳐 최종 manifest를 만든다.

    `new_video_ids`는 선정된 source_id → 프로젝트 video_id 대응이다. 이름은
    **내용이 아니라 source_id에서** 딴다 — 제목을 보고 짓는 순간 선정 단계에
    내용 판단이 섞인 것처럼 보인다.
    """
    final = list(EXISTING_PANEL) + [new_video_ids[r["id"]] for r in sel["selected_new"]]
    return {
        "schema_version": 1,
        "panel_id": "m8_c2_n8_v1",
        "created": "2026-08-27",
        "design": {
            "fixed_n": FIXED_N,
            "top_up_allowed": False,
            "c2_statistic": "median",
            "c2_threshold": C2_THRESHOLD,
            "reference_author": "human",
            "reference_blinded_to_m8": True,
            "evaluation_complete_is_not_acceptance_pass": True,
        },
        "seed": {"namespace": NAMESPACE, "commit": SEED_COMMIT, "algorithm": "sha256"},
        "sourcing_rule": {
            "path": "docs/finalization/M8_C2_SOURCING_RULE_2026-08-27.md",
            "sha256": "cd6dd0ad2e2ffd452d36fdcfdae26d2dec6b151bd12b1f818cae95b1698aa803",
            "frozen_before_candidate_review": True,
            "frozen_commit": "66b0f93",
            "reused_from": "docs/P2_영상후보_스크리닝규격_2026-08-20.md",
        },
        "existing_panel": [
            {"video_id": v, "n_segments": _n_segments(v), "eligibility": "ELIGIBLE",
             "channel_id": existing_channels.get(v),
             "channel_known": v not in EXISTING_CHANNEL_UNKNOWN}
            for v in EXISTING_PANEL],
        "caption_remediation": jissi_verdict,
        "candidate_pool": sel["candidate_pool"],
        "rejected_candidates": sel["rejected"],
        "selected_new": [{**r, "video_id": new_video_ids[r["id"]],
                          "n_segments": _n_segments(new_video_ids[r["id"]])}
                         for r in sel["selected_new"]],
        "reserve_order": sel["reserve_order"],
        "final_panel": final,
        "exclusions": [{"video_id": v, "reason_code": c} for v, c in FORBIDDEN.items()],
        "prior_exposure_exclusions": [{
            "video_id": "pland_costco_hosting",
            "statement": ("M8 산출물은 없고 표본 소비 선언 대상도 아니다. 다만 케이스 "
                          "스터디에서 캡션·검색 결과·프레임을 상세 열람했다"),
            "classification": "avoidable prior-exposure risk (오염 확정이 아니다)"}],
        "channel_constraints": {
            "new_distinct_from_each_other": True,
            "new_distinct_from_known_existing": True,
            "existing_known_channel_ids": existing_channels,
            "existing_unknown_channel": list(EXISTING_CHANNEL_UNKNOWN),
            "same_channel_pair_in_panel": ["wonyi_gyeongju", "wonyi_geoje"],
            "note": ("동일 채널 2편은 한계로 기록만 한다 — C2 계산법·weighting·"
                     "clustering 보정을 새로 만들지 않는다"),
        },
        "replacement_policy": {"allowed_reasons": list(REPLACEMENT_REASONS),
                               "human_choice_allowed": False,
                               "order": "reserve_order 그대로"},
        "replacements": [],
        "boundaries": {
            "m8_official_run": False,
            "event_recall_calculated": False,
            "m9_test_opened": False,
            "test_outcome_viewed": False,
            "threshold_changed": False,
            "panel_chosen_from_outcome": False,
            "selection_used_only_metadata": True,
        },
        "pilot_note": ("소비된 2개 pilot 영상에서 temporal Event Recall@IoU>=0.3 = 0.3019가 "
                       "관찰되었으나, 해당 영상은 사전 선언에 따라 confirmation panel에서 "
                       "제외했으며 C2 판정에는 포함하지 않았다"),
        "representativeness": ("확률표본이 아니다. 사전 정의된 적격 조건과 deterministic "
                              "selection rule로 고정한 M8 구조 판정 패널이다"),
    }


def verify(man: dict) -> list:
    """동결 이후 무엇이 어긋났는지. 빈 목록이면 그대로다."""
    diffs = []
    pool = man["candidate_pool"]["videos"]
    if pool_sha256(pool) != man["candidate_pool"]["sha256"]:
        diffs.append("candidate_pool_sha256 불일치 — 풀이 동결 이후에 바뀌었다")
    if man["seed"]["namespace"] != NAMESPACE or man["seed"]["commit"] != SEED_COMMIT:
        diffs.append("seed 불일치")
    primary, reserve = pick(pool)
    if [r["id"] for r in primary] != [r["id"] for r in man["selected_new"]]:
        diffs.append("primary 재현 실패")
    if [r["id"] for r in reserve] != [r["id"] for r in man["reserve_order"]]:
        diffs.append("reserve 재현 실패")
    d = man["design"]
    if d["fixed_n"] != FIXED_N or d["top_up_allowed"] or d["c2_threshold"] != C2_THRESHOLD:
        diffs.append("design 규칙이 바뀌었다")
    final = man["final_panel"]
    if len(final) != FIXED_N or len(set(final)) != FIXED_N:
        diffs.append(f"final_panel이 고유 {FIXED_N}편이 아니다")
    for v in FORBIDDEN:
        if v in final:
            diffs.append(f"금지 영상이 패널에 있다: {v}")
    for e in man.get("replacements", []):
        if e.get("reason_code") not in REPLACEMENT_REASONS:
            diffs.append(f"허용되지 않은 교체 사유: {e.get('reason_code')}")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--assemble", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--meta", type=Path)
    ap.add_argument("--selection", type=Path)
    ap.add_argument("--new-ids", type=Path,
                    help='{"<source_id>": "<video_id>"} 대응. 이름은 source_id에서 딴다')
    ap.add_argument("--jissi", type=Path, help="jissi_farm 재캡셔닝 판정 JSON")
    ap.add_argument("--existing-channels", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.verify:
        if not args.out.exists():
            print(f"manifest가 없다: {args.out}")
            return 2
        diffs = verify(json.loads(args.out.read_text(encoding="utf-8")))
        print("\n".join(diffs) if diffs else "동결 상태 그대로다")
        return 1 if diffs else 0

    if args.assemble:
        if args.out.exists():
            print(f"{args.out}는 이미 있다 — 동결본을 덮지 않는다")
            return 2
        man = assemble(
            json.loads(args.selection.read_text(encoding="utf-8")),
            json.loads(args.existing_channels.read_text(encoding="utf-8")),
            json.loads(args.new_ids.read_text(encoding="utf-8")),
            json.loads(args.jissi.read_text(encoding="utf-8")))
        diffs = verify(man)
        if diffs:
            print("조립 결과가 자체 검증을 통과하지 못했다:\n" + "\n".join(diffs))
            return 1
        args.out.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print("final_panel:", ", ".join(man["final_panel"]))
        return 0

    if not args.build:
        print("--build / --assemble / --verify 중 하나")
        return 2
    if args.out.exists():
        print(f"{args.out}는 이미 있다 — 동결본을 덮지 않는다")
        return 2
    ch = json.loads(args.existing_channels.read_text(encoding="utf-8"))
    res = build(args.meta, ch)
    print(f"적격 {res['candidate_pool']['n']} · 탈락 {len(res['rejected'])} · "
          f"pool_sha {res['candidate_pool']['sha256'][:16]}")
    for r in res["selected_new"]:
        print(f"PRIMARY_{r['rank']}  {r['id']}  {r['duration']}s  {r['channel']}")
    for r in res["reserve_order"][:5]:
        print(f"RESERVE_{r['rank']}  {r['id']}  {r['duration']}s  {r['channel']}")
    args.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
