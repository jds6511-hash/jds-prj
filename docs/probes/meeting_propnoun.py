"""[STT 후보 비교 Phase 2 — 회의 도메인 고유명사 재현율]

Phase 1(FLEURS)은 뉴스 낭독체다. 회의록 용도의 성능은 **고유명사·전문용어를 정확히
적는가**로 갈리고, Phase 1 상세에서 실제로 그 지점에서만 arm 간 차이가 보였다.

데이터: `data/meeting_probe/cabinet26_20260616.wav`(제26회 국무회의, 42분)와
공식 회의록 `260616 제26회 국무회의록(서울-세종).hwpx`가 쌍으로 있다.

**회의록을 WER 참조로 쓰지 않는 이유**: 개조식 요약체다("봉쇄되고 있습니다"→"봉쇄되고
있음"). 문장 어미가 전부 다르므로 WER/CER은 ASR 정확도가 아니라 문체 차이를 잰다.
반면 **고유명사는 요약 과정에서 표기가 그대로 옮겨진다** — 그래서 고유명사만 참조로 쓴다.

**누수 구조적 불가**: 2026-06-16 회의 음성. arm B의 학습셋(Zeroth, 2019 낭독)과 무관하고,
어떤 모델도 이 음성을 학습할 수 없다(모델 공개 시점이 앞선다).

## 지표

각 타깃 문자열에 대해 arm의 전체 전사문에서 **근사 부분열 매칭**(시작·끝 자유 편집거리)
으로 최소 정규화 편집거리 d를 구한다.
- d == 0                 → hit (정확 표기)
- 0 < d <= ATTEMPT_TAU   → near (발화된 것으로 보이나 오표기)
- d >  ATTEMPT_TAU       → absent (발화 안 됐거나 완전 실패)

**분모 = attempted 집합** = 어느 한 arm이라도 d <= ATTEMPT_TAU인 타깃.
참석자 60여 명 중 대부분은 이름이 실제로 발화되지 않으므로 전체를 분모로 쓰면
"발화 안 된 항목"이 분모를 오염시킨다. attempted 규칙이 이를 걸러낸다.

주지표: attempted 집합에서의 **exact-hit rate**. 쌍체 부트스트랩 95% CI
(B=2000, seed 42 — DESIGN_SPEC 8-1(b)와 동일 방식) + 불일치쌍(discordant) 수.
ATTEMPT_TAU는 결과를 보기 전에 0.40으로 고정하고, 0.34/0.50 민감도를 함께 보고한다.

## 공정성 설계

- **청킹 계획은 오디오 길이만으로 결정**(고정 25초 창 + 2초 겹침). 특정 arm의 VAD·세그먼트
  결과를 쓰지 않는다. 겹침을 두는 이유는 창 경계가 고유명사를 자르는 것을 막기 위함이고,
  존재 기반 지표라 겹침으로 인한 중복은 점수를 왜곡하지 않는다.
- arm A는 **native(전체 파일 1회)와 chunked(동일 창)를 모두** 측정한다. native는 현행
  운영 방식의 기준선, chunked는 arm C와 조건을 맞춘 비교용.
- 타깃 목록은 **회의록의 발화 구간에서만** 뽑고 전사 전에 동결한다(sha256 기록).
  발화 구간 = 개회~부처보고~협조사항. 의안심의 제안이유·부처보고 첨부문은 낭독되지
  않는 문서 텍스트이므로 제외.

실행:
  python3  docs/probes/meeting_propnoun.py --freeze-targets
  python3  docs/probes/meeting_propnoun.py --arm A --mode native
  python3  docs/probes/meeting_propnoun.py --arm A --mode chunked
  python3  docs/probes/meeting_propnoun.py --arm B --mode chunked
  ./.venv_qwen3asr/Scripts/python.exe docs/probes/meeting_propnoun.py --arm C --mode chunked
  python3  docs/probes/meeting_propnoun.py --compare
"""
import argparse, hashlib, json, os, re, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_scratch"
WAV = ROOT / "data" / "meeting_probe" / "cabinet26_20260616.wav"
HWPX = ROOT / "260616 제26회 국무회의록(서울-세종).hwpx"
TARGETS = OUT / "phase2_targets.json"

