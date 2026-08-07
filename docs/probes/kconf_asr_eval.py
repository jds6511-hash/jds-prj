"""[KconfSpeech 정답 전사 기반 STT 비교 — 채택 아님, 실측용]

지금까지 STT 비교는 정답 전사가 없어 **고유명사 존재 여부**라는 근사 지표를 썼다
(docs/probes/meeting_propnoun.py). 이 데이터셋은 발화 단위 정답이 있어 CER을 직접 잰다.

설계상 이점 하나가 크다: 발화가 평균 9.6초·최대 22.1초라 **모든 발화가 Qwen 청크
하나에 들어간다.** 회의 오디오에서 모델 효과와 청크 길이 효과가 섞였던 교란이 사라져
순수 모델·디코딩 비교가 된다.

arm 4종 (디코딩 대칭 2x2):
  A_prod     faster-whisper large-v3, 운영 설정 그대로(빔 5 기본)
  A_prod_b1  같은 설정, 그리디            -> A 내 빔 효과
  C          Qwen3-ASR, 그리디
  C_b5       Qwen3-ASR, 빔 5              -> C 내 빔 효과
  A_prod vs C, A_prod_b1 vs C 가 디코딩을 맞춘 모델 대비다.

**정규화는 배포본 규칙을 그대로 쓴다.** AI Hub가 데이터와 함께 배포하는 베이스라인
툴킷(hypersp, `03.AI모델/`)의 `tasks/SpeechRecognition/kconfspeech/local/cleaners.py`가
공식 규칙이고, 전처리 기본 인자가 **발음(pronounciation) 모드**라 그것이 주지표다.
CER도 배포본 정의를 따른다 — `hypersp/metrics/wer.py`에서 공백 제거 줄이 주석 처리돼
있어 **공백을 문자로 센다**. 코퍼스 단위 마이크로 평균인 것도 동일하다.

우리가 처음 추론했던 규칙과 배포본이 갈리는 지점이 둘 있다: 배포본은 제거 대상이
**기호 문자**라서 간투어 낱말(`어/` -> `어`)과 끊긴 말 조각(`인+` -> `인`)이 살아남고,
잡음 코드 중 `u/`만 `<unk>`로 남는다. 자체 변형 4조합(철자·발음 x 간투어 유지·제거,
공백 제거)은 **민감도 확인용으로만** 병기한다.

**주의 — 이 표본은 학습 분할이다.** 폴더명이 `KconfSpeech_train_D20`이고 배포본
`preprocess_kconfspeech.sh`가 D20~D27을 train으로 돌린다. Whisper·Qwen은 이 데이터를
본 적이 없어(zero-shot) 서로 비교하는 데는 문제가 없지만, **배포 베이스라인(Jasper)과
비교하면 그쪽에만 학습 데이터라 낙관 편향이 붙는다.** 공식 test 분할 없이 3자 비교를
하지 마라.

**후보 모델 검증 규약 점검 (DESIGN_SPEC 8-7).**
- (1) 채널 격리 — **구조적으로 충족**. CER은 STT 출력을 정답 전사와 직접 대는 것이라
  융합(α)을 거치지 않는다. 후보의 개선분이 희석될 경로가 없다.
- (2) 검출 한계 — 발화 1,950건 쌍체 부트스트랩 CI를 정규화 6종 전부에 병기한다.
  CER은 MRR과 달리 천장 포화가 없다(0에 붙지 않는 한).
- (3) 현행 전용 설정 — **미충족, 여기 기록한다.** arm A는 운영 설정을 그대로 받는다
  (`language="ko"`, `condition_on_previous_text=False`,
  `hallucination_silence_threshold=1.0` — 한국어 환각 방지 2중 장치). arm C에는 대응
  설정이 없다. 다만 이 표본은 전 발화가 유효 발화라 무발화 환각 방지 장치가 개입할
  여지가 거의 없고, 빔은 2x2로 대칭을 맞췄다(A/A_b1 vs C/C_b5). **해석 시 이 비대칭을
  빼고 읽지 마라.**
- (4) 동일 환경 대조군 — 충족. 네 arm 전부 같은 서버에서 같은 시점에 생성한다.
- (5) 생성물 전량 저장 — 충족. arm별 가설 전문을 `kconf_hyp_<arm>.json`에 남긴다.

데이터는 재배포 불가라 저장소에 없다. 서버 `/ssd/<SERVER_USER>/kconf_full`에 오디오 1,950건과
정답이 든 manifest.json이 있고, `--pack`으로 그 디렉터리를 가리킨다(로컬 사본은 삭제).

재현: python docs/probes/kconf_asr_eval.py --pack <팩경로> --arms A_prod,A_prod_b1,C,C_b5
      (--reuse: 이미 나온 arm은 재추론 없이 저장분을 쓴다. arm 코드를 고쳤으면
       그 arm의 kconf_hyp_<arm>.json을 지우고 써라)
"""
import argparse, glob, json, os, re, sys, time, wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_scratch"
DATA = ROOT / "New_Sample"
SEED = 42
BOOT_B = 2000

