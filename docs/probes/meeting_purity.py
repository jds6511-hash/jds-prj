"""Phase 3-b — 화자분리 **클러스터 순도**. 회의록 화자 라벨을 정답 축으로 쓴다.

DER의 대체물이 아니다. 회의록에 타임스탬프가 없어 프레임 단위 정답을 만들 수 없으므로
(작업현황 Phase 3 측정 한계), "회의록이 같은 사람의 발언으로 표시한 지점들이 실제로
같은 클러스터에 떨어지는가"만 잰다. Phase 4(화자별 요약)가 이 배정에 의존한다.

────────────────────────────── 사전 등록 프로토콜 (결과 보기 전 확정) ─────────────────

**앵커 구성** — 동결된 고유명사 타깃(`phase2_targets_*.json`)을 위치 앵커로 쓴다.
Phase 2에서 "실제로 발화됐다"가 검증된 문자열이라 새로 고르지 않는다. 필터 4개:
  A1. 회의록 발화 구간에서 **정확히 한 문단**에만 나타날 것 → 화자 귀속·위치가 유일.
  A2. 정규화 길이 **6자 이상** → 짧은 문자열의 우연 일치 배제.
  A3. 전사문에 **정확히 한 번** 부분문자열로 나타날 것(근사 매칭 금지 — 거리 0만).
      근사 위치는 신뢰할 수 없으므로 Phase 2의 τ 규칙을 여기서는 쓰지 않는다.
  A4. 해당 전사 세그먼트와 겹치는 화자 턴이 있을 것(겹침 0이면 배정 불가로 탈락).

**시각 해석** — 전사는 `src.m3_generate.transcribe`(운영 코드 그대로, `{text,t0,t1}`)를
쓴다. 앵커 매칭 위치의 중점이 속한 세그먼트를 잡고, 그 `[t0,t1]`과 겹침이 최대인
클러스터를 배정한다. **세그먼트 단위 해상도가 상한을 만든다** — 세그먼트가 화자 전환을
걸치면 배정이 틀릴 수 있다.

**지표** — 회의록 인물 s(앵커 2건 이상)에 대해 purity_s = (최다 클러스터 앵커 수)/(앵커 수).
합산은 앵커 가중 평균 = Σmax / Σn. 역방향(클러스터→인물)도 병기한다.

**우연 기저** — 관측된 클러스터 라벨을 앵커 사이에서 **무작위 재배치**(shuffle, seed 42,
1000회)해 같은 지표를 계산한다. 클러스터 주변분포를 정확히 보존한다. 순도는 인물당
앵커 수가 적으면 우연히도 높게 나오므로 이 기저 없이는 해석 불가다.
보고: 기저 평균과 95백분위. **관측치가 95백분위를 넘지 못하면 "순도 있음"을 주장하지 않는다.**

**해석 한계 (미리 적어둔다)**
  · 회의록은 개조식 요약이라 인용·복창을 구분하지 못한다. A가 B의 발언을 되짚으면
    타깃이 A 문단에 있어도 실제 발화자는 B일 수 있다 → 순도의 상한을 깎는다.
  · 회의록 인물 수 자체가 상한값이다(동일인 표기 변이 — meeting_diarize 참조).
  · 앵커는 고유명사에 편중된다. 고유명사가 없는 발언 구간은 측정되지 않는다.

실행:
  python3 docs/probes/meeting_purity.py                # 3편 전부
  python3 docs/probes/meeting_purity.py --meeting c26
"""
import argparse, importlib.util, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
MIN_NORM_LEN = 6            # A2
N_PERM = 1000


