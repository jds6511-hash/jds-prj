"""P2 AI 초안 — **프롬프트를 결과 전에 고정하고, 초안은 GT가 아니다.**

남은 행의 "초안 작성 노동"만 AI에게 넘긴다. 최종 GT 책임은 사람의 원본 확인에 있다.

```
AI가 볼 수 있는 것   query_id · video_id · 동결 query_type · 원본 영상 · 원본 음성 ·
                   컨택트시트 · 구간 idx/start/end/rep_frame ·
                   영상에 이미 박힌 자막·그래픽
AI가 못 보는 것      캡션(3B·4B) · 파이프라인 자막/STT · 임베딩 · 색인 · 검색 결과 ·
                   순위 · 점수 · RR/MRR · arm 구분 · 평가 산출물 ·
                   **기존 human-only 라벨 내용**
```

**이 모듈은 생성을 하지 않는다.** 프롬프트를 고정하고, 대상 행을 고르고, 초안 산출물의
스키마를 검증하고, 파일로 굳히는 것까지다. 실제 생성은 별도 승인 사건이다.

**온라인 튜닝을 기본 프로토콜로 만들지 않는다.** 10건 만들고 사람이 고쳐보고 프롬프트를
개선해 나머지를 만들면 annotation 프로토콜이 시간에 따라 달라진다. 순서는
`프롬프트 고정 → 전량 생성 → 산출물 동결 → 그 뒤 사람 심사`다.

**음성 근거가 필요한 유형은 도구가 음성을 실제로 듣지 못하면 초안을 만들지 않는다.**
시각 정보만으로 발화 내용을 추측하거나 파이프라인 STT를 대신 읽는 경로를 막는다.
그 행은 `requires_human_audio`로 보내고 사람 작성으로 남긴다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_label_intake as INTAKE                                   # noqa: E402

KIT = ROOT / "label_kit" / "p2_ai_assist"
DRAFTS = KIT / "p2_ai_drafts.jsonl"
TYPES = ("복합형", "자막형", "장면형")
AUDIO_REQUIRED_TYPES = ("자막형", "복합형")
DRAFT_FIELDS = ("query_id", "video_id", "query_type", "draft_text",
                "draft_gt_start", "draft_gt_end", "ai_model", "prompt_sha256",
                "generated_at")
OPTIONAL_FIELDS = ("rationale", "evidence_seg_idx", "ai_provider",
                   "ai_model_version", "settings")
FORBIDDEN_FIELDS = ("retrieval", "score", "rank", "arm", "3b", "4b", "caption",
                    "pipeline_subtitle", "embedding", "index", "rr", "mrr")
EVIDENCE_ALLOWED = ("query_id", "video_id", "frozen_query_type", "source_video",
                    "source_audio", "contact_sheet", "segment_grid",
                    "burned_in_on_screen_text")
EVIDENCE_FORBIDDEN = ("caption_3b", "caption_4b", "pipeline_subtitle_stt",
                      "embedding", "index", "search_result", "rank", "score",
                      "reciprocal_rank", "mean_reciprocal_rank", "arm_identity",
                      "arm_comparison", "evaluator_output",
                      "existing_human_labels")

TYPE_DEFINITION = {
    "자막형": ("말소리에 답이 있다. 화면을 보지 않고 소리만 들어도 그 구간이라고 "
             "알 수 있다"),
    "장면형": ("화면에 답이 있다. 소리를 끄고 봐도 알 수 있고 발화만으로는 알 수 "
             "없다. 화면에 박힌 글자(편집 자막·간판·표지판)는 화면으로 본다"),
    "복합형": ("발화와 화면 양쪽이 필요하거나, 양쪽 모두로 알 수 있다"),
}

PROMPT_TEMPLATE = """당신은 영상 모먼트 검색 벤치마크의 **질의 초안과 시간 구간 초안**을
만든다. 최종 정답은 사람이 원본 영상을 직접 보고 확정한다 — 당신의 출력은 초안이다.

쓸 수 있는 근거는 원본 영상·원본 음성·컨택트시트·구간 격자(idx/start/end)뿐이다.
검색 시스템·캡션 모델·임베딩·색인·검색 결과·순위·점수에서 추론하지 마라. 그것들은
당신에게 주어지지 않았고, 주어진 척 추측해도 안 된다.

