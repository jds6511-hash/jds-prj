"""[caption model×prompt 2×2 contemporaneous batch — AI Hub 194편·1,086질의]

**사전 등록: `docs/preregistration/caption_2x2_사전등록_2026-08-17.md` (커밋 `c676c46`).**
이 스크립트는 그 문서에 박힌 설계를 그대로 구현한다. 결과를 보고 지표·대비·표본을
바꾸지 않는다.

**왜 4 arm을 전부 새로 만드는가.** 기존 `3B/P0`(08-11)·`4B/P1`(08-10)을 재사용하면
2×2가 배치를 가로지르고, prompt 효과 두 개가 **서로 반대 방향으로** 배치 효과를 받아
interaction에 2배로 실린다. 실측 run-to-run 발산은 dev 655구간에서 8건(1.2%)·
캡션 단독 MRR 0.0124 — 재려는 대비(+0.02~0.04)와 같은 자릿수다. 규약 4항.

**주분석 대비 (사전 등록, 전부 신규 4 arm 내부)**
    C1 prompt at 3B     = 3B/P1 − 3B/P0
    C2 prompt at 4B     = 4B/P1 − 4B/P0
    C3 model under P0   = 4B/P0 − 3B/P0
    C4 model under P1   = 4B/P1 − 3B/P1
    C5 interaction      = (4B/P1 − 3B/P1) − (4B/P0 − 3B/P0)
주지표는 캡션 단독(α=0.0) MRR. BH-FDR q=0.05. 재표집 단위 3종 + ICC 전부 산출.

**표본 재사용 고지.** AI Hub 1,086은 이미 `4B/P1` vs `3B/P0` 확증에 1회 썼다.
이번 결과는 **확증이 아니라 선택·추정**이다. 선택은 A-half, 부호 유지 점검은 B-half
(sha256(video_id) 패리티 — 결과 보기 전 고정 규칙).

**건드리지 않는 것.** work_aihub 인덱스 불변(재임베딩은 메모리에서만).
기존 `aihub_confirm_captions/`는 읽기만 한다 — 신규 산출물은 `aihub_2x2_captions/`.
`results/` 아래 확정 산출물, 본 config, 본 인덱스 전부 불변. test 미접촉.

재현:
    python docs/probes/aihub_caption_2x2.py --canary 4     # 배관 점검
    python docs/probes/aihub_caption_2x2.py                # FULL (승인 후)
"""
import argparse, hashlib, io, json, platform, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m4_index import embed_texts                           # noqa: E402
from m5_search import VideoIndex, combine_scores           # noqa: E402
from caption_model_sweep import MODELS, PROMPTS, load_captioner   # noqa: E402
from aihub_external_eval import load_external_queries      # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
CAPROOT = OUT / "aihub_2x2_captions"          # 신규 전용 — 기존 산출물과 분리
OLDDIR = OUT / "aihub_confirm_captions"       # 부수 분석용, 읽기 전용
CAPDIR = None                                 # run_id별로 main에서 확정
ARMS = [("qwen25_3b", "P0"), ("qwen25_3b", "P1"),
        ("qwen3vl_4b", "P0"), ("qwen3vl_4b", "P1")]
CONTRASTS = [("C1_prompt_at_3B", "qwen25_3b/P1", "qwen25_3b/P0"),
             ("C2_prompt_at_4B", "qwen3vl_4b/P1", "qwen3vl_4b/P0"),
             ("C3_model_under_P0", "qwen3vl_4b/P0", "qwen25_3b/P0"),
             ("C4_model_under_P1", "qwen3vl_4b/P1", "qwen25_3b/P1")]
BASE = "qwen25_3b/P0"                          # configuration effect의 기준 셀

# canary 영상 — 성격이 섞이도록 **기존 산출물만 보고** 고정했다(신규 결과 무관).
# 앞 N편을 그냥 자르면 전부 같은 도메인·같은 성격이라 P0/P1 차이도 I1 검출기도 안 보인다.
CANARY_VIDEOS = [
    ("D3_DR_0922_000266", "I1 적중 이력 (기존 arm에서 오염 2건·CJK 4건)"),
    ("D3_DR_0922_000267", "CJK 포함하나 미적중 — scene text 후보"),
    ("D3_TR_0914_000785", "평범한 여행 장면 (오염 0·CJK 0)"),
    ("D3_FO_0907_000089", "평범한 요리음식 장면 (오염 0·CJK 0)"),
]


