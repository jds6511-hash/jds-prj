"""[STT 후보 비교 Phase 2 — 회의 도메인 고유명사 재현율]

Phase 1(FLEURS)은 뉴스 낭독체다. 회의록 용도의 성능은 **고유명사·전문용어를 정확히
적는가**로 갈리고, Phase 1 상세에서 실제로 그 지점에서만 arm 간 차이가 보였다.

데이터(`--meeting`): 국무회의 영상과 **공식 회의록**이 쌍으로 있는 회의.
  c26  제26회(2026-06-16), 42분   / `260616 …(서울-세종).hwpx`
  c20  제20회(2026-05-06), 165분  / `260506 …(청와대).hwpx`

**회의록을 WER 참조로 쓰지 않는 이유**: 개조식 요약체다("봉쇄되고 있습니다"→"봉쇄되고
있음"). 문장 어미가 전부 다르므로 WER/CER은 ASR 정확도가 아니라 문체 차이를 잰다.
반면 **고유명사는 요약 과정에서 표기가 그대로 옮겨진다** — 그래서 고유명사만 참조로 쓴다.

**누수 구조적 불가**: 2026년 회의 음성. arm B의 학습셋(Zeroth, 2019 낭독)과 무관하고,
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

- **기준선 arm은 `--mode prod`** = `m3_generate.py:41-44`의 호출 인자를 그대로 복사한
  것(long-form + `condition_on_previous_text=False` +
  `hallucination_silence_threshold=1.0`). 라이브러리 기본값으로 기준선을 세우면 허수아비가
  된다 — 실제로 c26 1차 측정에서 기본값 arm(`native`)과 비교해 "C가 15%p 유의하게 이긴다"는
  잘못된 결론이 나왔고, `prod`를 넣으니 비유의로 바뀌었다. `native`는 그 두 장치의 기여를
  분리하기 위한 참고 arm으로만 남긴다.
- **청킹 계획은 오디오 길이만으로 결정**(고정 25초 창 + 2초 겹침). 특정 arm의 VAD·세그먼트
  결과를 쓰지 않는다. 겹침을 두는 이유는 창 경계가 고유명사를 자르는 것을 막기 위함이고,
  존재 기반 지표라 겹침으로 인한 중복은 점수를 왜곡하지 않는다.
- 타깃 목록은 **회의록의 발화 단락에서만** 뽑고 전사 전에 동결한다(sha256 기록).
  범위는 개회~의안심의이고, 그 안에서도 낭독되지 않는 첨부문 단락을 단락 단위로 걸러낸다
  (제20회는 부처보고 안에서 발화와 첨부문이 교대로 나와 구간 지정이 불가능하다).
  판정 규칙과 검증 근거는 아래 `spoken_portion` 위 주석 참조.
- **속도 수치는 상한값으로만 읽는다.** 순차 배치로 재면 앞 arm의 VRAM 잔존 점유가
  뒤 arm을 시스템 RAM으로 밀어내 수십 배 느려진다(실측 43배, 출력은 동일).

실행:
  python3 docs/probes/meeting_propnoun.py --meeting c20 --freeze-targets
  python3 docs/probes/meeting_propnoun.py --meeting c20 --arm A --mode prod
  python3 docs/probes/meeting_propnoun.py --meeting c20 --arm A --mode chunked
  ./.venv_qwen3asr/Scripts/python.exe docs/probes/meeting_propnoun.py \
      --meeting c20 --arm C --mode chunked
  python3 docs/probes/meeting_propnoun.py --meeting c20 --compare
  python3 docs/probes/meeting_propnoun.py --pool            # 전 회의 통합 판정
"""
import argparse, hashlib, json, os, re, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_scratch"

# 회의별 (오디오, 공식 회의록). --meeting 으로 선택.
MEETINGS = {
    "c26": (ROOT / "data/meeting_probe/cabinet26_20260616.wav",
            ROOT / "260616 제26회 국무회의록(서울-세종).hwpx"),
    "c20": (ROOT / "data/meeting_probe/cabinet20_20260506.wav",
            ROOT / "260506 제20회 국무회의록(청와대).hwpx"),
}
MEETING = "c26"          # main()에서 --meeting 값으로 덮어씀
# 산출물 접미는 **항상** "_<회의키>"다. 한때 c26만 접미 없이 뒀는데(하위호환),
# 그러면 c26의 glob `phase2_hyp_*.json`이 `phase2_hyp_A_prod_c20.json`까지 잡아
# c26 타깃을 c20 전사문으로 채점했다(실측 사고). 접미 없는 회의를 만들지 마라.
SUF = f"_{MEETING}"
WAV, HWPX = MEETINGS[MEETING]
TARGETS = OUT / f"phase2_targets{SUF}.json"


