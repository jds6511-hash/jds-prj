"""AI 초안용 최소 blind handoff — **정체성 필드와 원본 프레임 경로만 나간다.**

새 채팅에 저장소나 인수문서를 주지 않는다. 초안 작성에 필요한 최소만 만든다.

```
payload    query_id · video_id · query_type · 컨택트시트 파일명
프롬프트     동결본을 내용 변경 없이 복사 (sha256 불일치면 fail-closed)
안 나가는 것  사람이 쓴 text·gt_start·gt_end·note · 기존 20건 · 캡션 · 파이프라인 자막 ·
           임베딩 · 색인 · 검색 결과 · 순위 · 점수 · RR/MRR · arm · 평가 산출물
```

**적격 판정에 현재 라벨 내용을 쓰지 않는다.** 기준은 셋뿐이다 — 활성 설계의 행인가,
전환 동결 시점 완료분(20건)에 속하지 않는가, 동결 유형이 장면형인가.

전환 동결 이후 사람이 더 썼을 수 있으므로 두 집합을 나눠 보고한다.

```
protocol_eligible_scene_rows   전환 시점 기준 최대 적격
currently_blank_scene_rows     지금도 비어 있는 행 (실제로 보낼 대상)
```

이미 사람이 쓴 장면형 행은 지우지 않고, 초안을 요청하지도 않는다. **값은 출력하지
않고 개수 차이만 보고한다.**

토큰 검사는 **payload와 프롬프트·README를 구분한다.** 프롬프트에 "캡션에서 추론하지
마라" 같은 문장이 있는 것은 정상이고, 금지 대상은 payload에 그 정보가 실리는 것이다.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_active_design as ACTIVE                                  # noqa: E402
import p2_ai_draft as AID                                          # noqa: E402
import p2_gt_freeze as PREGT                                       # noqa: E402
import p2_hybrid_freeze as HF                                      # noqa: E402
import p2_label_intake as INTAKE                                   # noqa: E402

HANDOFF = ROOT / "label_kit" / "p2_ai_assist" / "handoff"
SHEETS = ROOT / "label_kit" / "p2" / "contact_sheets"
SCENE = "장면형"
CSV_NAME = "p2_scene_rows_for_ai.csv"
MANIFEST_NAME = "p2_scene_handoff_manifest.json"
PROMPT_NAME = "PROMPT_FOR_AI_DRAFTER.txt"
README_NAME = "README_AI_HANDOFF.txt"
BY_VIDEO = "by_video"
CSV_COLUMNS = ("query_id", "video_id", "query_type")
QUERY_KEYS = {"query_id", "query_type"}
VIDEO_KEYS = {"video_id", "queries", "contact_sheets"}
MANIFEST_KEYS = {"videos", "row_count", "video_count", "csv_sha256",
                 "contact_sheet_manifest_source_sha256", "query_type",
                 "generated_from"}
EXPECTED_PROMPT_SHA256 = \
    "e7b153d095031f867c5866dc6d312a8232fd3e1759a70203078450b13dba76ff"
SHEET_RE = re.compile(r"^(?P<vid>.+)_p(?P<page>\d{2})\.jpg$")
FORBIDDEN_PAYLOAD_TOKENS = (
    "gt_start", "gt_end", "caption", "subtitle", "stt", "embedding", "index",
    "retrieval", "rank", "score", "mrr", "adoption", "evaluate", "alpha",
    "bootstrap", "3b", "4b", "arm", "note", "text")
README = """P2 AI 초안 handoff — 새 채팅에 이것만 올린다

1. PROMPT_FOR_AI_DRAFTER.txt 내용을 새 채팅의 **첫 메시지**로 보낸다.
   프롬프트를 고쳐 쓰지 마라 — 해시로 고정돼 있다.

2. 그다음 **영상 하나씩** 보낸다. 한 batch = 영상 1편.
   - by_video/<video_id>.json  (그 영상의 질의 목록)
   - 그 영상의 컨택트시트 JPG **전부**
     경로: label_kit/p2/contact_sheets/<video_id>_pNN.jpg
   시트를 전부 주는 이유: 서로 다른 검색 의도를 제안할 수 있어야 한다.

