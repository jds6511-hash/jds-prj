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

**정규화를 하나로 고르지 않는다.** AI Hub 전사는 `(철자)/(발음)` 이중 전사와 간투어
태그(`어/`, `뭐/`)를 쓰는데, 어느 쪽을 정답으로 잡느냐로 CER이 움직인다. 유리한 조합을
고르는 것을 막기 위해 **4조합(철자·발음 x 간투어 유지·제거)을 전부 보고**한다.
잡음 코드(b/ n/ l/ o/)는 발화가 아니므로 어느 조합에서도 제거한다.

재현: python docs/probes/kconf_asr_eval.py --sample 700 --arms A_prod,A_prod_b1,C,C_b5
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
        inputs = proc.apply_transcription_request(
            audio=np.asarray(arr, dtype=np.float32), language="ko",
            processor_kwargs={"pad_to_multiple_of": 100})
        inputs = {k: (v.to(model.device) if hasattr(v, "to") else v)
                  for k, v in inputs.items()}
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=440, **dec)
        txt = proc.batch_decode(out[:, inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True)[0]
        hyps.append(prefix.sub("", txt).strip())
        if i % 100 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
    return hyps, time.time() - t0


def cer_vec(refs, hyps, **nk):
    """발화별 (편집거리, 정답 길이). 쌍체 부트스트랩을 위해 벡터로 남긴다."""
    d, n = [], []
    for r, h in zip(refs, hyps):
        rr, hh = normalize(r, **nk), normalize(h, **nk)
        d.append(edit_distance(rr, hh))
        n.append(len(rr))
    return np.array(d, dtype=float), np.array(n, dtype=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=700, help="세션별 층화 표집 총량")
    ap.add_argument("--arms", default="A_prod,A_prod_b1,C,C_b5")
    ap.add_argument("--pack", help="manifest.json이 있는 디렉터리 (서버 실행용)")
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
        print(f"[{arm}] {kind} {name} beams={beams}", flush=True)
        fn = run_faster_whisper if kind == "faster-whisper" else run_qwen3_asr
        hyps[arm], elapsed[arm] = fn(name, rows, beams)
        p = OUT / f"kconf_hyp_{arm}.json"
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
    for reading in ("spelling", "pronunciation"):
        for fillers in ("keep", "drop"):
            key = f"{reading}/{fillers}"
            vecs = {arm: cer_vec(refs, hyps[arm], reading=reading, fillers=fillers)
                    for arm in arms}
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