def _git(*a) -> str:
    import subprocess
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def half_of(video_id: str) -> str:
    """결과를 보기 전에 고정한 A/B 분할 규칙 — sha256 첫 바이트 패리티."""
    h = hashlib.sha256(video_id.encode("utf-8")).digest()[0]
    return "A" if h % 2 == 0 else "B"


def provenance(cap, mkey: str, pkey: str, cfg: dict) -> dict:
    """실효값 기록. spec만 적으면 2026-08-10 사고(q4 무시)를 다시 놓친다."""
    model = getattr(cap, "model", None)
    conf = getattr(model, "config", None)
    quant = getattr(conf, "quantization_config", None)
    prompt = PROMPTS[pkey]
    prov = {
        "entrypoint": "aihub_caption_2x2",
        "arm": f"{mkey}/{pkey}",
        "spec": MODELS[mkey],
        "model_id_effective": getattr(conf, "_name_or_path", None),
        "model_revision": getattr(conf, "_commit_hash", None),
        "dtype_effective": str(getattr(model, "dtype", None)),
        "quantized_effective": quant is not None,
        "attn_implementation": getattr(conf, "_attn_implementation", None),
        "prompt_key": pkey,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_len": len(prompt),
        # K3: P0에만 있어야 하는 문구. 사람이 눈으로 볼 필요 없게 불리언으로 박는다.
        "prompt_forbids_ocr": "그대로 옮겨 적지 말고" in prompt,
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
    }
    for k in ("vlm_max_pixels", "vlm_max_new_tokens", "vlm_rep_penalty", "vlm_4bit"):
        if k in cfg:
            prov[f"config_{k}"] = cfg[k]
    try:
        import torch, transformers
        prov["torch"] = torch.__version__
        prov["transformers"] = transformers.__version__
        prov["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        pass
    return prov


def gen_arm(mkey, pkey, vids, segs, wdirs, cfg) -> tuple[dict, dict, float]:
    """arm 캡션 생성. 저장분이 있으면 재사용(중단 재개용) — 단 provenance는
    저장분과 함께 보관돼야 하므로 캡션 파일과 같은 곳에 쓴다."""
    f = CAPDIR / f"{mkey}__{pkey}.json"
    pf = CAPDIR / f"{mkey}__{pkey}.provenance.json"
    if f.exists() and pf.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        if all(v in d and len(d[v]) == len(segs[v]) for v in vids):
            print(f"[{mkey}/{pkey}] 저장분 재사용", flush=True)
            return d, json.loads(pf.read_text(encoding="utf-8")), 0.0
    cap, close = load_captioner(MODELS[mkey], cfg)
    prov = provenance(cap, mkey, pkey, cfg)
    t0 = time.time()
    try:
        caps = {}
        for n, v in enumerate(vids, 1):
            caps[v] = [cap(wdirs[v] / s["rep_frame"], PROMPTS[pkey]) for s in segs[v]]
            if n % 20 == 0:
                print(f"  {mkey}/{pkey} {n}/{len(vids)}편 "
                      f"({(time.time()-t0)/60:.1f}분)", flush=True)
    finally:
        close()
    el = time.time() - t0
    n_seg = sum(len(segs[v]) for v in vids)
    prov["elapsed_sec"] = round(el, 1)
    prov["sec_per_segment"] = round(el / n_seg, 3) if n_seg else None
    CAPDIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(caps, ensure_ascii=False), encoding="utf-8")
    pf.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{mkey}/{pkey}] 생성 완료 {el/60:.1f}분 ({prov['sec_per_segment']}초/구간)",
          flush=True)
    return caps, prov, el


