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


def is_corrupted_caption(text: str) -> bool:
    """VLM 캡션 오작동 감지: 한자/가나 과다 혼입, 또는 동일 단어 반복 생성.
    M8 리포트 생성이 오염된 캡션을 근거로 그대로 인용하는 것을 막기 위한 가벼운 필터
    (실제 관찰 사례: 캡션 전체가 중국어로 출력, "계단 위에는..." 문장 반복 생성 등)."""
    if not text:
        return False
    non_korean = len(re.findall(r"[一-鿿぀-ヿ]", text))
    if non_korean / len(text) > 0.2:
        return True
    words = text.split()
    if len(words) >= 6:
        most_common_count = Counter(words).most_common(1)[0][1]
        if most_common_count / len(words) > 0.4:
            return True
    return False