def load_propnoun():
    p = Path(__file__).with_name("meeting_propnoun.py")
    spec = importlib.util.spec_from_file_location("meeting_propnoun", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def paragraph_owners(mp) -> list[tuple[str, str]]:
    """발화 구간을 (화자 성명, 문단) 목록으로 되돌린다.

    `spoken_portion()`은 화자 라벨 줄과 발언 문단을 순서대로 섞어 내보낸다.
    라벨을 만나면 현재 화자를 갱신하고, 이후 문단은 그 화자 것이다.
    성명(마지막 토큰)으로 식별한다 — 직책 표기 변이를 접기 위해(meeting_diarize 참조).
    """
    out, cur = [], None
    for line in mp.spoken_portion().split("\n"):
        t = line.strip()
        if not t:
            continue
        if mp._LABEL.match(t):
            cur = t.lstrip("•ㅇo○ ").strip().split()[-1]
            continue
        if cur:
            out.append((cur, t))
    return out


def build_anchors(mp, utts):
    """사전 등록 필터 A1~A4를 적용해 (앵커, 탈락 사유 집계)를 돌려준다."""
    tg = json.loads(mp.TARGETS.read_text(encoding="utf-8"))
    paras = paragraph_owners(mp)

    # 정규화 전사문 + 문자 오프셋 → 세그먼트 인덱스
    spans, buf = [], []
    pos = 0
    for i, u in enumerate(utts):
        n = mp.norm(u["text"])
        if not n:
            continue
        buf.append(n)
        spans.append((pos, pos + len(n), i))
        pos += len(n)
    hay = "".join(buf)

    def seg_of(off):
        for a, b, i in spans:
            if a <= off < b:
                return i
        return None

    anchors, drop = [], {"A1_multi_para": 0, "A2_short": 0,
                         "A3_not_unique": 0, "A4_no_turn": 0}
    for t in tg["targets"]:
        raw = t["text"]
        owners = {sp for sp, para in paras if raw in para}
        n_para = sum(1 for _, para in paras if raw in para)
        if n_para != 1 or len(owners) != 1:            # A1
            drop["A1_multi_para"] += 1
            continue
        nt = mp.norm(raw)
        if len(nt) < MIN_NORM_LEN:                     # A2
            drop["A2_short"] += 1
            continue
        first = hay.find(nt)
        if first < 0 or hay.find(nt, first + 1) >= 0:   # A3
            drop["A3_not_unique"] += 1
            continue
        seg = seg_of(first + len(nt) // 2)
        if seg is None:
            drop["A3_not_unique"] += 1
            continue
        anchors.append({"text": raw, "cat": t["cat"], "owner": owners.pop(),
                        "seg": seg, "t0": utts[seg]["t0"], "t1": utts[seg]["t1"]})
    return anchors, drop, len(tg["targets"])


def assign_clusters(anchors, turns, drop):
    """세그먼트 구간과 겹침이 최대인 클러스터를 배정(A4)."""
    kept = []
    for a in anchors:
        best, bo = None, 0.0
        for t in turns:
            ov = min(a["t1"], t["end"]) - max(a["t0"], t["start"])
            if ov > bo:
                best, bo = t["speaker"], ov
        if best is None:
            drop["A4_no_turn"] += 1
            continue
        kept.append({**a, "cluster": best, "overlap_sec": round(bo, 2)})
    return kept


def purity(pairs, key_i, key_j):
    """(key_i → 최다 key_j) 가중 순도. pairs = [(i, j), ...]"""
    grp = {}
    for i, j in pairs:
        grp.setdefault(i, []).append(j)
    num = den = 0
    per = {}
    for i, js in grp.items():
        if len(js) < 2:
            continue
        top = max(js.count(x) for x in set(js))
        per[i] = {"n": len(js), "top": top, "purity": round(top / len(js), 3),
                  "n_clusters": len(set(js))}
        num += top
        den += len(js)
    return (round(num / den, 4) if den else None), den, per


def perm_baseline(pairs):
    """관측 클러스터 라벨을 앵커 사이에서 무작위 재배치. 주변분포 보존."""
    rnd = random.Random(SEED)
    owners = [i for i, _ in pairs]
    labels = [j for _, j in pairs]
    vals = []
    for _ in range(N_PERM):
        sh = labels[:]
        rnd.shuffle(sh)
        v, _d, _p = purity(list(zip(owners, sh)), "owner", "cluster")
        if v is not None:
            vals.append(v)
    vals.sort()
    return {"mean": round(sum(vals) / len(vals), 4),
            "p95": round(vals[int(len(vals) * 0.95)], 4),
            "max": round(vals[-1], 4), "n_perm": len(vals)}


def run_meeting(mp, key):
    mp.set_meeting(key)
    # src/는 평면 임포트(`import common`)라 ROOT가 아니라 src를 경로에 넣어야 한다.
    sys.path.insert(0, str(ROOT / "src"))
    from m3_generate import transcribe              # 운영 전사 코드 그대로
    utts = transcribe(mp.WAV)
    dp = OUT / f"phase3_diarize_{key}.json"
    if not dp.exists():
        raise SystemExit(f"화자분리 결과 없음: {dp} (meeting_diarize.py 먼저)")
    dia = json.loads(dp.read_text(encoding="utf-8"))

    anchors, drop, n_tg = build_anchors(mp, utts)
    anchors = assign_clusters(anchors, dia["turns"], drop)
    pairs = [(a["owner"], a["cluster"]) for a in anchors]
    fwd, n_fwd, per_owner = purity(pairs, "owner", "cluster")
    rev, n_rev, per_cluster = purity([(c, o) for o, c in pairs],
                                    "cluster", "owner")
    base = perm_baseline(pairs) if n_fwd else None
    return {
        "meeting": key, "n_targets": n_tg, "n_anchors": len(anchors),
        "dropped": drop,
        "n_utts": len(utts), "audio_sec": dia["audio_sec"],
        "n_clusters": dia["n_speakers"], "n_persons": dia["n_minutes_persons"],
        "owner_purity": fwd, "n_scored_owner": n_fwd,
        "cluster_purity": rev, "n_scored_cluster": n_rev,
        "perm_baseline_owner": base,
        "per_owner": per_owner, "per_cluster": per_cluster,
        "anchors": anchors,
    }


def main():
    ap = argparse.ArgumentParser()
    mp = load_propnoun()
    ap.add_argument("--meeting", choices=list(mp.MEETINGS))
    a = ap.parse_args()
    keys = [a.meeting] if a.meeting else list(mp.MEETINGS)

    per, allpairs = {}, []
    for k in keys:
        r = run_meeting(mp, k)
        per[k] = r
        allpairs += [(f'{k}:{x["owner"]}', x["cluster"]) for x in r["anchors"]]
        print(f'[{k}] anchors={r["n_anchors"]}/{r["n_targets"]} '
              f'owner_purity={r["owner_purity"]} '
              f'base_p95={(r["perm_baseline_owner"] or {}).get("p95")}')

    # 합산: 회의별 인물은 서로 다른 사건이므로 회의 키를 접두로 붙여 합친다.
    fwd, n_fwd, _ = purity(allpairs, "owner", "cluster")
    rep = {
        "note": "DER 아님. 회의록 화자 라벨 기준 클러스터 순도. 프로토콜은 docstring.",
        "seed": SEED, "min_norm_len": MIN_NORM_LEN, "n_perm": N_PERM,
        "pooled": {"owner_purity": fwd, "n_scored": n_fwd,
                   "perm_baseline": perm_baseline(allpairs) if n_fwd else None},
        "per_meeting": {k: {x: v for x, v in r.items() if x != "anchors"}
                        for k, r in per.items()},
        "anchors": {k: r["anchors"] for k, r in per.items()},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "phase3_purity.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'-> {p}  pooled owner_purity={fwd} (n={n_fwd}) '
          f'base_p95={(rep["pooled"]["perm_baseline"] or {}).get("p95")}')


if __name__ == "__main__":
    main()
