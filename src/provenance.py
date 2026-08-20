"""영상 출처 provenance — **인덱싱 전에 기록한다. 사후에 붙일 수 없다.**

기존 11편의 `work/*/meta.json`에는 `dim`·`embed_model`·`n_segments`·`text_hash`만
있어 **출처 URL·영상 ID가 없다.** 그래서 신규 후보와의 ID 단위 중복 대조가
불가능하다(사전등록 `부호역전_확증_보충3_P2표집범위` §7). 그 공백을 신규 영상부터
닫는다.

레지스트리는 **추적되는 파일**이다(`data/provenance/videos.json`). 영상 파일은
gitignore 대상이지만 출처 기록은 저장소에 남아야 한다.

```
videos          video_id -> {source_url, source_id, file_sha256}
legacy_exempt   video_id -> {reason}   출처를 알 수 없는 기존 영상
```

**면제는 데이터로만 존재한다.** 코드가 조용히 넘어가지 않는다 — 레지스트리에도
면제 목록에도 없는 영상은 M1이 **차단**한다(fail-closed).

**이 필드는 지표·eligibility 계산에 쓰지 않는다.** 기록 전용이다.
"""
import hashlib
import json
from pathlib import Path

PROV_FIELDS = ("source_url", "source_id", "file_sha256")
REGISTRY_REL = "data/provenance/videos.json"
EXEMPT_MARK = "legacy_no_provenance"


class ProvenanceError(RuntimeError):
    pass


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def registry_path(root) -> Path:
    return Path(root) / REGISTRY_REL


def load_registry(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"videos": {}, "legacy_exempt": {}}
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("videos", {})
    d.setdefault("legacy_exempt", {})
    return d


def duplicate_source_ids(reg: dict) -> dict:
    """같은 `source_id`가 두 `video_id`에 붙으면 중복 편입이다."""
    seen = {}
    for vid, e in (reg.get("videos") or {}).items():
        sid = e.get("source_id")
        if sid:
            seen.setdefault(sid, []).append(vid)
    return {s: v for s, v in seen.items() if len(v) > 1}


def resolve(reg: dict, video_id: str, video_path=None,
            verify_hash: bool = True) -> dict:
    """M1이 부를 함수. **없으면 통과시키지 않는다.**

    반환값이 `segments.json`에 그대로 들어간다. 면제 영상은 면제 표시를 남기고,
    값을 추측해 채우지 않는다.
    """
    entry = (reg.get("videos") or {}).get(video_id)
    if entry is None:
        if video_id in (reg.get("legacy_exempt") or {}):
            return {"provenance_status": EXEMPT_MARK,
                    "reason": reg["legacy_exempt"][video_id].get("reason", ""),
                    **{f: None for f in PROV_FIELDS}}
        raise ProvenanceError(
            f"{video_id}: provenance 레지스트리에 없다 — 신규 영상은 "
            f"`{REGISTRY_REL}`에 source_url·source_id·file_sha256을 먼저 기록해야 "
            "M1을 돌릴 수 있다. 인덱싱 후에는 붙일 수 없다")
    missing = [f for f in PROV_FIELDS if not entry.get(f)]
    if missing:
        raise ProvenanceError(f"{video_id}: provenance 필드 누락 {missing}")
    dup = duplicate_source_ids(reg)
    mine = [s for s, v in dup.items() if video_id in v]
    if mine:
        raise ProvenanceError(
            f"{video_id}: source_id 중복 {mine} — 같은 출처가 두 번 편입됐다")
    out = {"provenance_status": "recorded",
           **{f: entry[f] for f in PROV_FIELDS}}
    if verify_hash:
        if video_path is None:
            raise ProvenanceError(f"{video_id}: 해시 대조할 파일 경로가 없다")
        got = sha256_file(video_path)
        if got != entry["file_sha256"]:
            raise ProvenanceError(
                f"{video_id}: file_sha256 불일치 — 등록 {entry['file_sha256'][:12]} "
                f"vs 실제 {got[:12]}. 검증한 바이트와 다른 파일이다")
        out["sha256_verified_at_m1"] = True
    return out


def propagate(src: dict, dst: dict) -> dict:
    """downstream meta로 **그대로** 넘긴다. 중간 단계가 덮어쓰지 못한다."""
    prov = src.get("provenance")
    if prov is None:
        return dst
    existing = dst.get("provenance")
    if existing is not None and existing != prov:
        raise ProvenanceError(
            f"provenance 덮어쓰기 시도: {existing} -> {prov}")
    return {**dst, "provenance": prov}
