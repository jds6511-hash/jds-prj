"""공용 유틸: config 로드, 원자적 JSON 저장, segments.json 계약 검증 (DESIGN_SPEC 3-1)."""
import json, os, re
from collections import Counter
from pathlib import Path
import yaml

# 필드 → 그 필드를 채우는 모듈 (fail-fast 에러 메시지용, DESIGN_SPEC 5장)
FIELD_OWNER = {
    "rep_frame": "m2_keyframe.py", "is_static": "m2_keyframe.py",
    "motion_score": "m2_keyframe.py",
    "subtitle": "m3_generate.py", "caption": "m3_generate.py",
}


def load_config(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def work_dir(cfg: dict, video_id: str) -> Path:
    return Path(cfg["paths"]["work"]) / video_id


def atomic_write_json(path, obj) -> None:
    path = str(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_segments(path, require: list[str] | None = None, seg_len: int = 5) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음 — run m1_preprocess.py first")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    segs = doc["segments"]
    if doc["n_segments"] != len(segs):
        raise ValueError(f"n_segments={doc['n_segments']} != len(segments)={len(segs)}")
    for i, s in enumerate(segs):
        if s["idx"] != i:
            raise ValueError(f"segments[{i}].idx={s['idx']} — idx는 0부터 연속 정수여야 함")
        if s["start"] != i * seg_len:
            raise ValueError(f"segments[{i}].start={s['start']} — start = idx*{seg_len} 불변식 위반")
    for field in (require or []):
        missing = [s["idx"] for s in segs if field not in s]
        if missing:
            owner = FIELD_OWNER.get(field, "이전 모듈")
            raise ValueError(
                f"'{field}' 누락 세그먼트 {len(missing)}개 (예: idx {missing[:3]}) — run {owner} first")
    return doc


def save_segments(path, doc) -> None:
    atomic_write_json(path, doc)


_SENT_END = re.compile(r"[。．.!?！？…]")
_CJK_RUN = re.compile(r"[一-鿿぀-ヿ]+")


def truncate_to_sentence(text: str) -> str:
    """8-3(b) 미완결 문장 절단: 마지막 문장 경계(。.!?…)까지만 남긴다.
    경계가 없으면(전체가 조각) 원문 유지 — 신호 소실 방지."""
    matches = list(_SENT_END.finditer(text))
    return text[: matches[-1].end()].rstrip() if matches else text


def strip_residual_cjk(text: str) -> str:
    """8-3(c) 잔여 한자·가나 제거(음차 아님 — 모델 고유 gibberish라 신뢰할 매핑 없음).
    제거 후 생기는 이중 공백만 정리. display_clean과 동일 문자 클래스."""
    return re.sub(r"\s{2,}", " ", _CJK_RUN.sub("", text)).strip()


def postprocess_caption(text: str, cfg: dict) -> tuple[str, str | None]:
    """8-3 캡션 후처리. config 플래그가 켜졌을 때만 적용하며(기본 off = 동작 불변),
    변화가 있으면 원문을 caption_raw로 함께 반환(raw 보존 원칙, M8 raw_output과 일관)."""
    clean = text
    if cfg.get("caption_normalize_cjk"):
        clean = strip_residual_cjk(clean)
    if cfg.get("caption_truncate_incomplete"):
        clean = truncate_to_sentence(clean)
    return (clean, text) if clean != text else (clean, None)


def derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len: int) -> list[int]:
    """1초 이상 겹치는 모든 세그먼트, 없으면 최대 겹침 1개. [DESIGN_SPEC 3-3]

    **중립 모듈에 둔다.** 라벨 도구가 이 함수를 쓰려고 `m6_evaluate`를 import하면
    CLAUDE.md 절대규칙 3의 문언을 위반한다(라벨용 도구는 `m5_search`·`m6_evaluate`를
    import조차 하지 마라). 순수 파생이므로 평가 모듈에 있을 이유가 없다.
    `m6_evaluate`는 이 함수를 재수출한다 — 사본을 만들지 마라(표류한다).
    """
    overlaps = []
    for i in range(n_segments):
        s, e = i * seg_len, (i + 1) * seg_len
        overlaps.append((i, max(0.0, min(e, gt_end) - max(s, gt_start))))
    idx = [i for i, ov in overlaps if ov >= 1.0]
    return idx if idx else [max(overlaps, key=lambda t: t[1])[0]]


# 인용 의무가 없는 문장 역할. **evidence claim이 아닌 필드만** 여기 들어간다 —
# 제목·metadata·명시적 non-evaluable 한계 서술. 모든 문자열에 인용을 강제하는 것이
# 아니라, 평가 대상 factual sentence에만 인용을 의무화하기 위한 예외 목록이다.
# 현행 생성기는 role을 붙이지 않으므로 기존 산출물은 전부 evaluable이다(gwaktube
# report.json 83문장 실측: 인용 없는 문장 0건 — 이 규칙은 소급 효과가 없다).
CITATION_EXEMPT_ROLES = ("title", "metadata", "limitation")


def is_evaluable_sentence(s: dict) -> bool:
    """인용 의무 대상인가. role 미지정은 claim으로 본다(fail-closed 방향)."""
    return str(s.get("role") or "claim").strip().lower() not in CITATION_EXEMPT_ROLES


def uncited_evaluable_sentences(sentences) -> list:
    """인용 없는 evaluable 문장의 sent_id 목록. 비어 있어야 구조 유효다.

    **중립 모듈에 둔다.** `aar_view`(렌더 validator)와 `m9_report_eval`(평가)이 같은
    판정을 써야 한다 — 2026-08-26까지 두 곳의 기준이 달랐다(aar_view는 거부, M9는
    자동 ungrounded로 점수화). 사본을 만들면 다시 갈라진다.
    근거: docs/finalization/M8_M9_DECISIONS_2026-08-26.md §D4
    """
    return [s.get("sent_id") for s in sentences
            if is_evaluable_sentence(s) and not (s.get("cites") or [])]


def index_text_hash(doc) -> str:
    """임베딩 입력 텍스트(subtitle·caption)의 내용 해시. M4가 meta.json에 기록하고
    스킵 판정·M5 로드에서 대조 — 재캡셔닝 후 --force 누락 시 낡은 임베딩이 무증상으로
    유지되는 함정 차단 [리뷰 2026-07-11 Major]."""
    import hashlib
    h = hashlib.sha256()
    for s in doc["segments"]:
        h.update((s.get("subtitle", "") + "\x1f" + s.get("caption", "") + "\x1e")
                 .encode("utf-8"))
    return h.hexdigest()


def is_corrupted_caption(text: str) -> bool:
    """VLM 캡션 오작동 감지: 한자/가나 혼입, 또는 반복 생성.
    M8 리포트 생성이 오염된 캡션을 근거로 그대로 인용하는 것을 막기 위한 가벼운 필터
    (실제 관찰 사례: 캡션 전체가 중국어로 출력, 부분 혼입 "카모フラ주제…나무가满了",
    "계단 위에는..." 문장 반복 생성 등). 2026-07-11 보강: 부분 혼입(절대 개수)과
    3어절 이상 구(句) 연속 반복은 비율 기준만으로는 못 잡는 것이 리뷰에서 실증됨."""
    if not text:
        return False
    non_korean = len(re.findall(r"[一-鿿぀-ヿ]", text))
    if non_korean >= 3 or non_korean / len(text) > 0.2:
        return True
    if re.search(r"(.{3,20}?)\1{2,}", text):      # 동일 구 3회 이상 연속 반복
        return True
    words = text.split()
    if len(words) >= 6:
        most_common_count = Counter(words).most_common(1)[0][1]
        if most_common_count / len(words) > 0.4:
            return True
    return False


_CREDIT_PATTERNS = [
    r"한글\s*자막\s*(by|바이|제공|제작)\s*[:：]?\s*.{0,20}",
    r"자막\s*(제공|제작|by)\s*[:：]?\s*.{0,20}",
    r".{0,30}amara\.org.{0,40}",
]


def is_subtitle_credit(text: str) -> bool:
    """STT가 무발화 구간에 생성하는 **자막 크레딧 환각** 감지.

    실측: 본 인덱스 적발분이 전부 `한글자막 by <이름>` 형태다 — 발화 3건
    (jissi_farm 2, softyeon_ceramics 1)이 오버랩 귀속으로 세그먼트 5개에 걸쳐 있었다.
    Phase 2 회의 오디오에서도 현행 설정으로 재현됐다.

    **전체 일치로만 판정한다.** 크레딧 어구가 문장 안에 섞여 있으면 실제 발화이기
    때문이다("이 영상은 한글자막 by … 님이 달아주신 걸로"). 같은 이유로 `구독`·
    `좋아요`·`시청해주셔서 감사합니다`는 넣지 않았다 — 크리에이터가 실제로 말하는
    문구라 오탐이 곧 발화 삭제다(본 인덱스에 실제 사례 존재).

    is_corrupted_caption(VLM 캡션 품질)·is_suspicious_instruction(주입 안전)과는
    관심사가 달라 분리한다. 이건 STT 산출물 결함이다.
    """
    t = (text or "").strip()
    if not t:
        return False
    return any(re.fullmatch(p, t, re.IGNORECASE) for p in _CREDIT_PATTERNS)


_INJECTION_PATTERNS = [
    r"이전\s*지시", r"위\s*지시", r"다음\s*지시를?\s*따라", r"지시를\s*따라",
    r"무시하고", r"무시해", r"위\s*규칙을?\s*무시",
    r"시스템\s*프롬프트", r"system\s*prompt",
    r"ignore\s*(previous|above|all)\s*instructions?",
    r"너는\s*이제", r"당신은\s*이제",
]


def is_suspicious_instruction(text: str) -> bool:
    """세그먼트 텍스트(자막·캡션)에 리포트 생성 LLM을 겨냥한 지시문 패턴이 있는지
    휴리스틱 탐지 — 콘텐츠 내 프롬프트 주입 완화용(차단 보장 아님, DESIGN_SPEC 4-8).
    is_corrupted_caption과 별개 관심사(품질 vs 안전)라 분리한다."""
    if not text:
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in _INJECTION_PATTERNS)


