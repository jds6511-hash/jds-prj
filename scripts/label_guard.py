"""라벨 도구용 세그먼트 로더 — **텍스트 필드를 읽는 시점에 버린다.**

CLAUDE.md 절대규칙 3: 라벨 작성 시 검색 결과·캡션을 참조하지 않는다.

기존 도구들은 그 계약을 **관행으로** 지켰다 — `segments.json`을 통째로 읽고
`rep_frame`·`start`·`end`만 썼다. 그러나 같은 파일에 `caption`·`subtitle`이 들어
있어서 강제 장치가 없었다.

**P2에서 그 공백이 실제 위험이 된다.** 신규 31편에는 아직 모델 산출물이 없지만
**기확보 FREE 4편에는 캡션·자막이 이미 존재한다.** 따라서 "산출물이 없어서 오염이
불가능하다"는 말을 35편 전체에 쓸 수 없고, 도구가 차단해야 한다.

허용 필드만 통과시킨다. 새 필드가 생겨도 자동으로 들어오지 않는다(allowlist).
"""
import json
from pathlib import Path

# 프레임·시각만. 라벨러가 봐야 하는 것의 전부다
ALLOWED_SEG_FIELDS = ("idx", "start", "end", "rep_frame")
ALLOWED_TOP_FIELDS = ("video_id", "duration_sec", "fps", "n_segments")
# 통과하면 안 되는 것 — 테스트가 이 목록으로 산출물을 훑는다
FORBIDDEN_FIELDS = ("caption", "subtitle", "text", "score", "rank",
                    "emb", "is_static", "motion_score")


class GuardError(RuntimeError):
    pass


def strip_segments(doc: dict) -> dict:
    """allowlist 밖의 필드를 버린 사본. **원본을 수정하지 않는다.**"""
    out = {k: doc[k] for k in ALLOWED_TOP_FIELDS if k in doc}
    out["segments"] = [{k: s[k] for k in ALLOWED_SEG_FIELDS if k in s}
                       for s in doc.get("segments", [])]
    return out


def load_segments_for_labeling(path) -> dict:
    """`segments.json`을 읽되 **캡션·자막을 메모리에 들이지 않는다.**"""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    stripped = strip_segments(doc)
    del doc
    leaked = [f for f in FORBIDDEN_FIELDS
              if any(f in s for s in stripped["segments"])]
    if leaked:
        raise GuardError(f"allowlist가 새고 있다: {leaked}")
    return stripped