def i1_block(caps, vids) -> dict:
    """I1 원자료. 원인은 귀속하지 않는다 — 프레임 미검증(사전등록 §4-2)."""
    def has_cjk(t):
        return any("一" <= c <= "鿿" or "぀" <= c <= "ヿ" for c in t)
    flat = [t for v in vids for t in caps[v]]
    hit = [t for t in flat if common.is_corrupted_caption(t)]
    return {"n_captions": len(flat),
            "I1a_corrupted": len(hit),
            "I1b_cjk_any": sum(1 for t in flat if has_cjk(t)),
            "I1c_corrupted_non_cjk": sum(1 for t in hit if not has_cjk(t)),
            "empty": sum(1 for t in flat if not t.strip()),
            "len_mean": round(float(np.mean([len(t) for t in flat])), 1) if flat else None,
            "samples": hit[:10]}


def rank_of(score, gt) -> int:
    for r, i in enumerate(np.argsort(-score, kind="stable"), 1):
        if int(i) in gt:
            return r
    return 0


def per_query_rows(qs, idx0, caps, q_emb, alpha, cfg) -> list[dict]:
    """질의별 순위·RR·hit@1을 세 α에서. video_id·도메인·half를 함께 싣는다 —
    재표집 단위를 나중에 바꿀 수 있어야 한다(감사_2026-08-17 §3)."""
    cap_emb = {v: embed_texts(caps[v], cfg["embed_model"]) for v in idx0}
    rows = []
    for n, q in enumerate(qs):
        v = q["video_id"]
        vi = idx0[v]
        s_sub, s_cap = vi.emb_sub @ q_emb[n], cap_emb[v] @ q_emb[n]
        gt = set(q["gt_seg_idx"])
        row = {"query_id": q["query_id"], "video_id": v, "domain": q["type"],
               "half": half_of(v), "n_seg": len(vi.segments)}
        for al, name in ((0.0, "cap"), (alpha, "fus"), (1.0, "sub")):
            r = rank_of(combine_scores(s_sub, s_cap, vi.static_mask, al), gt)
            row[f"rank_{name}"] = r
            row[f"rr_{name}"] = 1.0 / r if r else 0.0
            row[f"hit1_{name}"] = 1.0 if r == 1 else 0.0
        rows.append(row)
    return rows


