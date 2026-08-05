"""[STT 후보 3종 성능 비교 — 공개 벤치마크 WER/CER]
회의록·화자별 요약 기능 요구(2026-07-31 회의)에 따른 STT 교체 검토. 채택 아님.

arm:
  A(현행)  faster-whisper large-v3
  B(한국어) ghost613/faster-whisper-large-v3-turbo-korean   (CTranslate2, 같은 코드 경로)
  C(신모델) Qwen/Qwen3-ASR-1.7B-hf                          (transformers>=5.13, 별도 venv)

데이터셋(--dataset):
  fleurs  google/fleurs:ko_kr test (382발화) — **주 벤치마크**
  zeroth  kresnik/zeroth_korean test        — 참고용. arm B가 이 데이터로 파인튜닝됐고
          자체 val/test를 원본 test 50/50 분할로 만들었다고 모델카드에 명시돼 있어
          **arm B에 대해 학습·평가 누수**다. 공정 비교 불가, 누수 사례 기록용으로만 둔다.

지표: 표기 관습이 점수를 왜곡하므로 두 가지를 병기한다.
  cer_raw      구두점 제거만. 데이터셋의 숫자 표기 관습에 종속(Zeroth=한글 수사,
               FLEURS=아라비아 숫자)이라 어느 쪽이든 한 모델에 유리해진다.
  cer_numfree  숫자 표기를 양쪽에서 제거한 **표기 중립** 지표. 모델 자체의 인식
               성능 비교가 목적이므로 이쪽을 주지표로 읽는다(사용자 결정 2026-08-04).
               토큰 단위로만 지운다 — 음절 단위로 지우면 '사람'→'람', '이용자'→'용자'
               처럼 일반 단어가 깨진다.
CI: 발화 단위 쌍체 부트스트랩 95% CI (DESIGN_SPEC 8-1(b)와 동일 방식).

실행:
  python3  docs/probes/stt_bench.py --arm A --dataset fleurs
  python3  docs/probes/stt_bench.py --arm B --dataset fleurs
  ./.venv_qwen3asr/Scripts/python.exe docs/probes/stt_bench.py --arm C --dataset fleurs
  python3  docs/probes/stt_bench.py --compare --dataset fleurs
"""
import argparse, json, os, re, time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
N_SAMPLE = 200

MODELS = {
    "A": ("faster-whisper", "large-v3"),
    "B": ("faster-whisper", "ghost613/faster-whisper-large-v3-turbo-korean"),
    # 비-hf 저장소는 Qwen 자체 툴킷용 — transformers로 로드하면
    # multi_modal_projector 가중치가 랜덤 초기화된다(실측 경고 확인). -hf가 정본.
    "C": ("qwen3-asr", "Qwen/Qwen3-ASR-1.7B-hf"),
}
DATASETS = {
    "fleurs": ("google/fleurs", "ko_kr", "test", "transcription"),
    "zeroth": ("kresnik/zeroth_korean", None, "test", "text"),
}

if os.name == "nt":                      # ctranslate2용 cuBLAS DLL [m3_generate.py 규약]
    import site
    for _b in (site.getusersitepackages(), *site.getsitepackages()):
        _d = os.path.join(_b, "nvidia", "cublas", "bin")
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            break

_NUM_SYL = "영공일이삼사오육칠팔구십백천만억조쩜점"
_NUM_WORD = ("하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열|스물|서른|마흔|쉰|예순|일흔|여든|아흔")


