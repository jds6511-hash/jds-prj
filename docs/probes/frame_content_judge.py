"""[실패 질의의 정답 프레임에 내용이 있는가 — 다중 판정자 2지선다. 결과 전 커밋]

**v1의 결함을 고친 것이다.** v1(frame_content_diagnosis.py)은 캡션을 만든 모델과
**같은 3B**에게 예/아니오로 물었다. 순환이다 — 캡셔너가 못 봐서 안 쓴 내용을
같은 가중치의 판정자도 못 보고 "없다"고 답한다. 진단이 가장 알고 싶은 사례에서
정확히 틀린다.

**고친 것 3가지.**

  ② **판정자를 계열별로 복수.** Qwen3-VL(생성) + VARCO(Llava 계열, 생성) +
     한국어 CLIP(**대조학습, 비생성**). 목적함수가 다른 판정자를 섞어야 오차가
     상관되지 않는다. 캡션을 만든 3B는 판정에서 뺀다.
  ③ **예/아니오 대신 2지선다.** 정답 프레임과 같은 영상의 무작위 비정답 프레임을
     **같이** 주고 고르게 한다. "예" 선택지가 없어 아부 편향이 원천 차단되고,
     **우연 수준이 정확히 0.5**다(추정할 필요가 없다). 제시 순서를 질의마다
     무작위로 뒤집어 위치 편향도 통제한다.
     CLIP 판정자는 두 프레임의 유사도를 직접 비교하므로 같은 2지선다가 된다.
  ④ **판정자를 먼저 검정한다.** 답을 아는 문항으로 관문을 통과해야 판정에 쓴다.
     - 양성 대조: **성공 질의**(현행이 이미 1위로 찾은 것) × 정답 vs 무작위.
       내용이 프레임에 있는 것이 확실하므로 정답을 골라야 한다.
     - 하드 네거티브: **다른 영상의 질의** × 이 영상의 두 프레임. 어느 쪽도
       정답이 아니므로 **0.5 근처**여야 한다. 한쪽으로 쏠리면 내용이 아니라
       구도·밝기 같은 것을 보고 있다는 뜻이다.

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-09).**
  - **판정자 관문**: 양성 대조 정답률 **≥ 0.75**이고 하드 네거티브가
    **0.35~0.65** 안이어야 그 판정자를 쓴다. 못 넘기면 그 판정자는 **제외**하고
    제외 사실을 결과에 남긴다. 남은 판정자가 2개 미만이면 **"판정 불가"** 로 끝낸다.
  - **항목별 판정**: 통과한 판정자 전원이 **만장일치**일 때만 확정한다.
    * 전원 정답 프레임 선택 → **(가) 프레임에 있다** — 캡션 모델·프롬프트가 병목
    * 전원 무작위 프레임 선택 → **(나) 프레임에 없다** — M2·해상도가 병목
    * 갈리면 → **판정 불가**. 다수결로 밀지 않는다.
  - **집계 판정**: 확정된 항목 중 (가) 비율이 **≥ 0.6이면 캡션 모델 방향 유지**,
    **≤ 0.4이면 M2·해상도로 우선순위 이동**, 그 사이면 **혼재**.
    판정 불가 비율도 반드시 병기한다.
  - 갈린 항목은 **사람 확인용 맹검 키트**로 내보낸다(`--human-kit`). 모델 합의로
    안 되는 것을 억지로 판정하지 않는다.

**해상도 2조건(선택).** `--full-res`를 주면 축소 없이 원본으로 한 번 더 판정한다.
원본에서는 보이는데 축소본에서 안 보이면 병목은 M2가 아니라 **max_pixels**다.

work/·results/ 불변, test 미접촉.
재현: python docs/probes/frame_content_judge.py [--full-res] [--human-kit]
"""
import argparse, csv, io, json, random, sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs/probes"))
import common                                              # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
SEED = 42
# 캡션을 만든 qwen25_3b_4bit는 **판정에서 뺀다**(순환 방지).
GEN_JUDGES = ["qwen3vl_4b", "varco_1_7b"]
CLIP_ID = "Bingsu/clip-vit-large-patch14-ko"
ASK2 = ('사진 1과 사진 2 중 다음 설명에 맞는 것은 무엇입니까?\n"{q}"\n'
        '"1" 또는 "2" 숫자 하나로만 답하시오.')
GATE_POS, GATE_NEG_LO, GATE_NEG_HI = 0.75, 0.35, 0.65