def boot(b, k, groups, B, seed, unit) -> dict:
    """unit: query | video-cluster | video-macro. 셋 다 산출한다(사전등록 §3)."""
    if unit == "query":
        n = len(b)
        ib = np.random.default_rng(seed).integers(0, n, size=(B, n))
        d = k[ib].mean(1) - b[ib].mean(1)
        pt, n_unit = float(k.mean() - b.mean()), n
    else:
        vids = sorted(set(groups))
        g = np.asarray(groups)
        pos = {v: np.flatnonzero(g == v) for v in vids}
        pick = np.random.default_rng(seed).integers(0, len(vids), size=(B, len(vids)))
        macro = unit == "video-macro"

        def stat(arr, ch):
            if macro:
                return float(np.mean([arr[pos[vids[j]]].mean() for j in ch]))
            return float(np.concatenate([arr[pos[vids[j]]] for j in ch]).mean())

        d = np.array([stat(k, r) - stat(b, r) for r in pick])
        pt = (float(np.mean([k[p].mean() for p in pos.values()])
                    - np.mean([b[p].mean() for p in pos.values()]))
              if macro else float(k.mean() - b.mean()))
        n_unit = len(vids)
    lo, hi = (float(x) for x in np.percentile(d, [2.5, 97.5]))
    # BH 보정용 부트스트랩 양측 p — 0을 넘는 재표집 비율 [8-1 계열]
    p = 2 * min((d <= 0).mean(), (d >= 0).mean())
    return {"unit": unit, "n_unit": n_unit, "delta": round(pt, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": bool(lo > 0 or hi < 0),
            "p_boot": round(float(min(max(p, 1.0 / len(d)), 1.0)), 4)}


def bh_fdr(pvals: dict, q: float = 0.05) -> dict:
    """Benjamini-Hochberg. 사전등록 §3 — 보정 전후를 모두 보고한다."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    thr, cut = {}, 0.0
    for i, (k, p) in enumerate(items, 1):
        if p <= i / m * q:
            cut = i / m * q
    for i, (k, p) in enumerate(items, 1):
        thr[k] = {"p_boot": p, "bh_threshold": round(i / m * q, 4),
                  "significant_bh": bool(p <= cut)}
    return {"q": q, "m": m, "per_contrast": thr}


def icc1(rows_b, rows_k, key) -> dict:
    g = {}
    for b, k in zip(rows_b, rows_k):
        g.setdefault(b["video_id"], []).append(k[key] - b[key])
    grp = [np.array(v) for v in g.values() if len(v) > 1]
    allv = np.concatenate(grp)
    n, K, gm = len(allv), len(grp), allv.mean()
    msb = sum(len(x) * (x.mean() - gm) ** 2 for x in grp) / (K - 1)
    msw = sum(((x - x.mean()) ** 2).sum() for x in grp) / (n - K)
    m = float(np.mean([len(x) for x in grp]))
    icc = (msb - msw) / (msb + (m - 1) * msw)
    return {"icc1": round(float(icc), 4),
            "design_effect": round(1 + (m - 1) * float(icc), 3)}


def divergence_vs_old(caps_new, vids, mkey, pkey) -> dict | None:
    """부수 분석 — 같은 arm의 과거 산출물과 완전일치율. 판정에 쓰지 않는다."""
    f = OLDDIR / f"{mkey}__{pkey}.json"
    if not f.is_file():
        return None
    old = json.loads(f.read_text(encoding="utf-8"))
    same = tot = 0
    for v in vids:
        if v not in old or len(old[v]) != len(caps_new[v]):
            return {"comparable": False, "reason": f"세그먼트 수 불일치 ({v})"}
        for a, b in zip(old[v], caps_new[v]):
            tot += 1
            same += (a == b)
    return {"comparable": True, "n": tot, "exact_match": round(same / tot, 4),
            "differing": tot - same, "old_file": f.name}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--queries", default="data_aihub/queries/queries_aihub.jsonl")
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--canary", action="store_true",
                    help="배관 점검 전용 — CANARY_VIDEOS 4편만. 결과를 보고하지 않는다")
    ap.add_argument("--run-id", default=None,
                    help="FULL 실행 필수. 산출물을 aihub_2x2_captions/<run_id>/ 로 분리한다 "
                         "— canary 산출물과 과거 실행을 덮지 않기 위해")
    ap.add_argument("--out", default="aihub_caption_2x2.json")
    a = ap.parse_args()

    global CAPDIR
    if a.canary:
        a.out = f"_canary_{a.out}"
        run_id = a.run_id or "canary"
    else:
        assert a.run_id, "FULL 실행은 --run-id 필수 (덮어쓰기 방지)"
        run_id = a.run_id
        a.out = f"{Path(a.out).stem}_{run_id}.json"
    CAPDIR = CAPROOT / run_id

    # K10: 신규 산출물 경로가 기존 자산과 절대 겹치지 않아야 한다. 기존 5개 파일은
    # run-to-run 비교용 자산이라 덮으면 복구 불가다. 경로 분리를 실행 전에 단언한다.
    assert CAPDIR.resolve() != OLDDIR.resolve(), "K10: 신규/기존 캡션 경로가 같다"
    assert CAPROOT.resolve() != OLDDIR.resolve(), "K10: 신규 루트가 기존 자산 경로다"
    for m, p in ARMS:
        assert (CAPDIR / f"{m}__{p}.json").resolve() \
            != (OLDDIR / f"{m}__{p}.json").resolve(), f"K10: {m}/{p} 경로 충돌"
    # 다른 run_id의 산출물도 덮지 않는다 — CAPDIR가 이미 있고 완료 마커까지 있으면 정지
    if (CAPDIR / "RUN_COMPLETE.json").is_file():
        raise SystemExit(f"이미 완료된 run_id다: {CAPDIR} — 다른 --run-id를 쓰라")
    pre_old = ({f.name: f.stat().st_mtime_ns for f in sorted(OLDDIR.iterdir())}
               if OLDDIR.is_dir() else {})

    t_start = time.time()
    print("=" * 72, flush=True)
    print("caption model×prompt 2×2 contemporaneous batch", flush=True)
    print("  목적: configuration / model / prompt effect 분해.", flush=True)
    print("  **test 재평가도 배포 채택도 아니다.** AI Hub/probe 실험이며,", flush=True)
    print("  8회차 HOLD 판정(I1·A2 FAIL)과 test 미접촉 상태는 그대로 유지된다.", flush=True)
    print(f"  사전등록: docs/preregistration/caption_2x2_사전등록_2026-08-17.md", flush=True)
    print(f"  {'CANARY' if a.canary else 'FULL'} execution commit = "
          f"{_git('rev-parse', 'HEAD')[:7]} (dirty={bool(_git('status', '--porcelain'))})",
          flush=True)
    print(f"  run_id = {run_id}   산출물 = {CAPDIR}", flush=True)
    print(f"  시작 = {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"  완료 마커 = {CAPDIR / 'RUN_COMPLETE.json'}", flush=True)
    print(f"  arm별 마커 = {CAPDIR}/<arm>.provenance.json", flush=True)
    print(f"  기존 자산 {len(pre_old)}개는 read-only — {OLDDIR.name}/", flush=True)
    print("=" * 72, flush=True)

    cfg = common.load_config(str(ROOT / a.config))
    alpha = a.alpha
    if alpha is None:
        p = ROOT / "results/alpha_search_dev.json"
        alpha = json.loads(p.read_text(encoding="utf-8"))["alpha_star"] if p.exists() else 0.5

    qs_all = load_external_queries(ROOT / a.queries)
    want = sorted({q["video_id"] for q in qs_all})
    if a.canary:
        want = [v for v, _ in CANARY_VIDEOS]
        missing = [v for v in want if v not in {q["video_id"] for q in qs_all}]
        assert not missing, f"canary 영상이 질의셋에 없다: {missing}"
    idx0 = {}
    for v in want:
        try:
            idx0[v] = VideoIndex.load(cfg, v)
        except Exception:
            pass
    assert idx0, "인덱스가 하나도 없다"
    qs = [q for q in qs_all if q["video_id"] in idx0]
    vids = sorted(idx0)
    segs = {v: idx0[v].segments for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}
    n_seg = sum(len(segs[v]) for v in vids)
    print(f"영상 {len(vids)}편 · 구간 {n_seg} · 질의 {len(qs)}건 · α={alpha}"
          f"{' [CANARY]' if a.canary else ''}", flush=True)

    rep = {"prereg": "docs/preregistration/caption_2x2_사전등록_2026-08-17.md",
           "note": ("확증 아님 — 표본 재사용(AI Hub 1,086은 4B/P1 vs 3B/P0 확증에 "
                    "1회 사용됨). 선택·추정으로만 보고한다. work_aihub 불변, test 미접촉."),
           "canary": a.canary, "n_videos": len(vids), "n_queries": len(qs),
           "n_segments": n_seg, "alpha_fused": alpha, "seed": cfg["seed"],
           "bootstrap_B": cfg["bootstrap_B"], "embed_model": cfg["embed_model"],
           "git_head": _git("rev-parse", "HEAD"),
           "git_dirty": bool(_git("status", "--porcelain")),
           "halves": {h: sum(1 for v in vids if half_of(v) == h) for h in ("A", "B")},
           "arms": {}, "provenance": {}, "i1": {}, "divergence_vs_old": {}}

    q_emb = embed_texts([q["text"] for q in qs], cfg["embed_model"])
    pq = {}
    for mkey, pkey in ARMS:
        arm = f"{mkey}/{pkey}"
        caps, prov, _ = gen_arm(mkey, pkey, vids, segs, wdirs, cfg)
        rep["provenance"][arm] = prov
        rep["i1"][arm] = i1_block(caps, vids)
        rep["divergence_vs_old"][arm] = divergence_vs_old(caps, vids, mkey, pkey)
        pq[arm] = per_query_rows(qs, idx0, caps, q_emb, alpha, cfg)
        rep["arms"][arm] = {k: round(float(np.mean([r[f"rr_{k}"] for r in pq[arm]])), 4)
                            for k in ("cap", "fus", "sub")}
        print(f"[{arm}] MRR 캡션단독 {rep['arms'][arm]['cap']} "
              f"융합 {rep['arms'][arm]['fus']} · I1a {rep['i1'][arm]['I1a_corrupted']}",
              flush=True)

    # ── 사전 등록 대비 ────────────────────────────────────────────────────────
    groups = [r["video_id"] for r in pq[ARMS[0][0] + "/" + ARMS[0][1]]]
    B, seed = cfg["bootstrap_B"], cfg["seed"]
    rep["contrasts"], pv = {}, {}
    for name, hi_arm, lo_arm in CONTRASTS:
        blk = {"high": hi_arm, "low": lo_arm}
        for metric, key in (("caption_only", "rr_cap"), ("fused", "rr_fus")):
            b = np.array([r[key] for r in pq[lo_arm]])
            k = np.array([r[key] for r in pq[hi_arm]])
            blk[metric] = {u: boot(b, k, groups, B, seed, u)
                           for u in ("query", "video-cluster", "video-macro")}
        blk["icc_caption_only"] = icc1(pq[lo_arm], pq[hi_arm], "rr_cap")
        rep["contrasts"][name] = blk
        pv[name] = blk["caption_only"]["query"]["p_boot"]     # 주지표 기준

    # C5 interaction — 쌍체 차이의 차이. 질의 단위로만 낸다(정의상 4 arm 결합)
    d_p1 = (np.array([r["rr_cap"] for r in pq["qwen3vl_4b/P1"]])
            - np.array([r["rr_cap"] for r in pq["qwen25_3b/P1"]]))
    d_p0 = (np.array([r["rr_cap"] for r in pq["qwen3vl_4b/P0"]])
            - np.array([r["rr_cap"] for r in pq["qwen25_3b/P0"]]))
    n = len(d_p1)
    ib = np.random.default_rng(seed).integers(0, n, size=(B, n))
    dd = (d_p1 - d_p0)[ib].mean(1)
    lo, hi = (float(x) for x in np.percentile(dd, [2.5, 97.5]))
    p5 = 2 * min((dd <= 0).mean(), (dd >= 0).mean())
    rep["contrasts"]["C5_interaction"] = {
        "definition": "(4B/P1 − 3B/P1) − (4B/P0 − 3B/P0), 캡션 단독",
        "caption_only": {"query": {
            "unit": "query", "n_unit": n,
            "delta": round(float((d_p1 - d_p0).mean()), 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": bool(lo > 0 or hi < 0),
            "p_boot": round(float(min(max(p5, 1.0 / B), 1.0)), 4)}}}
    pv["C5_interaction"] = rep["contrasts"]["C5_interaction"]["caption_only"]["query"]["p_boot"]
    rep["bh_fdr"] = bh_fdr(pv)

    # ── configuration effect: 각 셀 vs 기준 셀 ────────────────────────────────
    rep["configuration_effect_vs_base"] = {}
    for arm in [f"{m}/{p}" for m, p in ARMS]:
        if arm == BASE:
            continue
        b = np.array([r["rr_cap"] for r in pq[BASE]])
        k = np.array([r["rr_cap"] for r in pq[arm]])
        rep["configuration_effect_vs_base"][arm] = {
            u: boot(b, k, groups, B, seed, u)
            for u in ("query", "video-cluster", "video-macro")}

    # ── A/B 절반: 선택은 A, 부호 유지 점검은 B ────────────────────────────────
    rep["halves_detail"] = {}
    for h in ("A", "B"):
        sel = [i for i, r in enumerate(pq[BASE]) if r["half"] == h]
        g = [pq[BASE][i]["video_id"] for i in sel]
        blk = {}
        for arm in [f"{m}/{p}" for m, p in ARMS]:
            if arm == BASE:
                continue
            b = np.array([pq[BASE][i]["rr_cap"] for i in sel])
            k = np.array([pq[arm][i]["rr_cap"] for i in sel])
            blk[arm] = boot(b, k, g, B, seed, "video-cluster")
        rep["halves_detail"][h] = {"n_queries": len(sel), "vs_base": blk}

    # K10 사후 확인 — 경로 분리 단언만으로는 부족하다. 실제로 안 바뀌었는지 본다.
    post_old = ({f.name: f.stat().st_mtime_ns for f in sorted(OLDDIR.iterdir())}
                if OLDDIR.is_dir() else {})
    rep["K10_old_artifacts_intact"] = {
        "checked": len(pre_old), "unchanged": pre_old == post_old,
        "changed_files": [k for k in set(pre_old) | set(post_old)
                          if pre_old.get(k) != post_old.get(k)]}
    assert pre_old == post_old, (
        f"K10 위반: 기존 산출물이 변경됐다 — {rep['K10_old_artifacts_intact']['changed_files']}")

    rep["canary_videos"] = [{"video_id": v, "why": w} for v, w in CANARY_VIDEOS] \
        if a.canary else None

    # ── validator — 완료 판정은 프로세스 존재 여부가 아니라 이것으로 한다 ──────
    checks = {
        "arms_present": sorted(rep["arms"]) == sorted(f"{m}/{p}" for m, p in ARMS),
        "provenance_per_arm": len(rep["provenance"]) == len(ARMS),
        "captions_per_arm_match_segments": all(
            rep["i1"][f"{m}/{p}"]["n_captions"] == n_seg for m, p in ARMS),
        "per_query_rows_match_queries": all(len(v) == len(qs) for v in pq.values()),
        "no_empty_captions": all(rep["i1"][f"{m}/{p}"]["empty"] == 0 for m, p in ARMS),
        "K10_old_artifacts_unchanged": rep["K10_old_artifacts_intact"]["unchanged"],
        "git_not_dirty": not rep["git_dirty"],
        "prompt_hashes_distinct_by_key": (
            len({rep["provenance"][f"{m}/P0"]["prompt_sha256"] for m, _ in ARMS}) == 1
            and len({rep["provenance"][f"{m}/P1"]["prompt_sha256"] for m, _ in ARMS}) == 1
            and rep["provenance"][f"{ARMS[0][0]}/P0"]["prompt_sha256"]
            != rep["provenance"][f"{ARMS[0][0]}/P1"]["prompt_sha256"]),
        "P0_forbids_ocr_P1_not": all(
            rep["provenance"][f"{m}/P0"]["prompt_forbids_ocr"]
            and not rep["provenance"][f"{m}/P1"]["prompt_forbids_ocr"]
            for m, _ in ARMS),
        "all_bf16_unquantized": all(
            not rep["provenance"][f"{m}/{p}"]["quantized_effective"] for m, p in ARMS),
    }
    rep["validator"] = {"checks": checks, "PASS": all(checks.values()),
                        "failed": [k for k, v in checks.items() if not v]}
    rep["elapsed_sec"] = round(time.time() - t_start, 1)
    rep["run_id"] = run_id
    rep["per_query"] = pq
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / a.out
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 대비 (캡션 단독, 질의 단위) ===")
    for name in list(dict.fromkeys([c[0] for c in CONTRASTS] + ["C5_interaction"])):
        c = rep["contrasts"][name]["caption_only"]["query"]
        bh = rep["bh_fdr"]["per_contrast"][name]
        print(f"  {name:20s} Δ{c['delta']:+.4f} CI{c['ci95']} "
              f"p={c['p_boot']:.4f} BH={'유의' if bh['significant_bh'] else '비유의'}")
    v = rep["validator"]
    print(f"\nvalidator: {'PASS' if v['PASS'] else 'FAIL ' + str(v['failed'])}")
    print(f"소요 {rep['elapsed_sec']/3600:.2f}시간 · 종료 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("->", p)
    # 완료 마커는 **validator PASS일 때만** 쓴다 — 마커 존재가 곧 성공 판정이다
    if v["PASS"]:
        (CAPDIR / "RUN_COMPLETE.json").write_text(json.dumps({
            "run_id": run_id, "canary": bool(a.canary),
            "git_head": rep["git_head"], "n_videos": rep["n_videos"],
            "n_segments": n_seg, "n_queries": rep["n_queries"],
            "arms": sorted(rep["arms"]), "elapsed_sec": rep["elapsed_sec"],
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "result_file": str(p), "validator_PASS": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("완료 마커:", CAPDIR / "RUN_COMPLETE.json")
    else:
        raise SystemExit(f"validator FAIL — 완료 마커를 쓰지 않는다: {v['failed']}")


if __name__ == "__main__":
    main()
