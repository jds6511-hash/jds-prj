"""M3 자막·캡션 생성. 자막: faster-whisper(archive/초기탐색/stt_test/stt_local.py 검증 설정 차용),
캡션: Qwen2.5-VL(caption/qwen_caption_test 검증 설정 차용). [DESIGN_SPEC 4-3]"""
import argparse, json, os, re, sys
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


def _git(*args) -> str:
    import subprocess
    try:
        return subprocess.run(["git", *args], cwd=Path(__file__).resolve().parents[1],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def frame_manifest_hash(doc: dict, wdir) -> str | None:
    """캡션 입력 프레임 전체의 내용 해시. 하나라도 없으면 None.

    "같은 입력이었나"를 사후에 확인할 유일한 수단이다 — 2026-08-17에 세 번의
    생성물 차이를 추적할 때 프레임 동일성을 대조할 방법이 없었다. 못 냈으면
    **None으로 남긴다**(거짓 해시로 덮지 않는다)."""
    import hashlib
    h = hashlib.sha256()
    for s in doc["segments"]:
        p = Path(wdir) / s.get("rep_frame", "")
        if not p.is_file():
            return None
        h.update(p.read_bytes())
        h.update(b"\x1e")
    return h.hexdigest()


def caption_provenance(cfg: dict, model, prompt: str, entrypoint: str) -> dict:
    """캡션 생성 조건 기록. **요청값이 아니라 실효값을 남긴다.**

    2026-08-17에 08-10·08-14·08-17 세 번의 4B 생성물이 왜 달랐는지 추적하다,
    당시 라이브러리 버전·attention backend가 어디에도 없어 **코드 경로 차이까지만
    좁히고 멈췄다.** config를 남기는 것으로는 부족하다 — `vlm_4bit` 플래그가 무시된
    채 돌았던 전례가 있어, "적혀 있던 값"과 "실제 로드된 값"을 **둘 다** 남긴다.
    불일치 자체가 신호다."""
    import hashlib, platform
    conf = getattr(model, "config", None)
    quant = getattr(conf, "quantization_config", None)
    head = _git("rev-parse", "HEAD")

    prov = {
        "entrypoint": entrypoint,             # m3_generate / caption_model_sweep / …
        "model_id": getattr(conf, "_name_or_path", None),
        "model_revision": getattr(conf, "_commit_hash", None),
        "dtype": str(getattr(model, "dtype", None)),
        "quantized": quant is not None,
        "attn_implementation": getattr(conf, "_attn_implementation", None),
        "prompt_sha256": hashlib.sha256((prompt or "").encode("utf-8")).hexdigest(),
        "git_head": head,
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    # 요청값 — 실효값과 갈리면 그 자체가 사고다
    for k in ("caption_model", "vlm_4bit", "vlm_max_pixels", "vlm_max_new_tokens",
              "vlm_rep_penalty"):
        if k in cfg:
            prov[f"config_{k}"] = cfg[k]

    # **요청 정밀도와 실효 양자화를 별도 축으로 둔다** (2026-08-18). `dtype` 하나로
    # q4를 판정하면 안 된다 — 4bit 모델도 계산 dtype과 일부 비양자화 tensor는
    # bf16이다. 정밀도가 주 판정인 실험에서 arm 정체성을 증명할 근거다.
    def _q(name, default=None):
        if quant is None:
            return default
        if isinstance(quant, dict):
            return quant.get(name, default)
        return getattr(quant, name, default)

    prov["requested_quantized"] = bool(cfg.get("vlm_4bit"))
    prov["effective_quantized"] = quant is not None
    prov["quantization_mismatch"] = (
        prov["requested_quantized"] != prov["effective_quantized"])
    prov["bnb_quant_type"] = _q("bnb_4bit_quant_type")
    cd = _q("bnb_4bit_compute_dtype")
    prov["bnb_compute_dtype"] = None if cd is None else str(cd)
    prov["bnb_double_quant"] = _q("bnb_4bit_use_double_quant")

    try:
        import torch
        prov["torch"] = torch.__version__
        prov["cuda"] = torch.version.cuda
        prov["gpu"] = (torch.cuda.get_device_name(0)
                       if torch.cuda.is_available() else None)
    except Exception:
        prov["torch"] = prov["cuda"] = prov["gpu"] = None
    try:
        import transformers
        prov["transformers"] = transformers.__version__
    except Exception:
        prov["transformers"] = None
    return prov


def attach_provenance(doc: dict, prov: dict) -> None:
    """doc 최상위에 붙인다. `index_text_hash`는 segments의 텍스트만 보므로
    이 필드가 재임베딩을 유발하지 않는다."""
    doc["caption_provenance"] = prov


DEFAULT_BEAM_SIZE = 5     # faster-whisper 기본값. 확정 인덱스가 이 값으로 만들어졌다.


def transcribe(wav: Path, model_name: str = "large-v3", lang: str = "ko",
               force: bool = False, beam_size: int = DEFAULT_BEAM_SIZE) -> list[dict]:
    """utterance = {text, t0, t1} 리스트. 캐시: audio.wav 옆 stt_cache.json.

    `beam_size`는 **캐시 키에 포함**한다. 없으면 빔만 바꿔도 캐시가 적중해 옛 전사를
    조용히 돌려주고, 그걸 "차이 없음"으로 읽게 된다(2026-08-08 실패 테스트로 적발).
    구 캐시에는 이 키가 없으므로 기본값을 채워 비교한다 — 안 그러면 확정 인덱스
    11편이 전부 재전사되고, 환경이 다르면 자막이 달라질 수 있다.
    """
    cache = wav.parent / "stt_cache.json"
    meta = {"model": model_name, "lang": lang,
            "mtime": os.path.getmtime(wav), "size": os.path.getsize(wav),
            "beam_size": beam_size}
    if not force and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        stored = {"beam_size": DEFAULT_BEAM_SIZE, **d.get("meta", {})}
        if stored == meta:
            print(f"캐시된 전사 사용: {cache}")
            return d["utterances"]

    from faster_whisper import WhisperModel

    def run(device, compute):
        model = WhisperModel(model_name, device=device, compute_type=compute)
        # 한국어 환각 방지 2중 장치 + VAD 금지 [stt_local.py에서 검증됨]
        raw, _ = model.transcribe(
            str(wav), language=lang, word_timestamps=True,
            condition_on_previous_text=False,
            hallucination_silence_threshold=1.0,
            beam_size=beam_size, best_of=beam_size)
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
        # 자막 크레딧 환각은 세그먼트에 들이지 않는다. stt_cache.json에는 원본이
        # 남으므로 필터를 되돌리면 복원된다(재전사 불필요).
        if common.is_subtitle_credit(u["text"]):
            continue
        for s in segments:
            if min(u["t1"], s["end"]) - max(u["t0"], s["start"]) > 0:
                parts[s["idx"]].append(u["text"])
    for s in segments:
        s["subtitle"] = " ".join(parts[s["idx"]])


def vlm_class_name(model_id: str) -> str:
    """model id로 transformers 클래스를 고른다.

    Qwen2.5-VL과 Qwen3-VL은 클래스가 다르다. 예전에는 2.5 계열만 써서 클래스를
    하드코딩했는데, 그 상태로 config만 Qwen3-VL로 바꾸면 적재에서 죽는다.
    """
    if "Qwen3-VL" in model_id:
        # MoE(30B-A3B 등)는 별도 클래스다. 부분일치로 뭉뚱그리면 조용히 틀린 클래스를
        # 집어 적재가 깨진다 [2026-08-14 큰 모델 확인 결정].
        if re.search(r"-A\d+B", model_id):
            return "Qwen3VLMoeForConditionalGeneration"
        return "Qwen3VLForConditionalGeneration"
    if "Qwen2.5-VL" in model_id:
        return "Qwen2_5_VLForConditionalGeneration"
    raise ValueError(f"지원하지 않는 VLM 계열: {model_id}")


def load_vlm(cfg):
    """Qwen2.5-VL / Qwen3-VL 로딩. 4bit NF4·max_pixels는 기존 caption 실험 검증값."""
    import torch
    import transformers
    from transformers import AutoProcessor
    kwargs = dict(device_map="auto")
    if cfg.get("vlm_4bit"):
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    cls = getattr(transformers, vlm_class_name(cfg["caption_model"]))
    model = cls.from_pretrained(cfg["caption_model"], **kwargs)
    processor = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor


def caption_frame(image_path, prompt, model, processor, cfg, sample: bool = False) -> str:
    import torch
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "image", "image": str(image_path)},
        {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    imgs, vids = process_vision_info(messages)
    inputs = processor(text=[text], images=imgs, videos=vids,
                       padding=True, return_tensors="pt").to(model.device)
    gen_kwargs = dict(max_new_tokens=cfg.get("vlm_max_new_tokens", 128), do_sample=False)
    if sample:
        # 오염 캡션 재시도용 — greedy는 결정적이라 같은 오염 출력을 재현하므로
        # 샘플링으로만 다른 출력을 얻을 수 있다 [8-5(4)]
        gen_kwargs.update(do_sample=True, temperature=0.7, top_p=0.9)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gen_kwargs["repetition_penalty"] = cfg["vlm_rep_penalty"]
    with torch.inference_mode():
        gen = model.generate(**inputs, **gen_kwargs)
    out = processor.batch_decode(gen[:, inputs.input_ids.shape[1]:],
                                 skip_special_tokens=True)[0]
    return out.strip()


def caption_all(doc, wdir, cfg, captioner, checkpoint_every: int = 20) -> list[int]:
    """전 세그먼트 캡션. 실패 시 1회 재시도 후 실패 idx 반환. resume 지원.
    checkpoint_every개마다 중간 저장 — GPU 크래시(OOM 등) 시 이미 완료한 캡션 보존. [4-3]"""
    failed = []
    since_checkpoint = 0
    n_ok = 0
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
        if cap_text and common.is_corrupted_caption(cap_text):
            for _ in range(2):                        # 오염 감지 → 샘플링 재시도 [8-5(4)]
                try:
                    retry = captioner(img, sample=True)
                except Exception as e:
                    print(f"seg {seg['idx']} 샘플링 재시도 실패: {type(e).__name__}: {e}")
                    break
                if retry and not common.is_corrupted_caption(retry):
                    cap_text = retry
                    break
        if not cap_text:
            failed.append(seg["idx"])
        else:
            n_ok += 1
        # 8-3(b)(c) 후처리 — config 플래그 켜졌을 때만(기본 off = 동작 불변)
        clean, raw = common.postprocess_caption(cap_text, cfg)
        seg["caption"] = clean
        if raw is not None:
            seg["caption_raw"] = raw
        since_checkpoint += 1
        # 성공이 하나도 없으면 체크포인트를 찍지 않는다. 체크포인트의 목적은 완료한
        # 캡션 보존인데, 전건 실패 상태에서 저장하면 기존 산출물을 빈 문자열로 덮는다
        # (2026-08-13 서버 배치 사고: 프레임 부재로 1,525건 전부 실패 → 7편 소실).
        if since_checkpoint >= checkpoint_every and n_ok > 0:
            common.save_segments(Path(wdir) / "segments.json", doc)
            since_checkpoint = 0
    return failed


def assert_rep_frames_exist(doc, wdir) -> None:
    """캡션이 필요한 세그먼트의 rep_frame 이미지가 실제로 있는지 확인한다.

    segments.json의 `rep_frame` **필드**만 검사하던 것으로는 부족하다 — 다른 기계로
    segments.json만 옮기면 필드는 있고 이미지는 없다. 2026-08-13 서버 배치가 정확히
    이 상태에서 1,525건을 전부 실패시켰다. VLM 적재 전에 멈춘다.
    """
    missing = [s["idx"] for s in doc["segments"]
               if not (s.get("caption") or "").strip()
               and not (Path(wdir) / s["rep_frame"]).exists()]
    if missing:
        head = ", ".join(str(i) for i in missing[:5])
        raise SystemExit(
            f"프레임 이미지 {len(missing)}개가 없습니다 (예: seg {head}) — "
            f"{Path(wdir) / 'frames'}에 대표 프레임을 복사하거나 m2를 먼저 실행하라. "
            "rep_frame 필드만 있고 이미지가 없으면 캡션이 전부 빈 문자열이 된다 [8-5(3)]")


def clear_corrupted_captions(doc) -> list[int]:
    """오염 캡션(is_corrupted_caption)만 비워 caption_all의 resume 대상으로 만든다.
    반환: 비운 세그먼트 idx 목록. [8-5(4)]"""
    targets = {s["idx"] for s in doc["segments"]
               if common.is_corrupted_caption(s.get("caption") or "")}
    for s in doc["segments"]:
        if s["idx"] in targets:
            s["caption"] = ""
    return sorted(targets)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--captions-only", action="store_true",
                    help="Whisper 전사·자막 귀속을 건너뛰고 caption만 재생성 [8-5(3)]")
    ap.add_argument("--recaption-corrupted", action="store_true",
                    help="오염 감지(is_corrupted_caption)된 캡션만 재생성 [8-5(4)]")
    ap.add_argument("--subtitles-only", action="store_true",
                    help="캡션을 그대로 두고 자막만 재생성 — STT 설정 비교용 [8-5(7)]")
    args = ap.parse_args()
    if args.force and args.captions_only:
        ap.error("--force와 --captions-only는 동시 지정 불가(force는 전체 재실행)")
    if args.recaption_corrupted and (args.force or args.captions_only):
        ap.error("--recaption-corrupted는 --force/--captions-only와 동시 지정 불가")
    if args.subtitles_only and (args.force or args.captions_only or args.recaption_corrupted):
        ap.error("--subtitles-only는 다른 모드와 동시 지정 불가")
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)

    if args.captions_only:
        doc = common.load_segments(wdir / "segments.json", seg_len=cfg["seg_len_sec"])
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
    elif args.subtitles_only:
        # --captions-only의 반대 방향. 캡션 재생성은 환경이 바뀌면 인덱스를 열화시키므로
        # (2026-08-07 실측: 같은 설정·다른 GPU에서 완전일치 25.6%), STT 설정을 비교할 때
        # 캡션은 손대지 않는다. 캡션이 비어 있으면 캡션 없는 인덱스가 만들어지므로 먼저 막는다.
        doc = common.load_segments(wdir / "segments.json", seg_len=cfg["seg_len_sec"])
        if any(not (s.get("caption") or "").strip() for s in doc["segments"]):
            raise SystemExit(
                "--subtitles-only: segments.json에 caption이 비어 있습니다 — "
                "이 모드는 기존 캡션을 보존만 하고 만들지 않는다 [8-5(7)]")
        utts = transcribe(wdir / "audio.wav", cfg["stt_model"], cfg["stt_language"],
                          beam_size=cfg.get("stt_beam_size", DEFAULT_BEAM_SIZE))
        assign_subtitles(utts, doc["segments"])
        covered = sum(1 for s in doc["segments"] if s["subtitle"])
        print(f"자막 커버리지: {covered}/{doc['n_segments']} ({covered/doc['n_segments']:.1%})")
        common.save_segments(wdir / "segments.json", doc)
        print(f"M3 완료(자막만): {wdir / 'segments.json'}")
        return
    elif args.recaption_corrupted:
        doc = common.load_segments(wdir / "segments.json", require=["rep_frame"],
                                   seg_len=cfg["seg_len_sec"])
        targets = clear_corrupted_captions(doc)
        if not targets:
            print("오염 캡션 0건 — 재생성 불필요")
            return
        print(f"오염 캡션 {len(targets)}건 재생성 대상: {targets}")
    else:
        doc = common.load_segments(wdir / "segments.json", require=["rep_frame", "is_static"],
                                   seg_len=cfg["seg_len_sec"])
        if args.force:
            for s in doc["segments"]:
                s.pop("subtitle", None); s.pop("caption", None)

        # (a) 자막
        utts = transcribe(wdir / "audio.wav", cfg["stt_model"], cfg["stt_language"],
                          force=args.force,
                          beam_size=cfg.get("stt_beam_size", DEFAULT_BEAM_SIZE))
        assign_subtitles(utts, doc["segments"])
        covered = sum(1 for s in doc["segments"] if s["subtitle"])
        print(f"자막 커버리지: {covered}/{doc['n_segments']} ({covered/doc['n_segments']:.1%})")

    # (b) 캡션
    assert_rep_frames_exist(doc, wdir)          # VLM 적재 전에 막는다
    n_target = sum(1 for s in doc["segments"] if not (s.get("caption") or "").strip())
    model, processor = load_vlm(cfg)
    failed = caption_all(doc, wdir, cfg,
                         captioner=lambda p, sample=False: caption_frame(
                             p, cfg["caption_prompt"], model, processor, cfg, sample=sample))
    if n_target and len(failed) == n_target:
        # 전건 실패 — 저장하면 기존 캡션이 빈 문자열로 덮인다. 저장하지 않고 죽는다.
        sys.exit(f"캡션 {n_target}건이 전부 실패했습니다 — segments.json을 저장하지 "
                 f"않고 중단합니다. 원인을 해결한 뒤 다시 실행하라 (기존 캡션 보존).")
    if n_target:                                 # 실제로 생성한 경우에만 갱신
        prov = caption_provenance(cfg, model, prompt=cfg["caption_prompt"],
                                  entrypoint="m3_generate")
        prov["frame_manifest_sha256"] = frame_manifest_hash(doc, wdir)
        attach_provenance(doc, prov)
    common.save_segments(wdir / "segments.json", doc)
    if failed:
        print(f"⚠️ 캡션 실패 세그먼트 {len(failed)}개: {failed}")  # 검증 포인트 [4-3]
        sys.exit(1)
    print("M3 완료: caption 빈 문자열 0건")


if __name__ == "__main__":
    main()