def pick(ans: str):
    """생성 판정자의 답에서 1/2만 뽑는다. 못 읽으면 None(기권)."""
    for ch in (ans or "")[:12]:
        if ch in "12":
            return int(ch)
    return None


def load_gen_judge(spec, maxpx):
    """2지선다용 **다중 이미지** 판정자. caption_model_sweep의 cap()은 경로 1개만
    받아서 못 쓴다. 실행 중인 스윕 파일을 건드리지 않으려고 여기에 따로 둔다.

    반환: judge(images: list[PIL], prompt) -> str, closer
    """
    import gc
    import torch
    fam, mid = spec["family"], spec["id"]
    if fam == "qwen3vl":
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            mid, dtype=torch.bfloat16, device_map={"": 0}).eval()
        proc = AutoProcessor.from_pretrained(mid, min_pixels=256 * 28 * 28,
                                             max_pixels=maxpx)
        cast = None
    elif fam == "varco":
        from transformers import LlavaOnevisionForConditionalGeneration, AutoProcessor
        model = LlavaOnevisionForConditionalGeneration.from_pretrained(
            mid, dtype=torch.float16, attn_implementation="sdpa",
            device_map={"": 0}).eval()
        proc = AutoProcessor.from_pretrained(mid)
        cast = torch.float16
    else:
        raise ValueError(f"판정자로 지원하지 않는 계열: {fam}")

    def judge(images, prompt):
        content = [{"type": "image", "image": im} for im in images]
        content.append({"type": "text", "text": prompt})
        inputs = proc.apply_chat_template(
            [{"role": "user", "content": content}], tokenize=True,
            add_generation_prompt=True, return_dict=True, return_tensors="pt")
        inputs = inputs.to(model.device, cast) if cast else inputs.to(model.device)
        with torch.inference_mode():
            g = model.generate(**inputs, max_new_tokens=6, do_sample=False)
        return proc.batch_decode(g[:, inputs["input_ids"].shape[1]:],
                                 skip_special_tokens=True)[0].strip()

    def close():
        nonlocal model, proc                 # del은 UnboundLocalError를 낸다
        model = proc = None
        gc.collect(); torch.cuda.empty_cache()

    return judge, close


