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


def load_vlm(cfg):
    """Qwen2.5-VL 로딩. 4bit NF4·max_pixels 설정은 기존 caption 실험 검증값 차용."""
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    kwargs = dict(device_map="auto")
    if cfg.get("vlm_4bit"):
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(cfg["caption_model"], **kwargs)
    processor = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor


def caption_frame(image_path, prompt, model, processor, cfg) -> str:
    import torch
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "image", "image": str(image_path)},
        {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    imgs, vids = process_vision_info(messages)
    inputs = processor(text=[text], images=imgs, videos=vids,
                       padding=True, return_tensors="pt").to(model.device)
    gen_kwargs = dict(max_new_tokens=128, do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gen_kwargs["repetition_penalty"] = cfg["vlm_rep_penalty"]
    with torch.inference_mode():
        gen = model.generate(**inputs, **gen_kwargs)
    out = processor.batch_decode(gen[:, inputs.input_ids.shape[1]:],
                                 skip_special_tokens=True)[0]
    return out.strip()


def caption_all(doc, wdir, cfg, captioner) -> list[int]:
    """전 세그먼트 캡션. 실패 시 1회 재시도 후 실패 idx 반환. resume 지원. [4-3]"""
    failed = []
    for seg in doc["segments"]:
        if seg.get("caption"):                        # resume: 이미 있으면 건너뜀
            continue
        img = Path(wdir) / seg["rep_frame"]
        cap_text = ""
        for attempt in range(2):                      # 최초 1회 + 재시도 1회
            try:
                cap_text = captioner(img)
                break
            except Exception as e:
                if attempt == 1:
                    print(f"seg {seg['idx']} 캡션 실패: {type(e).__name__}: {e}")
        if not cap_text:
            failed.append(seg["idx"])
        seg["caption"] = cap_text
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--captions-only", action="store_true",
                    help="Whisper 전사·자막 귀속을 건너뛰고 caption만 재생성 [8-5(3)]")
    args = ap.parse_args()
    if args.force and args.captions_only:
        ap.error("--force와 --captions-only는 동시 지정 불가(force는 전체 재실행)")
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)

    if args.captions_only:
        doc = common.load_segments(wdir / "segments.json")
        # subtitle=""은 무발화 세그먼트의 정상값이므로 키 존재만 검사(값 진위 아님) [8-5(3)]
        # rep_frame은 common.load_segments의 require 경로를 쓰지 않는다 — 그 경로의
        # 일반 에러 메시지가 아니라 seeding 안내가 필요하기 때문 [8-5(3)①]
        missing = [f for f in ("subtitle", "rep_frame")
                  if any(f not in s for s in doc["segments"])]
        if missing:
            raise SystemExit(
                f"--captions-only: segments.json에 {', '.join(missing)}이 채워져 있지 않습니다 — "
                "기준 work 디렉터리의 segments.json·frames/를 복사해 seeding하라 [8-5(3)]")
        for s in doc["segments"]:
            s.pop("caption", None)   # resume이 no-op 되는 것 방지 [8-5(3)]
    else:
        doc = common.load_segments(wdir / "segments.json", require=["rep_frame", "is_static"])
        if args.force:
            for s in doc["segments"]:
                s.pop("subtitle", None); s.pop("caption", None)

        # (a) 자막
        utts = transcribe(wdir / "audio.wav", cfg["stt_model"], cfg["stt_language"],
                          force=args.force)
        assign_subtitles(utts, doc["segments"])
        covered = sum(1 for s in doc["segments"] if s["subtitle"])
        print(f"자막 커버리지: {covered}/{doc['n_segments']} ({covered/doc['n_segments']:.1%})")

    # (b) 캡션
    model, processor = load_vlm(cfg)
    failed = caption_all(doc, wdir, cfg,
                         captioner=lambda p: caption_frame(p, cfg["caption_prompt"],
                                                           model, processor, cfg))
    common.save_segments(wdir / "segments.json", doc)
    if failed:
        print(f"⚠️ 캡션 실패 세그먼트 {len(failed)}개: {failed}")  # 검증 포인트 [4-3]
        sys.exit(1)
    print("M3 완료: caption 빈 문자열 0건")


if __name__ == "__main__":
    main()