def set_meeting(key: str):
    """모듈 전역을 회의별로 재설정. 산출물 경로가 모두 이 값에 매달려 있다."""
    global MEETING, SUF, WAV, HWPX, TARGETS
    MEETING = key
    SUF = f"_{key}"
    WAV, HWPX = MEETINGS[key]
    TARGETS = OUT / f"phase2_targets{SUF}.json"

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

# ── 발화 단락 판정 ────────────────────────────────────────────────────────
# 회의록은 발화(개조식 요약)와 **낭독되지 않는 첨부문**이 섞여 있다. 제20회는 부처보고
# 안에서 둘이 교대로 나와 구간 지정이 불가능하므로 단락 단위로 판정한다.
#
# 범위: `(10시 개회)` ~ `▢ 의안심의`. 의안심의 이후의 제안이유는 문서 텍스트다.
# 그 안에서 아래를 제외한다.
#   - 문서 기호로 시작하는 단락(□ ▷ ◆ ※ ❶ 등) = 첨부문
#   - `ㅇ 보고 :` / `ㅇ 토의 :` 같은 서식 행
#   - 개조식 종결(음/함/임/바람/…)이나 물음표로 끝나지 않는 짧은 단락 = 표 조각
# 화자 라벨 행(`• 대통령 이재명`)은 발화가 아니지만 **인명·직책 표기의 출처**이므로
# 남긴다. 단 `ㅇ (109전화, SNS상담) …` 같은 첨부문 행이 `ㅇ`를 공유하므로,
# 라벨은 "직책 접미 + 끝에 2~4자 한글 이름"으로 좁혀 판정한다(실측으로 조정).
DOC_MARK = "□▷◆➡⇨※❶❷❸❹❺󰋻▸▴◈-*·"
_ADMIN = re.compile(r"^[ㅇo○]\s*(보\s*고|보고내용|토\s*의|의\s*결|제안설명|제안이유)\s*[:：]?")
_TITLE = "(장관|차관|처장|청장|위원장|실장|총리|대통령|본부장|차장|비서관|대행|원장|의정관)"
_LABEL = re.compile(rf"^[•ㅇo○]\s*.*{_TITLE}\s*\S*\s+[가-힣]{{2,4}}$")
_ENDING = re.compile(r"(음|함|임|됨|짐|옴|봄|힘|바람|드림)[.\"'”’\s]*$|[?？]\s*$")
SPOKEN_START, SPOKEN_END = "개회)", "▢ 의안심의"