대상
  video_id     {video_id}
  query_id     {query_id}
  유형(동결)    {query_type}
  유형 정의     {type_definition}
  구간 격자     0..{last_idx} · 각 구간 {seg_len}초 · 영상 길이 {duration:.1f}초

지시
  1. 이 영상에서 **분명히 식별되는 한 순간**을 고른다.
  2. 그 순간을 사람이 실제로 검색할 때 칠 **한국어 한 문장**을 쓴다.
     정답 구간을 묘사하는 설명문이 아니라 찾을 때 칠 말이다. 10~30자.
     발화를 그대로 옮기지 마라 — 문자열 일치 문제로 바뀐다.
  3. 그 순간을 담는 시간 구간을 초 단위로 제안한다. 사건이 5초면 5초다.
     넉넉하게 잡지 마라. 5초 격자에 맞춰 반올림하지 마라.
  4. 위 유형 정의가 성립하는 질의여야 한다. 유형을 바꾸지 마라.
  5. 원본에서 확인할 수 없는 내용을 만들어 넣지 마라. 확신이 없으면
     draft_text를 비우고 rationale에 이유를 적는다.

출력은 JSON 하나다.
  {{"draft_text": "...", "draft_gt_start": 0.0, "draft_gt_end": 0.0,
    "rationale": "...", "evidence_seg_idx": 0}}