SEED = 42
ATTEMPT_TAU = 0.40                  # 결과 보기 전 고정
TAU_SENSITIVITY = (0.34, 0.40, 0.50)
CHUNK_SEC = 25.0
OVERLAP_SEC = 2.0

MODELS = {
    "A": ("faster-whisper", "large-v3"),
    "B": ("faster-whisper", "ghost613/faster-whisper-large-v3-turbo-korean"),
    "C": ("qwen3-asr", "Qwen/Qwen3-ASR-1.7B-hf"),
}

if os.name == "nt":                  # ctranslate2용 cuBLAS DLL [m3_generate.py 규약]
    import site
    for _b in (site.getusersitepackages(), *site.getsitepackages()):
        _d = os.path.join(_b, "nvidia", "cublas", "bin")
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            break


# ---------------------------------------------------------------- 타깃 동결

# 발화 구간 경계는 회의록 단락 텍스트로 지정한다(줄번호는 추출 방식에 따라 흔들림).
SPOKEN_SPANS = [
    ("(10시 개회)", "1. 응급환자 이송체계 혁신 시범사업 결과"),
    ("(협조사항) 2027 서울 세계청년대회 정부 합동 지원 협조요청", "▢ 의안심의(사회 : 국무총리)"),
]

# 회의록 발화 구간에서 사람이 읽어 뽑은 고유명사·전문용어 후보.
# 전사문이 존재하기 전에 작성했으므로 특정 arm에 유리하게 고를 수 없다.
# 스크립트가 각 항목이 발화 구간에 실제로 있는지 검증하고, 없으면 제외+보고한다.
CANDIDATES = {
    "person": [
        "김민석", "구윤철", "유재성", "정성호", "윤호중",
        "문신학", "이억원", "정은경", "박윤주", "송미령", "김대현",
    ],
    "org": [
        "대한체육회", "서울경찰청", "경찰청", "법무부", "행안부", "해수부",
        "재경부", "산업부", "금융위", "농식품부", "문체부", "외교부",
        "롯데케미칼", "국가정책조정회의", "차관회의", "조직위원회",
        "보건복지부", "농림축산식품부", "문화체육관광부", "행정안전부",
        "재정경제부", "산업통상부", "금융위원회",
    ],
    "place": [
        "잠실 올림픽공원", "핸드볼경기장", "호르무즈 해협", "전남광주통합특별시",
        "제네바", "사우디", "카타르", "서울광장", "중남미", "중앙아시아", "아세안",
        "이란", "미국", "영국", "프랑스", "일본",
    ],
    "roman": ["WTI", "Brent", "NCC", "UAE", "MOU", "AI", "SWAP"],
    "named": [
        "착한주유소", "착하디착한 주유소", "햇빛이음학교", "K-뉴딜 아카데미",
        "포용금융 현장 대토론회", "채권·자금 시장 안정 프로그램",
        "주가 조작 근절 합동대응단", "국민참여성장펀드", "온누리상품권", "촌캉스",
        "바쁜 일상 속 쉼표", "2027 서울 세계청년대회", "2026 농촌여행 페스티벌",
        "금융안정반", "민생복지반", "해외상황관리반", "최고액 정산위원회",
        "레오 14세", "농촌체험마을", "최고 가격제",
    ],
    "term": [
        "코스피", "국고채", "나프타", "비축유", "고용위기지역", "특별고용지원",
        "긴급 할당 관세", "현행범", "채증", "참정권", "일벌백계", "신사 협정",
        "무법지대", "납품단가", "고환율", "취약 차주", "수입신용장", "공급망",
        "재외국민", "특명전권대사", "천주교", "가톨릭",
    ],
}


