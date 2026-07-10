import json
import common
from m3_generate import caption_all, clear_corrupted_captions

def _doc(n=3):
    segs = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "rep_frame": f"frames/seg_{i:04d}.jpg", "is_static": False,
             "subtitle": ""} for i in range(n)]
    return {"video_id": "v", "duration_sec": n * 5.0, "fps": 30.0,
            "n_segments": n, "segments": segs}

def test_caption_all_fills_every_segment(tmp_path):
    doc = _doc()
    failed = caption_all(doc, tmp_path, {}, captioner=lambda p: "캡션")
    assert failed == []
    assert all(s["caption"] == "캡션" for s in doc["segments"])

def test_caption_retry_once_then_report_failure(tmp_path):
    doc = _doc(2)
    calls = []
    def flaky(p):
        calls.append(p)
        if "0000" in str(p):
            raise RuntimeError("VLM 실패")
        return "ok"
    failed = caption_all(doc, tmp_path, {}, captioner=flaky)
    assert failed == [0]                              # 재시도 1회 후 실패 목록 [4-3]
    assert str(calls).count("0000") == 2              # 정확히 2회 시도
    assert doc["segments"][0]["caption"] == ""        # 실패 시 빈 문자열 기록
    assert doc["segments"][1]["caption"] == "ok"

def test_caption_resume_skips_existing(tmp_path):
    doc = _doc(2)
    doc["segments"][0]["caption"] = "기존"
    called = []
    caption_all(doc, tmp_path, {}, captioner=lambda p: (called.append(p) or "새로"))
    assert doc["segments"][0]["caption"] == "기존" and len(called) == 1

def test_static_segment_still_captioned(tmp_path):
    doc = _doc(1); doc["segments"][0]["is_static"] = True
    caption_all(doc, tmp_path, {}, captioner=lambda p: "정적 캡션")
    assert doc["segments"][0]["caption"] == "정적 캡션"   # 캡션 버리기 금지 [v2 8-4]

CORRUPTED = "夜晚人群聚集在户外庆祝新年天空中绽放着绚烂的烟花"   # 실관찰 사례: 전문 중국어 출력


def test_caption_corrupted_retried_with_sampling(tmp_path):
    # [8-5(4)] greedy 출력이 오염이면 샘플링 재시도로 교체. greedy는 결정적이라
    # sample=True 없이는 같은 오염 출력만 재현된다.
    doc = _doc(1)
    calls = []
    def captioner(p, sample=False):
        calls.append(sample)
        return "정상 한국어 캡션" if sample else CORRUPTED
    failed = caption_all(doc, tmp_path, {}, captioner=captioner)
    assert failed == []
    assert doc["segments"][0]["caption"] == "정상 한국어 캡션"
    assert calls == [False, True]                     # greedy 1회 + 샘플링 1회


def test_caption_corrupted_kept_if_retries_also_corrupted(tmp_path):
    # 샘플링 2회도 오염이면 greedy 출력 유지(빈 값 아님) — M8/M9 필터가 후처리 담당
    doc = _doc(1)
    calls = []
    def captioner(p, sample=False):
        calls.append(sample)
        return CORRUPTED
    failed = caption_all(doc, tmp_path, {}, captioner=captioner)
    assert failed == []                               # 오염≠실패(빈 문자열 아님)
    assert doc["segments"][0]["caption"] == CORRUPTED
    assert calls == [False, True, True]               # 샘플링 재시도 2회 상한


def test_clear_corrupted_captions_targets_only_corrupted():
    doc = _doc(3)
    doc["segments"][0]["caption"] = "정상적인 한국어 캡션입니다"
    doc["segments"][1]["caption"] = CORRUPTED
    doc["segments"][2]["caption"] = "반복 반복 반복 반복 반복 반복 반복 반복"
    targets = clear_corrupted_captions(doc)
    assert targets == [1, 2]
    assert doc["segments"][0]["caption"] == "정상적인 한국어 캡션입니다"
    assert doc["segments"][1]["caption"] == "" and doc["segments"][2]["caption"] == ""


def test_caption_all_checkpoints_progress_for_crash_recovery(tmp_path):
    # GPU 크래시 시 이미 완료한 캡션이 사라지지 않도록 N개마다 중간 저장 [보완: resume 무력화]
    doc = _doc(5)
    seg_path = tmp_path / "segments.json"
    common.save_segments(seg_path, doc)
    seen_at_checkpoint = []

    def captioner(p):
        # 체크포인트 시점(2개 처리 후)에 파일이 이미 갱신됐는지 기록
        saved = json.loads(seg_path.read_text(encoding="utf-8"))
        seen_at_checkpoint.append(sum(1 for s in saved["segments"] if s.get("caption")))
        return "캡션"

    caption_all(doc, tmp_path, {}, captioner=captioner, checkpoint_every=2)
    # 3번째 세그먼트 처리 시점에는 앞선 2개가 이미 디스크에 저장돼 있어야 함
    assert seen_at_checkpoint[2] == 2
    final = json.loads(seg_path.read_text(encoding="utf-8"))
    assert sum(1 for s in final["segments"] if s.get("caption")) >= 4  # 마지막 미만은 다음 체크포인트 전