"""


class DraftError(RuntimeError):
    pass


def prompt_sha256() -> str:
    """템플릿 자체의 해시. 행마다 채워 넣은 값과 무관하게 하나로 고정된다."""
    return hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


def prompt_for(query_type: str, query_id: str, video_id: str, n_segments: int,
               duration: float, seg_len: int = 5) -> str:
    if query_type not in TYPE_DEFINITION:
        raise DraftError(f"미허용 유형 {query_type!r}")
    return PROMPT_TEMPLATE.format(
        video_id=video_id, query_id=query_id, query_type=query_type,
        type_definition=TYPE_DEFINITION[query_type], last_idx=n_segments - 1,
        seg_len=seg_len, duration=duration)


# ------------------------------------------------------------- 대상 선정

def pending_rows(completed_ids, allocation: list = None) -> list:
    """활성 설계에서 아직 사람이 완성하지 않은 행. 내용은 읽지 않는다."""
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    done = set(completed_ids)
    return [r for r in allocation if r["query_id"] not in done]


def eligibility(rows: list, audio_supported: bool,
                video_supported: bool = True) -> dict:
    """도구가 실제로 지원하는 근거만으로 초안 가능 여부를 가른다.

    음성 근거가 필요한 유형(자막형·복합형)은 음성을 못 듣는 도구에서 초안을 만들지
    않는다 — 시각만으로 발화를 추측하거나 파이프라인 STT를 대신 읽는 경로를 막는다.
    """
    draftable, human = [], []
    for r in rows:
        needs_audio = r["query_type"] in AUDIO_REQUIRED_TYPES
        ok = video_supported and (audio_supported or not needs_audio)
        (draftable if ok else human).append(r["query_id"])
    return {"audio_supported": audio_supported,
            "video_supported": video_supported,
            "audio_required_types": list(AUDIO_REQUIRED_TYPES),
            "draftable": draftable, "requires_human_audio": human,
            "n_draftable": len(draftable), "n_requires_human": len(human)}


# ------------------------------------------------------------- 초안 검증

def validate_draft(row: dict, allocation: dict, durations: dict,
                   seg_len: int = 5) -> dict:
    """초안 한 건의 스키마·동결 정합성. 금지 필드가 있으면 거부한다."""
    missing = [f for f in DRAFT_FIELDS if f not in row]
    if missing:
        raise DraftError(f"{row.get('query_id')}: 필드 누락 {missing}")
    extra = [k for k in row if k not in DRAFT_FIELDS + OPTIONAL_FIELDS]
    if extra:
        raise DraftError(f"{row.get('query_id')}: 미허용 필드 {extra}")
    low = {k.lower() for k in row}
    hit = sorted(f for f in FORBIDDEN_FIELDS if f in low)
    if hit:
        raise DraftError(f"{row.get('query_id')}: 금지 필드 {hit} — 모델 산출물을 "
                         "초안에 담지 않는다")
    qid = row["query_id"]
    a = allocation.get(qid)
    if a is None:
        raise DraftError(f"{qid}: 동결 배정에 없다 — 새 질의를 만들 수 없다")
    for key in ("video_id", "query_type"):
        if row[key] != a[key]:
            raise DraftError(f"{qid}: {key}를 바꿀 수 없다 "
                             f"({row[key]!r} != {a[key]!r})")
    if not str(row["draft_text"]).strip():
        raise DraftError(f"{qid}: draft_text가 비어 있다 — 빈 초안은 사람 작성으로 "
                         "보내고 산출물에 넣지 않는다")
    try:
        s, e = float(row["draft_gt_start"]), float(row["draft_gt_end"])
    except (TypeError, ValueError):
        raise DraftError(f"{qid}: 시각이 숫자가 아니다")
    if not 0 <= s < e:
        raise DraftError(f"{qid}: draft_gt_start < draft_gt_end여야 한다 ({s}, {e})")
    dur = durations.get(a["video_id"])
    if dur is None:
        raise DraftError(f"{qid}: {a['video_id']} 길이를 모른다")
    if e > dur:
        raise DraftError(f"{qid}: 영상 길이 {dur:.2f}s를 넘는다 (draft_gt_end {e})")
    if row["prompt_sha256"] != prompt_sha256():
        raise DraftError(f"{qid}: prompt_sha256이 고정 템플릿과 다르다 — 생성 도중 "
                         "프롬프트를 바꾸지 않는다")
    if not str(row["ai_model"]).strip():
        raise DraftError(f"{qid}: ai_model이 비어 있다")
    return row


def validate_all(rows: list, allocation: list = None, durations: dict = None,
                 seg_len: int = 5) -> dict:
    allocation = allocation if allocation is not None \
        else INTAKE.active_allocation()
    by_id = {r["query_id"]: r for r in allocation}
    durations = durations if durations is not None \
        else INTAKE.time_bound_of(seg_len)
    seen = set()
    for r in rows:
        qid = r.get("query_id")
        if qid in seen:
            raise DraftError(f"{qid}: 초안 중복")
        seen.add(qid)
        validate_draft(r, by_id, durations, seg_len)
    models = sorted({r["ai_model"] for r in rows})
    return {"n_drafts": len(rows), "prompt_sha256": prompt_sha256(),
            "ai_models": models, "query_ids": [r["query_id"] for r in rows]}


# ------------------------------------------------------------- 산출물

def write_drafts(rows: list, path=DRAFTS, allocation: list = None,
                 durations: dict = None) -> dict:
    """검증을 통과한 초안만 굳힌다. 이미 있으면 덮지 않는다 — 동결 산출물이다."""
    path = Path(path)
    if path.exists():
        raise DraftError(f"초안 산출물이 이미 있다: {path} — 덮지 않는다. "
                         "재생성은 별도 승인 사건이다")
    meta = validate_all(rows, allocation=allocation, durations=durations)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    tmp.replace(path)
    meta["file"] = str(path)
    meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return meta


def load_drafts(path=DRAFTS) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in
            path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main():
    ap = argparse.ArgumentParser(
        description="P2 AI 초안 준비 — 프롬프트 고정·대상 선정·검증만 한다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt-hash")
    p = sub.add_parser("plan")
    p.add_argument("--audio-supported", action="store_true")
    p.add_argument("--no-video", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("--drafts", default=str(DRAFTS))
    a = ap.parse_args()
    if a.cmd == "prompt-hash":
        print(prompt_sha256())
        return
    if a.cmd == "plan":
        import p2_hybrid_freeze as HF
        rows = pending_rows(HF.completed_ids())
        el = eligibility(rows, audio_supported=a.audio_supported,
                         video_supported=not a.no_video)
        print(json.dumps({"n_pending": len(rows), **{
            k: v for k, v in el.items()
            if k not in ("draftable", "requires_human_audio")}},
            ensure_ascii=False, indent=2))
        return
    print(json.dumps(validate_all(load_drafts(a.drafts)), ensure_ascii=False,
                     indent=2)[:2000])


if __name__ == "__main__":
    main()