3. 프롬프트의 {} 자리 값
   query_id · video_id · query_type은 by_video JSON에 있다.
   구간 격자는 시트에서 센다 — 한 장에 6열 x 10행 = 60구간이고, 마지막 장의
   타일 수까지 더하면 마지막 idx다.
   이 값들을 payload에 넣지 않은 것은 의도한 것이다(스키마 allowlist).

   주의 — (마지막 idx + 1) x 5초는 **격자 상한이고 실제 영상 길이가 아니다.**
   마지막 구간은 5초보다 짧을 수 있다. 그 값을 정확한 duration이라고 말하지 말고,
   마지막 구간의 끝 경계를 확정하는 데 쓰지 마라. 후보 위치를 가늠하는 데만 쓴다.
   실제 경계는 사람이 원본 영상에서 확정한다.

하지 말 것
   - 과거 연구 문서 · 모델 산출물 · 검색 결과 · 순위/점수를 올리는 것
   - 프롬프트 수정
   - 여러 영상을 한 번에 섞어 보내는 것

출력은 **초안**이다. 정답이 아니다.
사람이 원본 영상에서 확인하고 accept / edit / reject를 고른 뒤에야 GT가 된다.
"""


class HandoffError(RuntimeError):
    pass


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _blank(row: dict) -> bool:
    return not all((row.get(c) or "").strip()
                   for c in ("text", "gt_start", "gt_end"))


# ------------------------------------------------------------- 적격 판정

def protocol_eligible(freeze_path=None, allocation: list = None) -> list:
    """전환 동결 기준 적격 행. **현재 라벨 내용을 보지 않는다.**"""
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    src = Path(freeze_path) if freeze_path is not None else HF.OUT
    if not src.is_file():
        raise HandoffError(f"전환 동결 파일이 없다: {src}")
    done = set(json.loads(src.read_text(encoding="utf-8"))
               ["human_only"]["query_ids"])
    return [r for r in allocation
            if r["query_type"] == SCENE and r["query_id"] not in done]


def currently_blank(query_ids, intake=None) -> list:
    """지금도 비어 있는 행만. **비었는지 여부만 쓰고 값은 반환하지 않는다.**"""
    path = Path(intake) if intake is not None else INTAKE.CSV_PATH
    rows = {(r.get("query_id") or "").strip(): r for r in csv.DictReader(
        path.read_text(encoding="utf-8-sig").splitlines())}
    out = []
    for q in query_ids:
        r = rows.get(q)
        if r is None:
            raise HandoffError(f"{q}: 작업 CSV에 없다")
        if _blank(r):
            out.append(q)
    return out


def sheets_of(video_id: str, sheets_dir=None) -> list:
    d = Path(sheets_dir) if sheets_dir is not None else SHEETS
    got = sorted(p.name for p in d.glob(f"{video_id}_p*.jpg"))
    if not got:
        raise HandoffError(f"{video_id}: 컨택트시트가 없다 ({d})")
    for name in got:
        m = SHEET_RE.match(name)
        if not m or m.group("vid") != video_id:
            raise HandoffError(f"{video_id}: 시트 이름이 규격을 벗어난다 {name}")
    return got


# ------------------------------------------------------------- 생성

def build_payload(freeze_path=None, allocation: list = None, intake=None,
                  sheets_dir=None) -> dict:
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    eligible = protocol_eligible(freeze_path, allocation)
    blank = set(currently_blank([r["query_id"] for r in eligible], intake))
    rows = [r for r in eligible if r["query_id"] in blank]
    seen, videos = set(), []
    for r in rows:
        if r["query_id"] in seen:
            raise HandoffError(f"{r['query_id']}: 중복")
        seen.add(r["query_id"])
    order = []
    for r in rows:
        if r["video_id"] not in order:
            order.append(r["video_id"])
    for vid in order:
        qs = [r for r in rows if r["video_id"] == vid]
        videos.append({"video_id": vid,
                       "queries": [{"query_id": q["query_id"],
                                    "query_type": q["query_type"]} for q in qs],
                       "contact_sheets": sheets_of(vid, sheets_dir)})
    return {"rows": [{c: r[c] for c in CSV_COLUMNS} for r in rows],
            "videos": videos,
            "protocol_eligible_scene_rows": len(eligible),
            "currently_blank_scene_rows": len(rows),
            "already_written_scene_rows": len(eligible) - len(rows)}


def prepare(out_dir=None, freeze_path=None, allocation: list = None,
            intake=None, sheets_dir=None) -> dict:
    out = Path(out_dir) if out_dir is not None else HANDOFF
    payload = build_payload(freeze_path, allocation, intake, sheets_dir)
    (out / BY_VIDEO).mkdir(parents=True, exist_ok=True)

    csv_path = out / CSV_NAME
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(CSV_COLUMNS))
        w.writeheader()
        w.writerows(payload["rows"])

    prompt_path = out / PROMPT_NAME
    prompt_path.write_text(AID.PROMPT_TEMPLATE, encoding="utf-8")
    got = hashlib.sha256(prompt_path.read_text(encoding="utf-8")
                         .encode("utf-8")).hexdigest()
    if got != EXPECTED_PROMPT_SHA256:
        prompt_path.unlink()
        raise HandoffError(f"프롬프트 sha256 불일치 — 기대 "
                           f"{EXPECTED_PROMPT_SHA256[:12]}… 실제 {got[:12]}…. "
                           "프롬프트를 고쳐 쓰지 않는다")

    for v in payload["videos"]:
        (out / BY_VIDEO / f"{v['video_id']}.json").write_text(
            json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "query_type": SCENE,
        "generated_from": {
            "active_design": "docs/P2_활성설계_2026-08-24.json",
            "transition_freeze":
                "docs/probes/_scratch/p2_gt_hybrid_transition_freeze.json"},
        "row_count": len(payload["rows"]),
        "video_count": len(payload["videos"]),
        "csv_sha256": _sha256_file(csv_path),
        "contact_sheet_manifest_source_sha256":
            PREGT.sheet_manifest(Path(sheets_dir) if sheets_dir else SHEETS)
            ["manifest_sha256"],
        "videos": payload["videos"]}
    (out / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / README_NAME).write_text(README, encoding="utf-8")
    return {"path": str(out), "prompt_sha256": got,
            "protocol_eligible_scene_rows":
                payload["protocol_eligible_scene_rows"],
            "currently_blank_scene_rows": payload["currently_blank_scene_rows"],
            "already_written_scene_rows":
                payload["already_written_scene_rows"],
            "video_count": manifest["video_count"],
            "row_count": manifest["row_count"],
            "csv_sha256": manifest["csv_sha256"]}


# ------------------------------------------------------------- 검증

_HEX64 = re.compile(r"\b[0-9a-f]{40,}\b")


def _residual(text: str, identities) -> str:
    """정체성 문자열을 지운 뒤 남는 부분. 남은 곳에 금지 토큰이 있으면 실제 누출이다.

    sha256 16진 문자열도 지운다 — 해시 안에 우연히 `3b`·`4b`가 들어 있어 그것을
    모델 이름 누출로 오판했다(실측). 해시는 정체성 값이지 payload 내용이 아니다.
    """
    text = _HEX64.sub(" ", text)
    for s in sorted(identities, key=len, reverse=True):
        text = text.replace(s, " ")
    return text


def verify(out_dir=None, allocation: list = None, freeze_path=None,
           sheets_dir=None) -> dict:
    out = Path(out_dir) if out_dir is not None else HANDOFF
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    by_id = {r["query_id"]: r for r in allocation}
    checks, problems = {}, []

    def fail(msg):
        problems.append(msg)

    for name in (CSV_NAME, MANIFEST_NAME, PROMPT_NAME, README_NAME):
        if not (out / name).is_file():
            raise HandoffError(f"{name}이 없다 — prepare를 먼저 돌려라")

    rows = list(csv.DictReader((out / CSV_NAME).read_text(encoding="utf-8-sig")
                              .splitlines()))
    got_cols = list(rows[0]) if rows else list(CSV_COLUMNS)
    checks["csv_columns_allowlisted"] = got_cols == list(CSV_COLUMNS)
    if not checks["csv_columns_allowlisted"]:
        fail(f"CSV 열이 {got_cols}다 — {list(CSV_COLUMNS)}만 허용")

    ids = [r["query_id"] for r in rows]
    checks["query_ids_unique"] = len(set(ids)) == len(ids)
    checks["subset_of_active_design"] = all(q in by_id for q in ids)
    checks["scene_only"] = all(r["query_type"] == SCENE for r in rows)
    checks["video_id_matches_design"] = all(
        q in by_id and rows[i]["video_id"] == by_id[q]["video_id"]
        for i, q in enumerate(ids))

    src = Path(freeze_path) if freeze_path is not None else HF.OUT
    done = set(json.loads(src.read_text(encoding="utf-8"))
               ["human_only"]["query_ids"])
    checks["transition_completed_excluded"] = not (set(ids) & done)

    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    checks["manifest_keys_allowlisted"] = set(manifest) <= MANIFEST_KEYS
    m_ids = []
    for v in manifest.get("videos", []):
        if set(v) != VIDEO_KEYS:
            fail(f"video 객체 키가 {sorted(v)}다 — {sorted(VIDEO_KEYS)}만 허용")
        for q in v.get("queries", []):
            if set(q) != QUERY_KEYS:
                fail(f"query 객체 키가 {sorted(q)}다 — {sorted(QUERY_KEYS)}만 허용")
            m_ids.append(q["query_id"])
    checks["json_keys_allowlisted"] = not problems
    checks["manifest_matches_csv"] = sorted(m_ids) == sorted(ids)
    checks["row_count_matches"] = manifest.get("row_count") == len(rows)
    checks["csv_sha256_matches"] = manifest.get("csv_sha256") == \
        _sha256_file(out / CSV_NAME)

    sheets_dir = Path(sheets_dir) if sheets_dir is not None else SHEETS
    pages = 0
    for v in manifest.get("videos", []):
        want = sheets_of(v["video_id"], sheets_dir)
        if v["contact_sheets"] != want:
            fail(f"{v['video_id']}: 시트 목록이 실제와 다르다 "
                 f"({len(v['contact_sheets'])} vs {len(want)})")
        for name in v["contact_sheets"]:
            if not (sheets_dir / name).is_file():
                fail(f"{name}이 없다")
        pages += len(v["contact_sheets"])
    checks["contact_sheets_present"] = not any("없다" in p for p in problems)
    checks["page_counts_match_source"] = not any("시트 목록" in p
                                                 for p in problems)
    checks["sheet_manifest_source_matches"] = \
        manifest.get("contact_sheet_manifest_source_sha256") == \
        PREGT.sheet_manifest(sheets_dir)["manifest_sha256"]

    prompt_text = (out / PROMPT_NAME).read_text(encoding="utf-8")
    actual = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    checks["prompt_sha256_matches"] = actual == EXPECTED_PROMPT_SHA256

    identities = set(ids) | {r["video_id"] for r in rows} | {SCENE} | \
        {n for v in manifest.get("videos", []) for n in v["contact_sheets"]} | \
        set(CSV_COLUMNS) | QUERY_KEYS | VIDEO_KEYS | MANIFEST_KEYS | \
        {"docs/P2_활성설계_2026-08-24.json",
         "docs/probes/_scratch/p2_gt_hybrid_transition_freeze.json"}
    payload_text = _residual(
        (out / CSV_NAME).read_text(encoding="utf-8") + "\n"
        + (out / MANIFEST_NAME).read_text(encoding="utf-8") + "\n"
        + "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((out / BY_VIDEO).glob("*.json"))),
        identities).lower()
    hits = sorted(t for t in FORBIDDEN_PAYLOAD_TOKENS if t in payload_text)
    checks["payload_has_no_forbidden_token"] = not hits
    if hits:
        fail(f"payload에 금지 토큰 {hits}")

    ok = all(checks.values()) and not problems
    return {"ok": ok, "checks": checks, "problems": problems,
            "n_rows": len(rows), "n_videos": len(manifest.get("videos", [])),
            "pages_referenced": pages,
            "prompt_sha256": {"expected": EXPECTED_PROMPT_SHA256,
                              "actual": actual,
                              "match": checks["prompt_sha256_matches"]}}


def export_sheets(out_dir=None, sheets_dir=None) -> dict:
    """업로드 편의용 복제. **원본은 수정하지 않고, 기본 동작이 아니다.**"""
    out = Path(out_dir) if out_dir is not None else HANDOFF
    sheets_dir = Path(sheets_dir) if sheets_dir is not None else SHEETS
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    dst = out / "contact_sheets"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for v in manifest["videos"]:
        for name in v["contact_sheets"]:
            shutil.copy2(sheets_dir / name, dst / name)
            n += 1
    return {"copied": n, "path": str(dst)}


def main():
    ap = argparse.ArgumentParser(
        description="AI 초안용 최소 blind handoff — 초안 생성은 하지 않는다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "verify", "export-sheets"):
        s = sub.add_parser(name)
        s.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "prepare":
        print(json.dumps(prepare(a.out), ensure_ascii=False, indent=2))
    elif a.cmd == "verify":
        r = verify(a.out)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if not r["ok"]:
            raise SystemExit(1)
    else:
        print(json.dumps(export_sheets(a.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