def norm_basic(t: str) -> str:
    """구두점·특수기호 제거 + 공백 단일화. 모든 arm에 동일 적용."""
    t = re.sub(r"[^가-힣ᄀ-ᇿ0-9a-zA-Z ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_numfree(t: str) -> str:
    """표기 중립화: 숫자를 나타내는 **토큰 전체**만 제거.

    규칙은 두 개뿐이다.
    - 아라비아 숫자 런 제거 (1,200 / 15 / 2011)
    - 공백 구분 토큰이 전부 수사 음절이면 그 토큰 제거 (천 / 이백 / 오 / 쩜)

    토큰 앞부분만 벗기는 규칙은 쓰지 않는다 — 넣어봤더니 '사람들이'→'람들이',
    '공사는'→'는', '이야기를'→'야기를'처럼 일반 단어가 대량으로 깨졌다(실측).

    한계(정직): 단위가 붙은 토큰은 남으므로 표기 차이가 완전히 사라지지는 않는다
    (한글 '천 이백 억원'→'억원' vs 아라비아 '1,200억 원'→'원'). 잔차는 양방향으로
    작용하고 cer_raw를 함께 보고하므로 해석 가능한 범위로 둔다.
    """
    t = norm_basic(t)
    t = re.sub(r"\d+", " ", t)
    keep = [tok for tok in t.split()
            if not re.fullmatch(rf"(?:[{_NUM_SYL}]|{_NUM_WORD})+", tok)]
    return " ".join(keep)


def load_samples(ds_key: str):
    """(audio_array, sr, ref_text, id) 리스트. 고정 시드 표본.

    datasets의 오디오 자동 디코딩은 torchcodec을 쓰는데 Windows에서 DLL 로드가
    실패하므로(libtorchcodec_core*.dll) decode=False + soundfile로 직접 디코딩한다.
    """
    import io
    import numpy as np
    import soundfile as sf
    from datasets import load_dataset, Audio
    repo, cfg, split, textcol = DATASETS[ds_key]
    ds = load_dataset(repo, cfg, split=split) if cfg else load_dataset(repo, split=split)
    ds = ds.cast_column("audio", Audio(decode=False))
    rng = np.random.default_rng(SEED)
    n = min(N_SAMPLE, len(ds))
    idx = sorted(rng.choice(len(ds), size=n, replace=False).tolist())
    out = []
    for i in idx:
        row = ds[i]
        a = row["audio"]
        raw = a["bytes"] if a.get("bytes") else Path(a["path"]).read_bytes()
        arr, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        if sr != 16000:                                # FLEURS는 이미 16k지만 방어
            import librosa
            arr = librosa.resample(arr, orig_sr=sr, target_sr=16000); sr = 16000
        out.append((arr, sr, row[textcol], str(row["id"])))
    return out


def run_faster_whisper(model_name, samples):
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cuda", compute_type="float16")
    hyps = []
    for arr, _sr, _ref, _id in samples:
        segs, _ = model.transcribe(np.asarray(arr, dtype=np.float32), language="ko",
                                   condition_on_previous_text=False,
                                   hallucination_silence_threshold=1.0)
        hyps.append(" ".join(s.text.strip() for s in segs).strip())
    return hyps


_ASR_PREFIX = re.compile(r"^\s*language\s+\S+\s*<asr_text>\s*", re.I)


def run_qwen3_asr(model_name, samples):
    """세 가지 실측 제약을 반영한 호출 경로.
    ① audio에 파일 경로를 주면 transformers.audio_utils.load_audio가 torchcodec을 타서
       실패 → numpy 배열을 직접 넘긴다(시그니처가 허용).
    ② 인코더가 feature length를 n_window*2(=100프레임)의 배수로 요구 →
       processor_kwargs로 pad_to_multiple_of=100. (**kwargs로 주면 무시된다는 경고 확인)
    ③ 출력에 'language Korean<asr_text>' 접두가 남아 파싱으로 벗긴다.
    """
    import numpy as np, torch
    from transformers import AutoProcessor, AutoModelForMultimodalLM
    proc = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_name, dtype=torch.float16, device_map={"": 0}).eval()
    hyps = []
    for arr, _sr, _ref, _id in samples:
        inputs = proc.apply_transcription_request(
            audio=np.asarray(arr, dtype=np.float32), language="ko",
            processor_kwargs={"pad_to_multiple_of": 100},
        ).to(model.device, model.dtype)
        with torch.inference_mode():
            ids = model.generate(**inputs, max_new_tokens=440)
        txt = proc.batch_decode(ids[:, inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True,
                                return_format="transcription_only")[0]
        hyps.append(_ASR_PREFIX.sub("", txt).replace("<asr_text>", "").strip())
    return hyps


def main_arm(arm: str, ds_key: str):
    kind, name = MODELS[arm]
    samples = load_samples(ds_key)
    print(f"arm {arm} / {name} / {ds_key} / {len(samples)}발화", flush=True)
    t0 = time.time()
    hyps = (run_faster_whisper(name, samples) if kind == "faster-whisper"
            else run_qwen3_asr(name, samples))
    dt = time.time() - t0
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"stt_{ds_key}_arm{arm}.json"
    dest.write_text(json.dumps({
        "arm": arm, "model": name, "kind": kind, "dataset": ds_key,
        "n": len(samples), "seed": SEED, "elapsed_sec": round(dt, 1),
        "items": [{"id": s[3], "ref": s[2], "hyp": h} for s, h in zip(samples, hyps)],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written: {dest}  ({dt:.1f}초)")


def compare(ds_key: str):
    import numpy as np
    import jiwer
    arms = {}
    for a in MODELS:
        p = OUT / f"stt_{ds_key}_arm{a}.json"
        if p.exists():
            arms[a] = json.loads(p.read_text(encoding="utf-8"))
    if len(arms) < 2:
        raise SystemExit(f"arm 결과 2개 이상 필요 — 현재 {sorted(arms)}")
    ids = {a: [x["id"] for x in d["items"]] for a, d in arms.items()}
    ref0 = ids[sorted(arms)[0]]
    for a, v in ids.items():
        assert v == ref0, f"arm {a} 발화 순서 불일치 — 쌍체 비교 불가"

    def per(d, prep, fn):
        vals = []
        for x in d["items"]:
            r, h = prep(x["ref"]), prep(x["hyp"])
            if not r:                       # 참조가 비면(전부 숫자였던 발화) 제외 표시
                vals.append(np.nan)
            else:
                vals.append(fn(r, h) if h else 1.0)
        return np.array(vals, dtype=float)

    M = {a: {"cer_raw": per(d, norm_basic, jiwer.cer),
             "wer_raw": per(d, norm_basic, jiwer.wer),
             "cer_numfree": per(d, norm_numfree, jiwer.cer)} for a, d in arms.items()}
    keep = ~np.isnan(np.vstack([M[a]["cer_numfree"] for a in M])).any(axis=0)
    out = {
        "note": "채택 아님. 주지표는 cer_numfree(표기 중립) — 데이터셋의 숫자 표기 관습이 "
                "특정 모델에 유리해지는 것을 제거한 값(사용자 결정 2026-08-04).",
        "dataset": ds_key, "n_utt": int(keep.sum()),
        "n_excluded_all_numeric_ref": int((~keep).sum()), "seed": SEED,
        "leakage_warning": ("arm B(ghost613)는 zeroth로 파인튜닝됐고 자체 val/test를 원본 "
                            "test 50/50 분할로 만들었다 — zeroth 결과는 arm B에 누수다."
                            if ds_key == "zeroth" else "없음(FLEURS는 arm B 학습셋과 무관)"),
        "arms": {}, "vs_current": {},
    }
    for a in sorted(M):
        out["arms"][a] = {
            "model": arms[a]["model"],
            "cer_numfree": round(float(np.nanmean(M[a]["cer_numfree"][keep])), 4),
            "cer_raw": round(float(np.nanmean(M[a]["cer_raw"][keep])), 4),
            "wer_raw": round(float(np.nanmean(M[a]["wer_raw"][keep])), 4),
            "elapsed_sec": arms[a]["elapsed_sec"],
        }
    rng = np.random.default_rng(SEED)
    n = int(keep.sum())
    ib = rng.integers(0, n, size=(2000, n))
    for a in sorted(M):
        if a == "A":
            continue
        for key in ("cer_numfree", "cer_raw"):
            d = M[a][key][keep] - M["A"][key][keep]
            ci = [round(float(x), 4) for x in np.percentile(d[ib].mean(1), [2.5, 97.5])]
            out["vs_current"].setdefault(a, {})[key] = {
                "delta": round(float(d.mean()), 4), "ci95_paired": ci,
                "significant": not (ci[0] <= 0 <= ci[1]),
                "direction": "개선" if d.mean() < 0 else "악화",
            }
    dest = OUT / f"stt_{ds_key}_compare.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=list(MODELS))
    ap.add_argument("--dataset", choices=list(DATASETS), default="fleurs")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if args.compare:
        compare(args.dataset)
    elif args.arm:
        main_arm(args.arm, args.dataset)
    else:
        ap.error("--arm 또는 --compare 필요")