def minutes_text() -> str:
    """hwpx 본문을 단락 단위 개행으로 이어붙인 문자열."""
    paras = []
    with zipfile.ZipFile(HWPX) as z:
        for n in sorted(x for x in z.namelist()
                        if re.fullmatch(r"Contents/section\d+\.xml", x)):
            xml = z.read(n).decode("utf-8")
            for p in re.findall(r"<hp:p\b.*?</hp:p>", xml, re.S):
                txt = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", p, re.S))
                for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"),
                             ("&quot;", '"'), ("&apos;", "'")):
                    txt = txt.replace(a, b)
                txt = re.sub(r"<[^>]+>", "", txt).strip()
                if txt:
                    paras.append(txt)
    return "\n".join(paras)


def spoken_portion(full: str) -> str:
    out = []
    for start, end in SPOKEN_SPANS:
        i = full.find(start)
        j = full.find(end)
        if i < 0 or j < 0 or j <= i:
            raise ValueError(f"발화 구간 경계 못 찾음: {start!r} / {end!r}")
        out.append(full[i:j])
    return "\n".join(out)


def freeze_targets():
    spoken = spoken_portion(minutes_text())
    kept, dropped = [], []
    for cat, items in CANDIDATES.items():
        for t in items:
            (kept if t in spoken else dropped).append(
                {"text": t, "cat": cat} if t in spoken else t)
    payload = {
        "note": "전사 전 동결. 발화 구간(개회~협조사항)에서만 추출.",
        "attempt_tau": ATTEMPT_TAU,
        "spoken_chars": len(spoken),
        "spoken_sha256": hashlib.sha256(spoken.encode("utf-8")).hexdigest(),
        "n_targets": len(kept),
        "dropped_not_in_spoken": dropped,
        "targets": kept,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    TARGETS.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"targets={len(kept)} dropped={len(dropped)} -> {TARGETS}")


# ---------------------------------------------------------------- 전사

def chunk_plan(n_samples: int, sr: int):
    """오디오 길이만으로 결정되는 (start, end) 샘플 인덱스 목록. arm 무관."""
    step = int((CHUNK_SEC - OVERLAP_SEC) * sr)
    win = int(CHUNK_SEC * sr)
    spans, s = [], 0
    while s < n_samples:
        spans.append((s, min(s + win, n_samples)))
        if s + win >= n_samples:
            break
        s += step
    return spans


def load_wav():
    import soundfile as sf
    arr, sr = sf.read(str(WAV), dtype="float32", always_2d=False)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return arr, sr


def run_faster_whisper(model_name, arr, sr, mode):
    from faster_whisper import WhisperModel
    last = None
    for dev, ct in (("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")):
        try:
            m = WhisperModel(model_name, device=dev, compute_type=ct)
            break
        except Exception as e:                                    # noqa: BLE001
            last = e
    else:
        raise RuntimeError(f"모델 로드 실패: {last}")
    if mode == "prod":
        # 현행 파이프라인과 **완전히 동일한** 호출 [m3_generate.py:41-44].
        # 한국어 환각 방지 2중 장치가 켜져 있고 VAD는 쓰지 않는다 —
        # native 모드(장치 없음)와 비교하면 이 장치들의 기여가 분리된다.
        segs, _ = m.transcribe(arr, language="ko", word_timestamps=True,
                               condition_on_previous_text=False,
                               hallucination_silence_threshold=1.0)
        return " ".join(s.text.strip() for s in segs)
    if mode == "native":
        segs, _ = m.transcribe(arr, language="ko", vad_filter=True)
        return " ".join(s.text.strip() for s in segs)
    parts = []
    for i, (a, b) in enumerate(chunk_plan(len(arr), sr)):
        segs, _ = m.transcribe(arr[a:b], language="ko")
        parts.append(" ".join(s.text.strip() for s in segs))
        if i % 20 == 0:
            print(f"  chunk {i}", flush=True)
    return " ".join(parts)