MODELS = {
    "A_prod":    ("faster-whisper", "large-v3", None),
    "A_prod_b1": ("faster-whisper", "large-v3", 1),
    "C":         ("qwen3-asr", "Qwen/Qwen3-ASR-1.7B-hf", None),
    "C_b5":      ("qwen3-asr", "Qwen/Qwen3-ASR-1.7B-hf", 5),
}

# ── 공식 정규화 (AI Hub 배포 툴킷 hypersp: tasks/.../kconfspeech/local/cleaners.py) ──
# 우리 규칙을 지어내지 않고 배포본을 그대로 옮긴다. 그래야 CER 정의가 표준과 같아진다.
_OFFICIAL_NOISE = ["o", "n", "u", "b", "l"]
_OFFICIAL_EXCEPT = ["/", "+", "*", "-", "@", "$", "^", "&", "[", "]", "=", ":", ";", ","]
_OFFICIAL_MARK = ["?", "!", "."]


def official_bracket_filter(sentence: str, mode: str) -> str:
    """`(철자)/(발음)` 중 한쪽만 남긴다. cleaners.bracket_filter 그대로."""
    out, flag = "", (False if mode == "pronunciation" else True)
    if mode == "pronunciation":
        for ch in sentence:
            if ch == "(" and flag is False:
                flag = True
                continue
            if ch == "(" and flag is True:
                flag = False
                continue
            if ch != ")" and flag is False:
                out += ch
    else:                                                # spelling
        for ch in sentence:
            if ch == "(":
                continue
            if ch == ")":
                flag = not flag
                continue
            if flag is True:
                out += ch
    return out


def official_special_filter(sentence: str) -> str:
    """잡음 코드·문장부호·기호 제거. cleaners.special_filter 그대로.

    주의할 점 둘: **`u/`만 `<unk>`로 남고** 나머지 잡음 코드는 사라진다. 그리고 제거
    대상은 **기호 문자**라서 간투어 낱말(`어/` -> `어`)과 끊긴 말 조각(`인+` -> `인`)은
    **살아남는다** — 우리가 임의로 정했던 규칙과 다른 지점이다.
    """
    out = ""
    for i, ch in enumerate(sentence):
        if ch not in _OFFICIAL_MARK:
            if i + 1 < len(sentence) and ch in _OFFICIAL_NOISE and sentence[i + 1] == "/":
                if ch == "u":
                    out += "<unk>"
                continue
        if ch in _OFFICIAL_MARK:
            continue
        elif ch not in _OFFICIAL_EXCEPT:
            out += ch
    return re.sub(r"\s\s+", " ", out.strip())


def official_filter(sentence: str, mode: str = "pronunciation") -> str:
    """배포본 `sentence_filter`. 전처리 기본 인자가 발음 모드라 그것이 공식 기준이다."""
    return official_special_filter(official_bracket_filter(sentence, mode))


# ── 아래는 민감도 확인용 자체 변형 (공식과 다른 처리를 의도적으로 넣은 것) ──
# 발화가 아닌 잡음 코드. AI Hub 규약: b 숨소리 / n 잡음 / l 웃음 / o 기타 / u 불명.
_NOISE = re.compile(r"(?:^|\s)[bnlou]/")
# `(철자)/(발음)` 이중 전사.
_DUAL = re.compile(r"\(([^)]*)\)/\(([^)]*)\)")
# 간투어 태그: 한글 낱말 뒤 슬래시 (`어/`, `뭐/`, `인제/`).
_FILLER = re.compile(r"(?:^|\s)([가-힣]+)/")
# 끊긴 말 (`인+ 인턴`). 모델이 조각을 일관되게 내지 않으므로 조각을 버린다.
_CUT = re.compile(r"\S*\+")
_PUNCT = re.compile(r"[.,?!*@%]")


def normalize(text: str, reading: str = "spelling", fillers: str = "keep",
              drop_space: bool = True) -> str:
    """정답·가설 공통 정규화.

    reading  spelling      이중 전사에서 철자형을 정답으로 (`(2가지)/(두 가지)` -> 2가지)
             pronunciation 발음형을 정답으로                                  -> 두 가지
    fillers  keep          간투어 낱말을 남긴다 (태그 슬래시만 제거)
             drop          간투어 낱말을 지운다 (모델이 흔히 생략하므로 민감도 확인용)
    """
    t = _DUAL.sub(lambda m: m.group(1) if reading == "spelling" else m.group(2), text)
    t = _NOISE.sub(" ", t)
    t = _FILLER.sub(" " if fillers == "drop" else r" \1", t)
    t = _CUT.sub(" ", t)
    t = _PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace(" ", "") if drop_space else t


