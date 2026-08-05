"""Phase 3 — pyannote 화자분리를 회의 오디오에 적용하고 회의록 화자 라벨과 대조한다.

목적: `회의록·화자별 요약` 기능의 WHO 채널 타당성 확인. Phase 2(STT 교체 검토)와 달리
확정 config를 건드리지 않는 **추가 기능** 검토다.

환경 실측 (2026-08-05, RTX 3060 Laptop 6GB):
- `pyannote/speaker-diarization-community-1` + `pyannote.audio 4.0.5`는 **torchcodec
  없이 동작한다**(문서상 블로커 해소). 파형 텐서를 직접 넘기는 경로를 쓴다.
- RTF 0.035 / peak VRAM 1.6GB. 42분 오디오가 ~90초. Whisper·Qwen과 달리 여유가 크다.
- 출력은 `DiarizeOutput`이고 `speaker_diarization`(겹침 허용) /
  `exclusive_speaker_diarization`(겹침 제거) 둘 다 있다. **겹침 제거 쪽을 쓴다** —
  화자별 요약은 한 구간을 한 화자에게 배정해야 한다.
- `nvidia-cudnn-cu12`를 DLL 경로에 추가하면 torch 번들 `cudnn64_9.dll`과 충돌해
  pyannote가 죽는다(stt_test/stt_local.py:32 기록). 절대 추가하지 마라.

측정 설계 — **DER은 측정하지 않는다.** 공식 회의록에 타임스탬프가 없어서 프레임 단위
정답을 만들 수 없다. 대신 회의록이 확실히 주는 것만 쓴다:
  · 발화 구간 화자 라벨의 **종류 수**(`• 국무총리 …` 형태) vs 분리된 클러스터 수
  · 발화 시간 총량 / 턴 길이 분포 (무음 구간을 화자로 잡아내는지)
DER이 필요하면 별도 타임스탬프 라벨링이 선행돼야 한다 — 지금은 하지 않는다.

실행:
  python3 docs/probes/meeting_diarize.py --meeting c26
  python3 docs/probes/meeting_diarize.py --meeting c26 --max-speakers 12
"""
import argparse, importlib.util, json, os, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_scratch"
MODEL = "pyannote/speaker-diarization-community-1"