def env_provenance() -> dict:
    """실행 환경 캡처 — 어떤 코드·라이브러리·하드웨어에서 나온 산출물인지.

    **왜 필요한가.** 2026-08-17에 4B 생성물 세 판이 왜 달랐는지 추적하다가, 당시
    라이브러리 버전·attention backend가 어디에도 없어 코드 경로 차이까지만 좁히고
    멈췄다. m3_generate.caption_provenance가 같은 항목을 캡션 쪽에서 남긴다 —
    M8/M9도 같은 정보가 필요해 공용으로 뺀다.
    """
    import platform, subprocess, datetime

    def _git(*a) -> str:
        try:
            return subprocess.run(["git", *a], cwd=Path(__file__).resolve().parents[1],
                                  capture_output=True, encoding="utf-8",
                                  errors="replace").stdout.strip()
        except Exception:
            return ""

    env = {"git_head": _git("rev-parse", "HEAD"),
           "git_dirty": bool(_git("status", "--porcelain")),
           "python": platform.python_version(),
           "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        import torch
        env["torch"] = torch.__version__
        env["cuda"] = torch.version.cuda
        env["gpu"] = (torch.cuda.get_device_name(0)
                      if torch.cuda.is_available() else None)
    except Exception:
        env["torch"] = env["cuda"] = env["gpu"] = None
    try:
        import transformers
        env["transformers"] = transformers.__version__
    except Exception:
        env["transformers"] = None
    return env