def edit_distance(a: str, b: str) -> int:
    """레벤슈타인 거리. 발화 단위(<=22초)라 문자열이 짧아 O(nm)으로 충분하다."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def load_manifest(pack_dir: Path):
    """평면 오디오 디렉터리 + manifest.json. 서버 전송용 형식.

    원본은 폴더명이 한글(`원천데이터`/`라벨링데이터`)이라 전송·경로 조작에서 깨지기
    쉽다. 표집은 로컬에서 끝내고 서버에는 ASCII 경로만 올린다.
    """
    man = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    return [{"wav": str(pack_dir / "audio" / f'{i["key"]}.wav'), "session": i["session"],
             "utt": i["utt"], "ref": i["ref"]} for i in man["items"]]


def load_pairs(sample_n: int | None):
    """(wav 경로, 정답 텍스트) 목록. 세션별 층화 표집(시드 고정)."""
    rows = []
    for w in sorted(glob.glob(str(DATA / "원천데이터/**/*.wav"), recursive=True)):
        t = w.replace("원천데이터", "라벨링데이터").replace(
            "_wav_", "_label_").replace(".wav", ".txt")
        if os.path.exists(t):
            rows.append({"wav": w, "session": Path(w).parent.name,
                         "utt": Path(w).stem,
                         "ref": Path(t).read_text(encoding="utf-8").strip()})
    if sample_n is None or sample_n >= len(rows):
        return rows
    rng = np.random.default_rng(SEED)
    bysess: dict[str, list] = {}
    for r in rows:
        bysess.setdefault(r["session"], []).append(r)
    per = max(1, sample_n // len(bysess))
    out = []
    for s in sorted(bysess):
        pool = bysess[s]
        idx = rng.permutation(len(pool))[:per]
        out += [pool[i] for i in sorted(idx)]
    return out


def read_wav(path: str):
    with wave.open(path) as f:
        sr, n = f.getframerate(), f.getnframes()
        arr = np.frombuffer(f.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return arr, sr


def run_faster_whisper(model_name, rows, beams):
    from faster_whisper import WhisperModel
    m = WhisperModel(model_name, device="cuda", compute_type="float16")
    dec = {} if beams is None else {"beam_size": beams, "best_of": beams}
    hyps, t0 = [], time.time()
    for i, r in enumerate(rows):
        arr, _ = read_wav(r["wav"])
        # m3_generate.py와 동일한 운영 호출 (한국어 환각 방지 2중 장치).
        segs, _ = m.transcribe(arr, language="ko", word_timestamps=True,
                               condition_on_previous_text=False,
                               hallucination_silence_threshold=1.0, **dec)
        hyps.append(" ".join(s.text.strip() for s in segs))
        if i % 100 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
    return hyps, time.time() - t0


def run_qwen3_asr(model_name, rows, beams):
    import torch
    from transformers import AutoProcessor, AutoModelForMultimodalLM
    proc = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_name, dtype=torch.float16, device_map={"": 0}).eval()
    dec = {} if beams is None else {"num_beams": beams, "do_sample": False}
    prefix = re.compile(r"^\s*language\s+\w+\s*")
    hyps, t0 = [], time.time()
    for i, r in enumerate(rows):
        arr, _ = read_wav(r["wav"])
        # `.to(device, dtype)`로 한 번에 옮긴다. device만 옮기면 input_features가
        # float32로 남아 fp16 conv와 충돌한다(RuntimeError: Input type (float) and
        # bias type (c10::Half) should be the same — 1차 실행에서 arm C가 여기서 죽었다).
        inputs = proc.apply_transcription_request(
            audio=np.asarray(arr, dtype=np.float32), language="ko",
            processor_kwargs={"pad_to_multiple_of": 100},
        ).to(model.device, model.dtype)
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=440, **dec)
        txt = proc.batch_decode(out[:, inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True,
                                return_format="transcription_only")[0]
        txt = txt.replace("<asr_text>", "")
        hyps.append(prefix.sub("", txt).strip())
        if i % 100 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
    return hyps, time.time() - t0


def cer_vec(refs, hyps, official_mode=None, **nk):
    """발화별 (편집거리, 정답 길이). 쌍체 부트스트랩을 위해 벡터로 남긴다.

    `official_mode`가 주어지면 배포본 `sentence_filter`를 쓴다. 공식 CER은 공백을
    **문자로 세므로**(hypersp/metrics/wer.py에서 공백 제거 줄이 주석 처리돼 있다)
    지우지 않는다.
    """
    d, n = [], []
    for r, h in zip(refs, hyps):
        if official_mode:
            rr, hh = official_filter(r, official_mode), official_filter(h, official_mode)
        else:
            rr, hh = normalize(r, **nk), normalize(h, **nk)
        d.append(edit_distance(rr, hh))
        n.append(len(rr))
    return np.array(d, dtype=float), np.array(n, dtype=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=700, help="세션별 층화 표집 총량")
    ap.add_argument("--arms", default="A_prod,A_prod_b1,C,C_b5")
    ap.add_argument("--pack", help="manifest.json이 있는 디렉터리 (서버 실행용)")
    ap.add_argument("--reuse", action="store_true",
                    help="이미 저장된 kconf_hyp_<arm>.json이 있으면 재추론하지 않는다. "
                         "arm 코드가 바뀐 뒤에는 그 arm의 파일을 지우고 써라")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]

    rows = load_manifest(Path(a.pack)) if a.pack else load_pairs(a.sample)
    sec = sum(len(read_wav(r["wav"])[0]) / 16000 for r in rows)
    print(f"발화 {len(rows)}건 / 오디오 {sec/60:.1f}분 / 세션 "
          f"{len(set(r['session'] for r in rows))}개", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)

    refs = [r["ref"] for r in rows]
    hyps, elapsed = {}, {}
    for arm in arms:
        kind, name, beams = MODELS[arm]
        p = OUT / f"kconf_hyp_{arm}.json"
        if a.reuse and p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            assert d["model"] == name and d["beams"] == beams and len(d["hyps"]) == len(rows), \
                f"{p}가 지금 설정과 다르다 — 지우고 다시 돌려라"
            hyps[arm], elapsed[arm] = d["hyps"], d["elapsed_sec"]
            print(f"[{arm}] 저장분 재사용 ({p.name})", flush=True)
            continue
        print(f"[{arm}] {kind} {name} beams={beams}", flush=True)
        fn = run_faster_whisper if kind == "faster-whisper" else run_qwen3_asr
        hyps[arm], elapsed[arm] = fn(name, rows, beams)
        p.write_text(json.dumps({"arm": arm, "model": name, "beams": beams,
                                 "elapsed_sec": round(elapsed[arm], 1),
                                 "audio_sec": round(sec, 1),
                                 "rtf": round(elapsed[arm] / sec, 4),
                                 "hyps": hyps[arm]}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"[{arm}] {elapsed[arm]/60:.1f}분 RTF {elapsed[arm]/sec:.3f} -> {p}",
              flush=True)

    rep = {"note": "채택 아님. KconfSpeech 정답 전사 기반 CER 비교.",
           "dataset": "KconfSpeech D20 (교육/스튜디오, 방송)",
           "n_utterances": len(rows), "audio_min": round(sec / 60, 1),
           "seed": SEED, "bootstrap_B": BOOT_B, "arms": arms,
           "runtime": {k: {"elapsed_sec": round(v, 1), "rtf": round(v / sec, 4)}
                       for k, v in elapsed.items()},
           "by_normalization": {}}

    rng = np.random.default_rng(SEED)
    ib = rng.integers(0, len(rows), size=(BOOT_B, len(rows)))
    # 공식 정규화 2종(주지표는 발음 모드 — 배포 전처리의 기본 인자)을 먼저,
    # 자체 변형 4종을 민감도 확인으로 뒤에 둔다.
    schemes = ([(f"OFFICIAL/{m}", {"official_mode": m}) for m in ("pronunciation", "spelling")]
               + [(f"{r}/{f}", {"reading": r, "fillers": f})
                  for r in ("spelling", "pronunciation") for f in ("keep", "drop")])
    for key, nk in schemes:
        vecs = {arm: cer_vec(refs, hyps[arm], **nk) for arm in arms}
        blk = {"cer": {arm: round(float(d.sum() / n.sum()), 4)
                       for arm, (d, n) in vecs.items()}, "pairs": {}}
        for i, b in enumerate(arms):
            for c in arms[i + 1:]:
                db, nb = vecs[b]
                dc, nc = vecs[c]
                # 쌍체 부트스트랩: 발화 재표집 인덱스를 두 arm이 공유한다.
                diff = (dc[ib].sum(1) / nc[ib].sum(1)) - (db[ib].sum(1) / nb[ib].sum(1))
                lo, hi = np.percentile(diff, [2.5, 97.5])
                blk["pairs"][f"{c}_vs_{b}"] = {
                    "delta_cer": round(float(dc.sum() / nc.sum() - db.sum() / nb.sum()), 4),
                    "ci95": [round(float(lo), 4), round(float(hi), 4)],
                    "significant": bool(lo > 0 or hi < 0)}
        rep["by_normalization"][key] = blk
        print(f"[{key:22s}] " + "  ".join(
            f"{arm} {blk['cer'][arm]:.4f}" for arm in arms), flush=True)

    p = OUT / "kconf_asr_eval.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", p)


if __name__ == "__main__":
    main()