def load_propnoun():
    """회의 등록부·회의록 파싱을 meeting_propnoun.py에서 재사용(중복 구현 금지)."""
    p = Path(__file__).with_name("meeting_propnoun.py")
    spec = importlib.util.spec_from_file_location("meeting_propnoun", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def read_hf_token() -> str:
    """paper/.env에서 읽는다. 등호 주변 공백·따옴표를 모두 벗겨야 한다 —
    따옴표가 남으면 `Bearer "hf_..."`로 나가 401(실측)."""
    for ln in (ROOT / "paper/.env").read_text(encoding="utf-8").splitlines():
        k, _, v = ln.partition("=")
        if k.strip() == "HF_TOKEN":
            return v.strip().strip('"').strip("'")
    raise SystemExit("paper/.env에 HF_TOKEN 없음")


def minutes_speakers(mp) -> list[str]:
    """**발화 구간**의 화자 라벨 목록.

    `spoken_portion()`을 거쳐야 한다 — 회의록 전체를 훑으면 의안심의 블록의
    `제안설명 : …`(대부분 서면)까지 화자로 세어 c26에서 25종이 나온다(실측 오류).
    발화 구간 경계와 `_LABEL` 판정기는 Phase 2에서 타깃 손실 0으로 검증됐다.
    """
    seen = []
    for line in mp.spoken_portion().split("\n"):
        t = line.strip()
        if mp._LABEL.match(t):
            lab = t.lstrip("•ㅇo○ ").strip()
            if lab not in seen:
                seen.append(lab)
    return seen


def distinct_persons(labels: list[str]) -> dict[str, list[str]]:
    """성명(마지막 토큰) 기준으로 라벨을 묶는다.

    회의록 자체에 동일인 표기 변이가 있다 — c20 `산업통상부차관 문신학` /
    `산업부통상차관 문신학`(직책 오타), c13 `기후에너지환경부장관 김성환` /
    `…김정환`(성명 오타). 직책 문자열로 세면 실제 화자 수가 과대 계상된다.
    성명 오타는 이 방식으로도 안 잡히므로(김성환≠김정환) **인물 수는 상한**이다.
    """
    out = {}
    for lab in labels:
        out.setdefault(lab.split()[-1], []).append(lab)
    return out


def diarize(wav: Path, num=None, lo=None, hi=None):
    import numpy as np, soundfile as sf, torch
    from pyannote.audio import Pipeline
    arr, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    w = torch.from_numpy(arr.T)
    if w.shape[0] > 1:
        w = w.mean(dim=0, keepdim=True)
    audio_sec = w.shape[1] / sr
    pipe = Pipeline.from_pretrained(MODEL, token=read_hf_token())
    if torch.cuda.is_available():
        pipe.to(torch.device("cuda"))
        torch.cuda.reset_peak_memory_stats()
    kw = {}
    if num:
        kw["num_speakers"] = num
    else:
        if lo:
            kw["min_speakers"] = lo
        if hi:
            kw["max_speakers"] = hi
    t0 = time.time()
    out = pipe({"waveform": w, "sample_rate": sr}, **kw)
    dt = time.time() - t0
    # 겹침 제거 주석을 쓴다(화자별 요약은 구간을 한 화자에게 배정해야 한다).
    ann = (getattr(out, "exclusive_speaker_diarization", None)
           or getattr(out, "speaker_diarization", None) or out)
    turns = [{"start": round(float(t.start), 2), "end": round(float(t.end), 2),
              "speaker": s} for t, _, s in ann.itertracks(yield_label=True)]
    peak = (round(torch.cuda.max_memory_allocated() / 2**20, 1)
            if torch.cuda.is_available() else None)
    return turns, {"audio_sec": round(audio_sec, 1), "elapsed_sec": round(dt, 1),
                   "rtf": round(dt / audio_sec, 3), "peak_MiB": peak,
                   "kwargs": kw}


def main():
    ap = argparse.ArgumentParser()
    mp = load_propnoun()
    ap.add_argument("--meeting", choices=list(mp.MEETINGS), default="c26")
    ap.add_argument("--num-speakers", type=int)
    ap.add_argument("--min-speakers", type=int)
    ap.add_argument("--max-speakers", type=int)
    a = ap.parse_args()
    mp.set_meeting(a.meeting)
    labels = minutes_speakers(mp)
    persons = distinct_persons(labels)
    turns, meta = diarize(mp.WAV, a.num_speakers, a.min_speakers, a.max_speakers)

    spk = {}
    for t in turns:
        d = spk.setdefault(t["speaker"], {"turns": 0, "sec": 0.0})
        d["turns"] += 1
        d["sec"] += t["end"] - t["start"]
    for v in spk.values():
        v["sec"] = round(v["sec"], 1)
    speech = round(sum(v["sec"] for v in spk.values()), 1)
    durs = sorted(t["end"] - t["start"] for t in turns)
    rep = {
        "model": MODEL, "meeting": a.meeting, **meta,
        "n_turns": len(turns), "n_speakers": len(spk),
        "speech_sec": speech,
        "speech_ratio": round(speech / meta["audio_sec"], 3),
        "turn_dur": {"median": round(durs[len(durs) // 2], 2) if durs else None,
                     "p90": round(durs[int(len(durs) * 0.9)], 2) if durs else None,
                     "max": round(durs[-1], 2) if durs else None,
                     "under_1s": sum(1 for d in durs if d < 1.0)},
        "per_speaker": dict(sorted(spk.items(),
                                   key=lambda kv: -kv[1]["sec"])),
        "minutes_speaker_labels": labels,
        "n_minutes_labels": len(labels),
        # 인물 단위(성명 기준). 직책 표기 변이를 접는다 — 위 docstring 참조.
        "minutes_persons": {k: v for k, v in persons.items() if len(v) > 1},
        "n_minutes_persons": len(persons),
        "cluster_minus_persons": len(spk) - len(persons),
        "turns": turns,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"phase3_diarize_{a.meeting}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {p}  turns={len(turns)} clusters={len(spk)} "
          f"persons={len(persons)} speech={speech}s/{meta['audio_sec']}s "
          f"rtf={meta['rtf']}")


if __name__ == "__main__":
    main()
