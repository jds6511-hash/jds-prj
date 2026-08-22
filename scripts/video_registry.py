"""영상 provenance registry — **canonical schema · 검증 · 읽기 어댑터.**

문제: 영상 identity가 여러 manifest에 흩어져 있다. 선정표본, 승격 기록, 입력 해시
게이트, 변환 기록, meta.json의 provenance가 각각 일부만 들고 있어서 "이 파일이 어디서
왔고 어떤 바이트인가"를 한 곳에서 답할 수 없다.

**이 모듈은 아직 source of truth가 아니다.** 지금 P2 FULL이 돌고 있고, 실행 중에
provenance 구조를 갈아타는 것은 그 자체로 재현성 사고다. 그래서 여기서는

```
1  canonical schema
2  fail-closed 검증 API
3  읽기 전용 어댑터 (writer를 두지 않는다)
4  기존 manifest를 스키마로 투영해 어긋나지 않는지 확인하는 경로
```

까지만 만든다. 전환은 FULL 종료 후 별도 판단이다.

**registry 필드를 지표·적격성·채택 판단에 쓰지 않는다.** 여기 있는 것은 신원과 바이트
사실이고, 성능 해석의 입력이 아니다.

legacy 규칙: 기확보 4편은 취득 시점에 출처 ID·해시를 남기지 않았다. 그것을 **추측해
채우지 않는다** — 없는 필드는 없는 채로 두고 `legacy_exempt`와 사유를 요구한다.

재현:
  python scripts/video_registry.py --check          # 기존 manifest 투영 후 검증
  python scripts/video_registry.py --emit out.jsonl # 투영 결과를 파일로 (참고용)
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
DURATION_ARTIFACT = ROOT / "docs" / "P2_FREE4_duration_2026-08-22.json"
DEFAULT_PATH = ROOT / "data" / "registry" / "videos.jsonl"
SHA256 = re.compile(r"^[0-9a-f]{64}$")

# 다운스트림 단계가 바꿀 수 없는 필드. 검색·평가·리포트는 이것을 읽을 수만 있다.
IDENTITY_FIELDS = ("video_id", "source_id", "source_url", "staging_sha256",
                   "production_sha256")
REQUIRED_ALWAYS = ("video_id", "source_id", "acquisition_class", "n_segments",
                   "provenance_reference")
REQUIRED_NEW = ("source_url", "production_sha256")
# legacy에서 값이 없어야 하는 필드 — 있으면 추측해 채운 것이다
LEGACY_MUST_BE_ABSENT = ("source_url", "staging_sha256", "production_sha256",
                         "acquisition_tool")
LEGACY_CLASS = "pre_existing"
LEGACY_REASON = ("취득 시점에 출처 ID·해시를 기록하지 않았다 — ID 단위 대조 불가"
                 "(id_level_verified = false)")


class RegistryError(RuntimeError):
    pass


def _hash_ok(v) -> bool:
    return isinstance(v, str) and bool(SHA256.match(v))


def validate(records: list) -> dict:
    """fail-closed 검증. 하나라도 어긋나면 예외를 던진다."""
    if not records:
        raise RegistryError("registry가 비었다")
    seen_v, seen_s = set(), set()
    for r in records:
        vid = r.get("video_id", "<video_id 없음>")
        for f in REQUIRED_ALWAYS:
            if r.get(f) in (None, ""):
                raise RegistryError(f"{vid}: 필수 필드 {f}가 없다")
        if r["video_id"] in seen_v:
            raise RegistryError(f"{r['video_id']}: video_id 중복")
        if r["source_id"] in seen_s:
            raise RegistryError(f"{r['source_id']}: source_id 중복")
        seen_v.add(r["video_id"])
        seen_s.add(r["source_id"])

        legacy = bool(r.get("legacy_exempt"))
        if legacy:
            if r["acquisition_class"] != LEGACY_CLASS:
                raise RegistryError(
                    f"{vid}: legacy_exempt는 acquisition_class == "
                    f"'{LEGACY_CLASS}'에서만 쓴다 (지금 "
                    f"{r['acquisition_class']!r})")
            if not str(r.get("legacy_exempt_reason") or "").strip():
                raise RegistryError(f"{vid}: legacy_exempt에 사유가 없다")
            present = [f for f in LEGACY_MUST_BE_ABSENT if r.get(f)]
            if present:
                raise RegistryError(
                    f"{vid}: legacy인데 {present}가 채워져 있다 — 없는 값을 "
                    f"추측해 채우지 않는다")
            continue

        for f in REQUIRED_NEW:
            if r.get(f) in (None, ""):
                raise RegistryError(f"{vid}: 신규 취득인데 {f}가 없다")
        for f in ("staging_sha256", "production_sha256"):
            if r.get(f) is not None and not _hash_ok(r[f]):
                raise RegistryError(f"{vid}: {f}가 sha256 형식이 아니다")
        s, p = r.get("staging_sha256"), r.get("production_sha256")
        if s and p and s != p and not str(
                r.get("production_differs_reason") or "").strip():
            raise RegistryError(
                f"{vid}: staging과 production 해시가 다르다 — 승격은 복사이므로 "
                f"같아야 하고, 다르면 production_differs_reason이 필요하다")
    return {"ok": True, "n": len(records),
            "n_legacy_exempt": sum(1 for r in records if r.get("legacy_exempt")),
            "identity_fields": list(IDENTITY_FIELDS),
            "note": ("신원·바이트 사실만 담는다. 지표·적격성·채택 판단의 입력이 "
                     "아니다")}


def load(path=DEFAULT_PATH) -> list:
    """읽기 전용 어댑터. **writer를 두지 않는다** — 전환 전까지 쓰기 경로가 없다."""
    p = Path(path)
    if not p.is_file():
        raise RegistryError(f"registry 파일이 없다: {p}")
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def assert_identity_unchanged(before: list, after: list) -> bool:
    """다운스트림이 identity를 바꾸지 못한다."""
    b = {r["video_id"]: r for r in before}
    a = {r["video_id"]: r for r in after}
    gone = sorted(set(b) - set(a))
    if gone:
        raise RegistryError(f"레코드가 사라졌다: {gone}")
    for vid, rec in b.items():
        for f in IDENTITY_FIELDS:
            if rec.get(f) != a[vid].get(f):
                raise RegistryError(
                    f"{vid}: identity 필드 {f}가 바뀌었다 "
                    f"({rec.get(f)!r} → {a[vid].get(f)!r})")
    return True


def _duration_index(artifact, selection: dict) -> dict:
    """측정 artifact를 읽는다 — **값을 그대로 베끼지 않고 격자를 대조한다.**

    artifact가 다른 바이트를 잰 것이면 격자가 사전등록 `n_segments`와 어긋난다.
    그때는 그 길이를 쓰지 않는다.
    """
    if artifact is None:
        return {}
    p = Path(artifact)
    if not p.is_file():
        raise RegistryError(f"duration artifact가 없다: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rel = (str(p.relative_to(ROOT)).replace("\\", "/")
           if p.is_relative_to(ROOT) else str(p))
    out = {}
    for row in doc["rows"]:
        vid = row["video_id"]
        pre = selection.get(vid, {}).get("n_segments")
        if row.get("n_segments_derived") != pre:
            raise RegistryError(
                f"{vid}: artifact의 격자 {row.get('n_segments_derived')}가 "
                f"사전등록 n_segments {pre}와 다르다 — 이 길이를 쓰지 않는다")
        out[vid] = {"duration_sec": row["duration_sec"],
                    "duration_status": "measured",
                    "duration_source": rel,
                    "duration_measurement_path": row.get("measurement_path")}
    return out


def require_duration(records: list) -> dict:
    """duration이 필요한 검사의 진입점. **unknown을 조용히 빼지 않는다.**"""
    unknown = sorted(r["video_id"] for r in records
                     if r.get("duration_status") != "recorded"
                     and r.get("duration_sec") is None)
    if unknown:
        raise RegistryError(
            f"duration이 unknown인 영상 {len(unknown)}편: {unknown} — 이 검사는 "
            f"그 행에 대해 unsupported다. 행을 제외하고 통과시키지 않는다")
    return {"ok": True, "n": len(records)}


def project_from_selection(path=SELECTION,
                           duration_artifact=DURATION_ARTIFACT) -> list:
    """기존 선정표본을 canonical schema로 **투영**한다(변환이 아니라 읽기다).

    없는 값을 만들지 않는다 — 기확보 4편에는 `source_url`·해시 키를 넣지 않고
    `legacy_exempt`와 사유만 적는다. 길이는 세 상태로 구분한다.

    ```
    recorded   선정표본에 기록돼 있다
    measured   측정 artifact를 참조했다 (출처를 함께 적는다)
    unknown    둘 다 없다 — **키를 비우지 않고 상태로 드러낸다**
    ```
    """
    sel = json.loads(Path(path).read_text(encoding="utf-8"))["selected"]
    rel = str(Path(path).relative_to(ROOT)).replace("\\", "/")
    by_id = {r["source_id"]: r for r in sel}
    dur = _duration_index(duration_artifact, by_id)
    out = []
    for r in sel:
        rec = {"video_id": r["source_id"], "source_id": r["source_id"],
               "publisher": r.get("publisher"), "program": r.get("program"),
               "n_segments": r["n_segments"],
               "provenance_reference": rel}
        if r.get("duration_sec") is not None:
            rec["duration_sec"] = r["duration_sec"]
            rec["duration_status"] = "recorded"
            rec["duration_source"] = rel
        elif r["source_id"] in dur:
            rec.update(dur[r["source_id"]])
        else:
            rec["duration_status"] = "unknown"
            rec["duration_unknown_reason"] = (
                "취득 시점에 기록되지 않았고 측정 artifact도 주어지지 않았다 — "
                "n_segments*seg_len으로 추정해 채우지 않는다")
        if r.get("file_sha256"):
            rec.update({"acquisition_class": "downloaded",
                        "source_url": r["source_url"],
                        "staging_sha256": r["file_sha256"],
                        "production_sha256": r["file_sha256"],
                        "audio_language": r.get("selected_audio_language"),
                        "audio_evidence": r.get("speech_status")})
        else:
            rec.update({"acquisition_class": LEGACY_CLASS,
                        "legacy_exempt": True,
                        "legacy_exempt_reason": LEGACY_REASON})
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="기존 manifest 투영 후 스키마 검증")
    ap.add_argument("--emit", help="투영 결과를 JSONL로 쓴다 (참고용, 아직 SoT 아님)")
    a = ap.parse_args()
    recs = project_from_selection()
    r = validate(recs)
    print(f"projected {r['n']} / legacy_exempt {r['n_legacy_exempt']} / "
          f"ok {r['ok']}")
    if a.emit:
        p = Path(a.emit)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                               for x in recs) + "\n", encoding="utf-8")
        print(f"emitted: {p}  (참고용이다 — source of truth 전환은 별도 판단)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