def run_qwen3_asr(model_name, arr, sr, mode):
    """Phase 1과 동일한 호출 경로(파일경로 대신 배열, pad_to_multiple_of=100)."""
    import numpy as np, torch
    from transformers import AutoProcessor, AutoModelForMultimodalLM
    if mode != "chunked":
        raise SystemExit("arm C는 chunked만 지원(42분 단일 입력 불가)")
    proc = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_name, dtype=torch.float16, device_map={"": 0}).eval()
    prefix = re.compile(r"^\s*language\s+\w+\s*")
    parts = []
    for i, (a, b) in enumerate(chunk_plan(len(arr), sr)):
        inputs = proc.apply_transcription_request(
            audio=np.asarray(arr[a:b], dtype=np.float32), language="ko",
            processor_kwargs={"pad_to_multiple_of": 100},
        ).to(model.device, model.dtype)
        with torch.inference_mode():
            ids = model.generate(**inputs, max_new_tokens=440)
        txt = proc.batch_decode(ids[:, inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True,
                                return_format="transcription_only")[0]
        parts.append(prefix.sub("", txt).replace("<asr_text>", "").strip())
        if i % 20 == 0:
            print(f"  chunk {i}", flush=True)
    return " ".join(parts)


def main_arm(arm: str, mode: str):
    kind, name = MODELS[arm]
    arr, sr = load_wav()
    spans = chunk_plan(len(arr), sr)
    print(f"arm {arm} / {name} / {mode} / {len(arr)/sr:.1f}초 / chunks={len(spans)}",
          flush=True)
    t0 = time.time()
    if kind == "faster-whisper":
        text = run_faster_whisper(name, arr, sr, mode)
    else:
        text = run_qwen3_asr(name, arr, sr, mode)
    dt = time.time() - t0
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"phase2_hyp_{arm}_{mode}.json"
    p.write_text(json.dumps({
        "arm": arm, "model": name, "mode": mode,
        "audio_sec": round(len(arr) / sr, 1), "n_chunks": len(spans),
        "elapsed_sec": round(dt, 1),
        "realtime_factor": round(dt / (len(arr) / sr), 2),
        "chars": len(text), "text": text,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done {dt:.1f}s chars={len(text)} -> {p}")


# ---------------------------------------------------------------- 채점

def norm(t: str) -> str:
    """비교 정규화: 공백·구두점 제거, 영문 소문자화. 표기 차이만 남긴다."""
    t = re.sub(r"[^가-힣0-9a-zA-Z]", "", t)
    return t.lower()


def approx_substring_dist(needle: str, hay: str) -> float:
    """시작·끝 자유 편집거리 / len(needle). 근사 부분열 매칭."""
    m, n = len(needle), len(hay)
    if m == 0:
        return 1.0
    prev = [0] * (n + 1)              # 첫 행 0 = 건초더미 어디서든 시작 허용
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        ni = needle[i - 1]
        for j in range(1, n + 1):
            cur[j] = min(prev[j - 1] + (ni != hay[j - 1]),
                         prev[j] + 1, cur[j - 1] + 1)
        prev = cur
    return min(prev) / m


def bootstrap_ci(pairs, b=2000, seed=SEED):
    """쌍체 부트스트랩: (base_hit, cand_hit) 리스트의 hit-rate 차이 CI."""
    import numpy as np
    if not pairs:
        return None
    a = np.array([p[0] for p in pairs], dtype=float)
    c = np.array([p[1] for p in pairs], dtype=float)
    rng = np.random.default_rng(seed)
    n = len(a)
    d = [float(c[i].mean() - a[i].mean())
         for i in (rng.integers(0, n, size=n) for _ in range(b))]
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"delta": round(float(c.mean() - a.mean()), 4),
            "ci95_paired": [round(float(lo), 4), round(float(hi), 4)],
            "significant": bool(lo > 0 or hi < 0)}


def compare():
    tg = json.loads(TARGETS.read_text(encoding="utf-8"))
    runs = {}
    for p in sorted(OUT.glob("phase2_hyp_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        runs[f"{d['arm']}_{d['mode']}"] = d
    if not runs:
        raise SystemExit("전사 결과 없음")
    hays = {k: norm(v["text"]) for k, v in runs.items()}

    rows = []
    for t in tg["targets"]:
        nt = norm(t["text"])
        d = {k: round(approx_substring_dist(nt, h), 4) for k, h in hays.items()}
        rows.append({"text": t["text"], "cat": t["cat"], "dist": d})

    report = {
        "note": "채택 아님. Phase 2 회의 도메인 고유명사 재현율.",
        "audio": WAV.name, "minutes": HWPX.name,
        "targets_sha256": tg["spoken_sha256"], "n_targets": len(rows),
        "attempt_tau": ATTEMPT_TAU, "seed": SEED,
        "runs": {k: {"model": v["model"], "mode": v["mode"],
                     "elapsed_sec": v["elapsed_sec"],
                     "realtime_factor": v["realtime_factor"],
                     "chars": v["chars"]} for k, v in runs.items()},
        "by_tau": {},
    }
    keys = sorted(hays)
    for tau in TAU_SENSITIVITY:
        att = [r for r in rows if min(r["dist"].values()) <= tau]
        block = {"n_attempted": len(att), "hit_rate": {}, "near_rate": {}}
        for k in keys:
            hit = sum(1 for r in att if r["dist"][k] == 0.0)
            near = sum(1 for r in att if 0.0 < r["dist"][k] <= tau)
            block["hit_rate"][k] = round(hit / len(att), 4) if att else None
            block["near_rate"][k] = round(near / len(att), 4) if att else None
        # 전 쌍 비교. 단일 기준선으로는 핵심 질문을 못 본다 —
        # A_native(현행 운영) vs A_chunked는 **같은 모델**이고 청킹만 다르므로,
        # 모델 자체의 우열은 C_chunked vs A_chunked로 봐야 한다.
        block["pairs"] = {}
        for i, base in enumerate(keys):
            for cand in keys[i + 1:]:
                pairs = [(1.0 if r["dist"][base] == 0.0 else 0.0,
                          1.0 if r["dist"][cand] == 0.0 else 0.0) for r in att]
                ci = bootstrap_ci(pairs)
                block["pairs"][f"{cand}_vs_{base}"] = {
                    **(ci or {}),
                    "discordant_cand_only": sum(1 for x, y in pairs if y > x),
                    "discordant_base_only": sum(1 for x, y in pairs if y < x)}
        if tau == ATTEMPT_TAU:
            block["by_cat"] = {}
            for cat in sorted({r["cat"] for r in att}):
                sub = [r for r in att if r["cat"] == cat]
                block["by_cat"][cat] = {
                    "n": len(sub),
                    **{k: round(sum(1 for r in sub if r["dist"][k] == 0.0) / len(sub), 4)
                       for k in keys}}
            block["discordant_items"] = [
                {"text": r["text"], "cat": r["cat"], "dist": r["dist"]}
                for r in att
                if len({1 if r["dist"][k] == 0.0 else 0 for k in keys}) > 1]
        report["by_tau"][str(tau)] = block

    p = OUT / "phase2_propnoun_compare.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-targets", action="store_true")
    ap.add_argument("--arm", choices=list(MODELS))
    ap.add_argument("--mode", choices=["prod", "native", "chunked"], default="chunked")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    if a.freeze_targets:
        freeze_targets()
    elif a.compare:
        compare()
    elif a.arm:
        main_arm(a.arm, a.mode)
    else:
        ap.error("--freeze-targets / --arm / --compare 중 하나")
