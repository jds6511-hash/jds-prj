"""M3 자막·캡션 생성. 자막: faster-whisper(stt_test/stt_local.py 검증 설정 차용),
캡션: Qwen2.5-VL(caption/qwen_caption_test 검증 설정 차용). [DESIGN_SPEC 4-3]"""
import argparse, json, os, sys
from pathlib import Path
import common

# Windows 콘솔(cp949) 크래시 방지 [stt_local.py 차용]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# Windows: ctranslate2용 cuBLAS(CUDA 12) DLL 주입. cudnn은 절대 추가 금지 [stt_local.py 차용]
if os.name == "nt":
    import site
    for _base in (site.getusersitepackages(), *site.getsitepackages()):
        _dir = os.path.join(_base, "nvidia", "cublas", "bin")
        if os.path.isdir(_dir):
            os.add_dll_directory(_dir)
            break


def transcribe(wav: Path, model_name: str = "large-v3", lang: str = "ko",
               force: bool = False) -> list[dict]:
    """utterance = {text, t0, t1} 리스트. 캐시: audio.wav 옆 stt_cache.json."""
    cache = wav.parent / "stt_cache.json"
    meta = {"model": model_name, "lang": lang,
            "mtime": os.path.getmtime(wav), "size": os.path.getsize(wav)}
    if not force and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("meta") == meta:
            print(f"캐시된 전사 사용: {cache}")
            return d["utterances"]

    from faster_whisper import WhisperModel

    def run(device, compute):
        model = WhisperModel(model_name, device=device, compute_type=compute)
        # 한국어 환각 방지 2중 장치 + VAD 금지 [stt_local.py에서 검증됨]
        raw, _ = model.transcribe(
            str(wav), language=lang, word_timestamps=True,
            condition_on_previous_text=False,
            hallucination_silence_threshold=1.0)
        return [{"text": s.text.strip(), "t0": float(s.start), "t1": float(s.end)}
                for s in raw if s.text.strip()]

    # GPU 폴백 사다리 [stt_local.py 차용]
    ladder = [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    utts = None
    for device, compute in ladder:
        try:
            print(f"faster-whisper {model_name} ({device}/{compute}) 전사 중...")
            utts = run(device, compute)
            break
        except Exception as e:
            if (device, compute) == ladder[-1]:
                raise
            print(f"  {device}/{compute} 불가({type(e).__name__}) → 폴백")

    common.atomic_write_json(cache, {"meta": meta, "utterances": utts})
    return utts


def assign_subtitles(utts: list[dict], segments: list[dict]) -> None:
    """오버랩 귀속: 발화가 겹치는 모든 세그먼트에 포함(경계 문장 양쪽 중복 허용).
    최대 겹침 세그먼트가 자동 포함되므로 '더 많이 걸친 쪽 귀속'을 상회 충족. [3-2]"""
    parts = {s["idx"]: [] for s in segments}
    for u in utts:
        for s in segments:
            if min(u["t1"], s["end"]) - max(u["t0"], s["start"]) > 0:
                parts[s["idx"]].append(u["text"])
    for s in segments:
        s["subtitle"] = " ".join(parts[s["idx"]])