def load_clip():
    """비생성 판정자. 로드 실패 시 None — 판정자 하나가 빠질 뿐 전체는 진행."""
    try:
        import torch
        from transformers import AutoModel, AutoProcessor
        m = AutoModel.from_pretrained(CLIP_ID).eval().cuda()
        p = AutoProcessor.from_pretrained(CLIP_ID)

        def judge(imgs, query):
            with torch.inference_mode():
                x = p(text=[query], images=imgs, return_tensors="pt",
                      padding=True, truncation=True).to("cuda")
                out = m(**x)
                sims = out.logits_per_text[0]          # (2,)
            return int(sims.argmax().item()) + 1
        return judge, lambda: None
    except Exception as e:
        print(f"[clip] 로드 실패 — 판정자에서 제외: {type(e).__name__}: {e}", flush=True)
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-res", action="store_true",
                    help="축소 없이 원본 해상도로도 판정(해상도 병목 분리)")
    ap.add_argument("--human-kit", action="store_true",
                    help="판정이 갈린 항목만 사람 확인용 맹검 키트로 내보낸다")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}

    per_q = evaluate(dev, base, 0.0, cfg)["per_query"]
    rank1 = {r["query_id"]: (r["rank"] == 1) for r in per_q}
    failed = [q for q in dev if not rank1[q["query_id"]]]
    succ = [q for q in dev if rank1[q["query_id"]]]
    print(f"실패 {len(failed)} / 성공 {len(succ)}", flush=True)

    rng = random.Random(SEED)

    def pair_for(q, cross=False):
        """(프레임 경로 2개, 정답이 몇 번인지). cross=True면 정답이 없다(하드 네거티브)."""
        v = q["video_id"]
        segs, gt = base[v].segments, set(q["gt_seg_idx"])
        pool = [i for i in range(len(segs)) if i not in gt]
        if cross:
            i1, i2 = rng.sample(pool, 2)
            return (wdirs[v] / segs[i1]["rep_frame"],
                    wdirs[v] / segs[i2]["rep_frame"]), None
        gi = q["gt_seg_idx"][0]
        ri = rng.choice(pool)
        gt_f = wdirs[v] / segs[gi]["rep_frame"]
        rd_f = wdirs[v] / segs[ri]["rep_frame"]
        if rng.random() < 0.5:                     # 위치 편향 통제
            return (gt_f, rd_f), 1
        return (rd_f, gt_f), 2

    # 하드 네거티브: 다른 영상의 질의를 이 영상 프레임 쌍에 붙인다
    cross_items = []
    for q in failed:
        other = [x for x in dev if x["video_id"] != q["video_id"]]
        cross_items.append((rng.choice(other)["text"], q))

    # MODELS·_resize만 빌려 쓴다. load_captioner의 cap()은 경로 1개만 받아
    # 2지선다에 못 쓰므로 이 파일의 load_gen_judge를 쓴다.
    from caption_model_sweep import MODELS, _resize        # noqa: E402
    maxpx = cfg["vlm_max_pixels"]

    def open_pair(paths, full):
        return [Image.open(p).convert("RGB") if full
                else _resize(Image.open(p).convert("RGB"), maxpx) for p in paths]

    conds = [("capped", False)] + ([("full", True)] if a.full_res else [])
    rep = {"note": "dev-only, 채택 아님. 다중 판정자 2지선다. test 미접촉.",
           "prereg": {"gate": f"양성 ≥{GATE_POS}, 하드네거티브 {GATE_NEG_LO}~{GATE_NEG_HI}",
                      "item_rule": "통과 판정자 만장일치일 때만 확정, 갈리면 판정 불가",
                      "aggregate": "(가) 비율 ≥0.6 캡션 방향 / ≤0.4 M2·해상도 / 사이는 혼재",
                      "declared_before_run": True},
           "judges_planned": GEN_JUDGES + [CLIP_ID], "seed": SEED,
           "n_failed": len(failed), "n_success": len(succ), "by_condition": {}}

    for cname, full in conds:
        votes = {}          # judge -> {query_id: 정답을 골랐나(bool|None)}
        gate = {}
        for jkey in GEN_JUDGES:
            try:
                cap, close = load_gen_judge(MODELS[jkey], maxpx)
            except Exception as e:
                print(f"[{jkey}] 로드 실패 — 제외: {type(e).__name__}: {e}", flush=True)
                gate[jkey] = {"loaded": False}
                continue
            try:
                # 양성 대조 — 내용이 프레임에 있는 것이 확실한 성공 질의
                hits = []
                for q in succ:
                    (paths, gt_pos) = pair_for(q)
                    ans = pick(cap(open_pair(paths, full), ASK2.format(q=q["text"])))
                    hits.append(None if ans is None else (ans == gt_pos))
                got = [h for h in hits if h is not None]
                pos_rate = float(np.mean(got)) if got else 0.0
                # 하드 네거티브 — 정답이 없으므로 "1번 선택률"이 0.5 근처여야 한다
                ones = []
                for qtext, q in cross_items:
                    (paths, _) = pair_for(q, cross=True)
                    ans = pick(cap(open_pair(paths, full), ASK2.format(q=qtext)))
                    if ans is not None:
                        ones.append(ans == 1)
                neg_rate = float(np.mean(ones)) if ones else 0.5
                ok = (pos_rate >= GATE_POS) and (GATE_NEG_LO <= neg_rate <= GATE_NEG_HI)
                gate[jkey] = {"loaded": True, "positive_rate": round(pos_rate, 4),
                              "hard_negative_rate": round(neg_rate, 4), "passed": ok}
                print(f"[{cname}/{jkey}] 관문 양성 {pos_rate:.3f} "
                      f"하드네거 {neg_rate:.3f} → {'통과' if ok else '제외'}", flush=True)
                if ok:
                    v = {}
                    for q in failed:
                        (paths, gt_pos) = pair_for(q)
                        ans = pick(cap(open_pair(paths, full), ASK2.format(q=q["text"])))
                        v[q["query_id"]] = None if ans is None else (ans == gt_pos)
                    votes[jkey] = v
            finally:
                close()

        cj, cclose = load_clip()
        if cj is not None:
            hits = []
            for q in succ:
                (paths, gt_pos) = pair_for(q)
                hits.append(cj(open_pair(paths, full), q["text"]) == gt_pos)
            pos_rate = float(np.mean(hits))
            ones = [cj(open_pair(pair_for(q, True)[0], full), t) == 1
                    for t, q in cross_items]
            neg_rate = float(np.mean(ones))
            ok = (pos_rate >= GATE_POS) and (GATE_NEG_LO <= neg_rate <= GATE_NEG_HI)
            gate["clip"] = {"loaded": True, "positive_rate": round(pos_rate, 4),
                            "hard_negative_rate": round(neg_rate, 4), "passed": ok}
            print(f"[{cname}/clip] 관문 양성 {pos_rate:.3f} "
                  f"하드네거 {neg_rate:.3f} → {'통과' if ok else '제외'}", flush=True)
            if ok:
                v = {}
                for q in failed:
                    (paths, gt_pos) = pair_for(q)
                    v[q["query_id"]] = (cj(open_pair(paths, full), q["text"]) == gt_pos)
                votes["clip"] = v
        else:
            gate["clip"] = {"loaded": False}

        blk = {"gate": gate, "n_judges_passed": len(votes)}
        if len(votes) < 2:
            blk["verdict"] = ("판정 불가 — 관문을 통과한 판정자가 2개 미만. "
                              "사람 확인으로 넘긴다")
        else:
            per_item, ga, na, undec = {}, 0, 0, 0
            for q in failed:
                vs = [votes[j].get(q["query_id"]) for j in votes]
                vs = [x for x in vs if x is not None]
                if len(vs) < 2 or len(set(vs)) != 1:
                    per_item[q["query_id"]] = "판정 불가"; undec += 1
                elif vs[0]:
                    per_item[q["query_id"]] = "가"; ga += 1
                else:
                    per_item[q["query_id"]] = "나"; na += 1
            dec = ga + na
            ratio = (ga / dec) if dec else None
            blk.update({"per_item": per_item, "n_ga": ga, "n_na": na,
                        "n_undecided": undec,
                        "ga_ratio_among_decided": None if ratio is None else round(ratio, 4)})
            blk["verdict"] = (
                "판정 불가 — 확정 항목이 없다" if not dec else
                "(가) 프레임에는 있다 — 캡션 모델·프롬프트가 병목" if ratio >= 0.6 else
                "(나) 프레임에 없다 — M2·해상도로 우선순위 이동" if ratio <= 0.4 else
                "혼재 — 두 갈래 모두 연다")
            print(f"[{cname}] 가 {ga} / 나 {na} / 판정불가 {undec} → {blk['verdict']}",
                  flush=True)
        rep["by_condition"][cname] = blk

    # 사람 확인 키트 — 모델이 갈린 항목만
    if a.human_kit:
        c0 = rep["by_condition"][conds[0][0]]
        split = [qid for qid, v in c0.get("per_item", {}).items() if v == "판정 불가"]
        kit = OUT / "frame_human_kit"
        (kit / "frames").mkdir(parents=True, exist_ok=True)
        keymap, rows = {}, []
        byid = {q["query_id"]: q for q in failed}
        for i, qid in enumerate(sorted(split), 1):
            q = byid[qid]
            (paths, gt_pos) = pair_for(q)
            for j, p in enumerate(paths, 1):
                Image.open(p).convert("RGB").save(kit / "frames" / f"item_{i:02d}_{j}.jpg")
            keymap[f"item_{i:02d}"] = {"query_id": qid, "gt_position": gt_pos}
            rows.append({"item_id": f"item_{i:02d}", "질의문": q["text"], "정답": ""})
        (kit / "_keymap.json").write_text(
            json.dumps(keymap, ensure_ascii=False, indent=2), encoding="utf-8")
        with (kit / "answers_blind.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, ["item_id", "질의문", "정답"])
            w.writeheader(); w.writerows(rows)
        (kit / "가이드.md").write_text(
            "# 프레임 내용 확인 (모델 판정이 갈린 항목만)\n\n"
            "`frames/item_XX_1.jpg`와 `item_XX_2.jpg` 두 장을 보고, `answers_blind.csv`의\n"
            "**정답** 칸에 질의문에 맞는 사진 번호(`1` 또는 `2`)를 적는다. **둘 다 아니면 `0`**.\n\n"
            "- 어느 쪽이 정답인지는 파일에 없다(`_keymap.json`은 보지 말 것).\n"
            "- 검색 결과·캡션·자막을 보지 않는다(절대규칙 3).\n"
            "- 애매하면 `0`을 적는다. 억지로 고르지 않는다.\n",
            encoding="utf-8")
        rep["human_kit"] = {"n_items": len(rows), "path": str(kit)}
        print(f"사람 확인 키트 {len(rows)}건 -> {kit}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "frame_content_judge.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", p)


if __name__ == "__main__":
    main()