# 회의록 발화 구간에서 사람이 읽어 뽑은 고유명사·전문용어 후보.
# 전사문이 존재하기 전에 작성했으므로 특정 arm에 유리하게 고를 수 없다.
# 스크립트가 각 항목이 발화 구간에 실제로 있는지 검증하고, 없으면 제외+보고한다.
CANDIDATES = {}
CANDIDATES["c26"] = {
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

# 제20회(2026-05-06, 2시간 45분). c26과 동일 절차 — 발화 단락만 읽고 전사 전에 작성.
CANDIDATES["c20"] = {
    "person": [
        "이재명", "김민석", "송미령", "김영수", "윤호중", "이형일", "문신학",
        "오유경", "정은경", "이억원", "김용범", "봉욱", "이진수", "정일연",
        "박홍근", "김윤덕", "원민경", "조원철", "유재성", "트럼프", "루비오",
    ],
    "org": [
        "산림청", "농식품부", "국조실", "행안부", "법무부", "금융위", "기획처",
        "식약처", "외교부", "산업부", "국민권익위원회", "공정거래위", "농지은행",
        "한국은행", "여천NCC", "한국 백신", "민주당", "을지로 위원회",
        "금융감독원", "농림축산식품부", "보건복지부", "행정안전부", "금융위원회",
        "식품의약품안전처", "국토교통부", "성평등가족부", "법제처",
    ],
    "place": [
        "호르무즈 해협", "이란", "미국", "전북", "경기도", "남원", "성남시",
        "호주", "수도권", "영국",
    ],
    "roman": ["Brent", "WTI", "AA", "TF", "AI", "WGBI", "FOMC", "OPEC",
              "SWAP", "NCC", "SNS"],
    "named": [
        "착하디착한 주유소", "프로젝트 프리덤", "장대한 분노 작전", "새희망 홀씨",
        "포용금융 평가 체계", "청년 뉴딜", "부마항쟁", "물가안정법",
        "공익신고자보호법", "농지법", "금융안정반", "민생복지반",
        "해외 상황관리반", "거시경제 물가대응반", "전략경제협력특사단",
        "민생 물가 TF", "최고 가격제", "고용유지 지원금", "고용위기지역",
        "특별고용 지원 업종", "농촌여행", "공익신고자", "국가자살예방전략",
    ],
    "term": [
        "매점매석", "환가처분", "이행강제금", "처분의무", "처분명령",
        "신고포상금", "공시지가", "감정평가액", "직불금", "임차농", "자경",
        "페이퍼컴퍼니", "벌떼 입찰", "바지 사장", "계고장", "재자연화",
        "핀플루언서", "수입신용장", "나프타", "비축유", "시효 완성",
        "기한이익", "연체채권", "고신용자", "중저신용자", "포용금융",
        "불법사금융", "일벌백계", "징검다리", "흑색 선전", "무역수지",
        "펀더멘털", "할당관세", "매도자", "재외국민", "예인", "선사",
        "스트레스 테스트", "리스크", "고독사", "복지 위기 가구",
        "의료 폐기물", "희귀질환자", "약포지", "종합병원", "혈액 투석",
        "브레인스토밍", "국정감사", "흑색선전", "직무유기", "집행유예",
        "선이자", "추심", "채무조정", "손비", "출연료", "규제상 혜택",
    ],
}


def minutes_paras() -> list[str]:
    """hwpx 본문 단락 리스트."""
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
    return paras


def spoken_portion() -> str:
    paras = minutes_paras()
    try:
        i = next(k for k, p in enumerate(paras) if SPOKEN_START in p)
        j = next(k for k, p in enumerate(paras) if p.startswith(SPOKEN_END))
    except StopIteration:
        raise ValueError(f"발화 구간 경계 못 찾음: {SPOKEN_START!r} / {SPOKEN_END!r}")
    keep = []
    for p in paras[i:j]:
        if p[0] in DOC_MARK or _ADMIN.match(p):
            continue
        if _LABEL.match(p):                 # 화자 라벨: 인명·직책 표기 출처로 보존
            keep.append(p)
            continue
        if len(p) < 8 or not _ENDING.search(p):
            continue
        keep.append(p)
    return "\n".join(keep)


def freeze_targets():
    spoken = spoken_portion()
    kept, dropped = [], []
    for cat, items in CANDIDATES[MEETING].items():
        for t in items:
            if t in spoken:
                kept.append({"text": t, "cat": cat})
            else:
                dropped.append(t)
    payload = {
        "note": "전사 전 동결. 발화 단락(개회~의안심의, 첨부문 제외)에서만 추출.",
        "meeting": MEETING,
        "minutes": HWPX.name,
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
    print(f"[{MEETING}] targets={len(kept)} dropped={len(dropped)} "
          f"spoken={len(spoken)}자 -> {TARGETS}")


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
    p = OUT / f"phase2_hyp_{arm}_{mode}{SUF}.json"
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


def score_rows():
    """현재 회의의 (타깃 × arm) 거리 행렬과 run 메타를 돌려준다."""
    tg = json.loads(TARGETS.read_text(encoding="utf-8"))
    runs = {}
    for p in sorted(OUT.glob(f"phase2_hyp_*{SUF}.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        runs[f"{d['arm']}_{d['mode']}"] = d
    if not runs:
        raise SystemExit(f"[{MEETING}] 전사 결과 없음")
    hays = {k: norm(v["text"]) for k, v in runs.items()}
    rows = []
    for t in tg["targets"]:
        nt = norm(t["text"])
        rows.append({"text": t["text"], "cat": t["cat"], "meeting": MEETING,
                     "dist": {k: round(approx_substring_dist(nt, h), 4)
                              for k, h in hays.items()}})
    return rows, runs, tg


def _stats_block(rows, keys, tau, with_detail):
    att = [r for r in rows if min(r["dist"].values()) <= tau]
    block = {"n_attempted": len(att), "hit_rate": {}, "near_rate": {}}
    for k in keys:
        hit = sum(1 for r in att if r["dist"][k] == 0.0)
        near = sum(1 for r in att if 0.0 < r["dist"][k] <= tau)
        block["hit_rate"][k] = round(hit / len(att), 4) if att else None
        block["near_rate"][k] = round(near / len(att), 4) if att else None
    # 전 쌍 비교. 단일 기준선으로는 핵심 질문을 못 본다 — A_prod vs A_chunked는
    # **같은 모델**이고 청킹만 다르므로, 모델 자체의 우열은 C_chunked vs A_prod다.
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
    if with_detail:
        block["by_cat"] = {}
        for cat in sorted({r["cat"] for r in att}):
            sub = [r for r in att if r["cat"] == cat]
            block["by_cat"][cat] = {
                "n": len(sub),
                **{k: round(sum(1 for r in sub if r["dist"][k] == 0.0) / len(sub), 4)
                   for k in keys}}
        block["discordant_items"] = [
            {"text": r["text"], "cat": r["cat"], "meeting": r["meeting"],
             "dist": r["dist"]}
            for r in att
            if len({1 if r["dist"][k] == 0.0 else 0 for k in keys}) > 1]
    return block


def pool():
    """회의 전편을 합쳐 한 번에 검정한다.

    회의 1편·타깃 74건으로는 CI가 0을 아슬하게 포함해 판정이 안 됐다. 표본을 늘리는
    것이 유일한 해결책이므로, **같은 arm 구성이 있는 회의만** 골라 attempted를 합친다.
    회의별 결과도 함께 남긴다(효과가 한 회의에서만 나오는지 확인해야 하므로).
    """
    per, pooled = {}, []
    for key in MEETINGS:
        set_meeting(key)
        try:
            rows, runs, _ = score_rows()
        except SystemExit:
            continue
        per[key] = {"arms": sorted(rows[0]["dist"]) if rows else [],
                    "n_targets": len(rows),
                    "runs": {k: {"mode": v["mode"], "chars": v["chars"],
                                 "audio_sec": v["audio_sec"]}
                             for k, v in runs.items()}}
        pooled.append((key, rows))
    if len(pooled) < 2:
        raise SystemExit("합칠 회의가 2편 미만")
    # arm 구성이 다르면 합칠 수 없다 — 교집합만 쓴다.
    common = set.intersection(*(set(r[0]["dist"]) for _, r in pooled))
    keys = sorted(common)
    print(f"합산 회의: {[k for k,_ in pooled]} / 공통 arm: {keys}")
    allrows = [{**r, "dist": {k: r["dist"][k] for k in keys}}
               for _, rs in pooled for r in rs]
    report = {"note": "채택 아님. Phase 2 회의 통합 판정.",
              "meetings": [k for k, _ in pooled], "arms": keys,
              "n_targets_total": len(allrows), "attempt_tau": ATTEMPT_TAU,
              "seed": SEED, "per_meeting_meta": per, "by_tau": {}, "per_meeting": {}}
    for tau in TAU_SENSITIVITY:
        report["by_tau"][str(tau)] = _stats_block(allrows, keys, tau,
                                                  tau == ATTEMPT_TAU)
    for key, rs in pooled:
        sub = [{**r, "dist": {k: r["dist"][k] for k in keys}} for r in rs]
        report["per_meeting"][key] = _stats_block(sub, keys, ATTEMPT_TAU, True)
    p = OUT / "phase2_propnoun_pooled.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {p}")


def compare():
    rows, runs, tg = score_rows()
    hays = {k: None for k in runs}

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
        report["by_tau"][str(tau)] = _stats_block(rows, keys, tau,
                                                  tau == ATTEMPT_TAU)

    p = OUT / f"phase2_propnoun_compare{SUF}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", choices=list(MEETINGS), default="c26")
    ap.add_argument("--freeze-targets", action="store_true")
    ap.add_argument("--arm", choices=list(MODELS))
    ap.add_argument("--mode", choices=["prod", "native", "chunked"], default="chunked")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--pool", action="store_true",
                    help="회의 전편 합산 판정(회의별 결과도 병기)")
    a = ap.parse_args()
    set_meeting(a.meeting)
    if a.pool:
        pool()
    elif a.freeze_targets:
        freeze_targets()
    elif a.compare:
        compare()
    elif a.arm:
        main_arm(a.arm, a.mode)
    else:
        ap.error("--freeze-targets / --arm / --compare / --pool 중 하나")
