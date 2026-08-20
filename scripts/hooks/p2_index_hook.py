"""P2 두 arm 색인 — **실험별** validator hook.

launcher 공통 검사(파일 존재·provenance 키·commit 대조)는 "돌았는가"를 본다. 이
실험에서 통과시킬 수 없는 것은 **"두 arm이 비교 가능한가"**다. 조건이 갈린 채
20시간을 쓰면 그 산출물로는 부호를 판정할 수 없다.

그래서 아래를 게이트로 올린다.

```
both_arms_present              두 arm 산출물이 다 있다
model_ids_as_declared          사전등록 arm 정체성 그대로다
both_arms_quantized            양쪽 4bit — PRIMARY가 배포 경로 비교다
prompt_identical_across_arms   프롬프트 해시가 같다 (arm이 바꾸는 것은 모델뿐)
subtitles_identical_across_arms 자막이 같다 (STT 1회 + 복제가 실제로 됐는가)
segments_match_preregistered   구간 수가 표집틀 검증값과 같다 (재현 게이트)
captions_complete              빈 캡션 0건
text_hash_matches              m4가 갱신된 텍스트로 돌았다
emb_shapes_ok                  (n, 1024) x 2
provenance_present             영상 출처가 색인에 실려 있다
```

**성능은 보지 않는다.** MRR·Δ·우열 판단은 GT 라벨 뒤 별도 분석의 일이다.
"""
import json
from pathlib import Path

DECLARED = {"3b": "Qwen/Qwen2.5-VL-3B-Instruct",
            "4b": "Qwen/Qwen3-VL-4B-Instruct"}
EMB_DIM = 1024
RUN_GLOB = "p2_index_batch_run*.json"


def _report(run_dir: Path) -> dict:
    """**FULL 산출물을 우선한다.** CANARY와 FULL이 같은 run_id를 공유하므로 두 파일이
    함께 있을 수 있고, 이름순으로 집으면 1편짜리 CANARY 결과를 FULL로 검증하게 된다."""
    ps = sorted(Path(run_dir).glob(RUN_GLOB))
    full = [p for p in ps if p.stem.endswith("_full")]
    for p in (full or ps):
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def check(run_dir) -> tuple:
    """(ok, checks). launcher `validate`의 실험별 훅."""
    rep = _report(run_dir)
    arms = rep.get("arms") or {}
    checks = {"both_arms_present": set(arms) == set(DECLARED)}

    def prov(a, k):
        return ((arms.get(a) or {}).get("caption_provenance") or {}).get(k)

    present = [a for a in DECLARED if a in arms]
    checks["model_ids_as_declared"] = bool(present) and all(
        prov(a, "model_id") == DECLARED[a] for a in present)
    checks["both_arms_quantized"] = bool(present) and all(
        prov(a, "quantized") is True for a in present)
    prompts = {prov(a, "prompt_sha256") for a in present}
    checks["prompt_identical_across_arms"] = len(prompts) == 1 and None not in prompts

    rows = {a: (arms[a].get("videos") or {}) for a in present}
    vids = sorted({v for r in rows.values() for v in r})
    checks["videos_present_in_both_arms"] = bool(vids) and all(
        all(v in rows[a] for a in present) for v in vids)

    def every(fn):
        return bool(vids) and all(
            fn(rows[a][v]) for a in present for v in vids if v in rows[a])

    checks["subtitles_identical_across_arms"] = bool(vids) and all(
        len({rows[a][v].get("subtitle_sha256") for a in present
             if v in rows[a]}) == 1 for v in vids)
    checks["segments_match_preregistered"] = every(
        lambda r: r.get("expected_n_segments") is not None
        and r.get("n_segments") == r.get("expected_n_segments"))
    checks["captions_complete"] = every(
        lambda r: r.get("captions_nonempty") == r.get("n_segments"))
    checks["provenance_present"] = every(lambda r: r.get("provenance_present") is True)

    # m4까지 돌았을 때만 본다 — 단계별 실행에서 없는 것을 FAIL로 만들지 않는다
    has_index = every(lambda r: r.get("emb_shapes") is not None)
    checks["index_stage_ran"] = has_index
    if has_index:
        checks["text_hash_matches"] = every(
            lambda r: r.get("text_hash_matches_meta") is True)
        checks["emb_shapes_ok"] = every(
            lambda r: all(r["emb_shapes"].get(k) == [r["n_segments"], EMB_DIM]
                          for k in ("emb_sub", "emb_cap")))

    return all(checks.values()), checks
