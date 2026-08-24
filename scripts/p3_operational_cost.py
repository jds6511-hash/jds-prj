"""3B vs 4B **운영비 프로파일** — 검색 성능을 보지 않고 생성 비용만 잰다.

채택 효용 기준("어느 정도 이득이면 교체할 가치가 있는가")을 정하려면 먼저 **무엇을 더
지불하는가**를 알아야 한다. 그 질문은 retrieval outcome과 무관하므로 P3를 오염시키지
않는다 — 단, **읽는 필드를 구조적으로 제한**해야 그렇다.

```
읽는다     provenance(모델·정밀도·설정·하드웨어·소요시간) · i1의 캡션 길이 평균 · n_segments
안 읽는다   arms(캡션/융합/자막 MRR) · per_query · contrasts · bh_fdr · halves
새 GPU run  없다. 이미 있는 산출물만 읽는다
```

쓸 수 있는 자료는 **AI Hub 2×2 full 하나뿐**이다. 네 arm이 같은 GPU·같은 commit·같은
entrypoint·같은 max_pixels/max_new_tokens에서 돌았으므로 모델 크기의 생성비 비교가
가능하다. 다만 **그 표본은 bf16이고 배포는 4bit다** — 정밀도 간극을 결과에 적는다.

빠진 것(peak VRAM·4bit throughput·로딩 오버헤드·저장량·OOM)은 새 측정이 필요하다.
그 측정 프로토콜을 여기서 **동결하고 실행하지 않는다**(GPU 배치는 사용자 승인 사건).

재현:
  python scripts/p3_operational_cost.py --out docs/P3_운영비_2026-08-24.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "probes" / "_scratch" / \
    "aihub_caption_2x2_full_2026-08-17.json"

BASE_ARM = "qwen25_3b/P0"
CAND_ARM = "qwen3vl_4b/P0"

# 읽어도 되는 최상위 키. 이 목록 밖은 열지 않는다
READ_ALLOWLIST = ("provenance", "i1", "n_segments")
# 검색 성능이 들어 있는 키·필드. 읽으면 채택 기준을 결과에 맞추는 통로가 된다
FORBIDDEN_KEYS = ("arms", "per_query", "contrasts", "bh_fdr", "halves",
                  "halves_detail", "configuration_effect_vs_base",
                  "divergence_vs_old")
FORBIDDEN_FIELDS = ("cap", "fus", "sub")

# provenance에서 arm 간에 **같아야** 비교가 성립하는 필드
MATCH_FIELDS = ("gpu", "git_head", "entrypoint", "python", "torch",
                "transformers", "attn_implementation",
                "config_vlm_max_pixels", "config_vlm_max_new_tokens",
                "config_vlm_rep_penalty", "prompt_sha256")
COST_FIELDS = ("model_id_effective", "model_revision", "dtype_effective",
               "quantized_effective", "attn_implementation",
               "config_vlm_max_pixels", "config_vlm_max_new_tokens",
               "elapsed_sec", "sec_per_segment", "gpu")

DEPLOYMENT_PRECISION = "4bit"

# 재캡셔닝 규모 투사에 쓰는 corpus 크기 — 출처를 함께 적는다
CORPORA = (
    {"name": "배포 인덱스(dev+test 대상)", "n_segments": 2568,
     "source": "docs/작업현황_2026-08-22.md — 11편 2,568구간"},
    {"name": "P2 장편 표본", "n_segments": 9115,
     "source": "docs/작업현황_2026-08-22.md §5 — 35편 9,115구간"},
)

# P2 FULL 단계 소요(작업현황 2026-08-22 §5). **단계 의미가 비대칭이다**
P2_STAGE = {"m3_base_sec": 40988, "m3_captions_sec": 28808,
            "n_segments": 9115}

MISSING = (
    {"item": "peak_vram",
     "why_it_matters": "배포가 6GB 노트북 4bit다. 4B가 그 안에 들어가는지·여유가 얼마인지가 "
                       "교체 가능성을 직접 정한다",
     "how_to_get_it": "같은 기기에서 두 arm을 각각 로드해 torch.cuda.max_memory_allocated "
                      "peak을 기록. 프레임 수·max_pixels·max_new_tokens 고정",
     "existing_partial": "4B 4bit 노트북 3060에서 peak 3.27GB "
                         "(docs/probes/_scratch/laptop_4bit_feasibility.json) — "
                         "3B 짝이 없어 비교 불가"},
    {"item": "throughput_at_4bit",
     "why_it_matters": "가진 비교는 bf16이다. 4bit에서 두 모델의 상대 속도가 뒤집힐 수 있다",
     "how_to_get_it": "동일 기기·동일 프레임 집합에서 두 arm 4bit로 sec/segment 측정",
     "existing_partial": None},
    {"item": "load_overhead",
     "why_it_matters": "영상당 로드 1회다. 배치 구조상 총비용에 직접 더해진다",
     "how_to_get_it": "로드 시작~첫 생성까지 시간을 arm별 3회 반복 측정",
     "existing_partial": "4B 4bit 노트북 로드 18.3초 (laptop_4bit_feasibility.json)"},
    {"item": "storage_delta",
     "why_it_matters": "모델 가중치와 캐시 용량. /ssd 용량 제약이 있다",
     "how_to_get_it": "HF_HOME 아래 arm별 스냅샷 디렉터리 바이트 합계",
     "existing_partial": None},
    {"item": "oom_failure",
     "why_it_matters": "장애 위험은 지연과 다른 종류의 비용이다",
     "how_to_get_it": "배포 프로필(6GB)에서 두 arm 각각 최소 30구간 연속 생성, 실패 수 기록",
     "existing_partial": None},
    {"item": "reindex_wall_clock",
     "why_it_matters": "교체는 전 영상 재캡셔닝 + m4를 부른다. 그 시간이 교체 비용의 큰 항이다",
     "how_to_get_it": "위 throughput에 corpus 구간 수를 곱하고 m4 실측을 더한다",
     "existing_partial": "P2 FULL m4_index 921초 / 35편 9,115구간 (양 arm)"},
)

PROTOCOL = {
    "name": "p3_opcost_v1",
    "purpose": "3B와 4B의 생성 비용을 배포 정밀도에서 같은 조건으로 잰다",
    "executed": False,
    "requires_user_approval": True,
    "labels_required": 0,
    "reads_retrieval_outcome": False,
    "writes_captions_to_index": False,
    "matched_conditions": (
        "같은 기기·같은 GPU", "같은 commit", "같은 프레임 집합(고정 목록)",
        "같은 vlm_max_pixels·max_new_tokens·rep_penalty",
        "같은 attn_implementation", "같은 프롬프트(P0, prompt_sha256 기록)",
        "양 arm 동일 정밀도(4bit)", "같은 실행 순서 내 교대 배치(웜업 편향 제거)",
    ),
    "steps": (
        "1  프레임 목록·반복 수·측정 필드를 먼저 파일로 동결한다(결과 보고 고치지 않는다)",
        "2  arm별 로드 시간·peak VRAM을 각 3회 측정하고 중위수를 쓴다",
        "3  고정 프레임 집합에서 sec/segment를 측정한다. 캡션 **문자열은 저장하지 않고** "
        "   길이·토큰 수만 남긴다 (내용을 보면 GT·프롬프트 조정 통로가 열린다)",
        "4  실패·OOM 수를 세고, storage 바이트를 기록한다",
        "5  결과 JSON에 provenance(모델·revision·dtype·양자화 실효값·라이브러리)를 넣는다",
    ),
    "explicitly_not_measured": (
        "retrieval 성능", "캡션 내용 품질", "MRR·RR·순위", "GT 관련 어떤 것도",
    ),
    "note": ("정식 GPU 배치는 git에 등록된 스크립트로만 돌린다. 계획 → canary → 본 실행 "
             "순서를 지키고 본 실행 전 승인을 받는다"),
}


class CostError(RuntimeError):
    pass


def _load(source) -> dict:
    """**allowlist에 있는 최상위 키만** 남기고 나머지는 버린다."""
    p = Path(source)
    if not p.is_file():
        raise CostError(f"자료가 없다: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in doc.items() if k in READ_ALLOWLIST}


def _arm_prov(doc: dict, arm: str) -> dict:
    prov = doc.get("provenance") or {}
    if arm not in prov:
        raise CostError(f"arm {arm!r}의 provenance가 없다")
    return prov[arm]


def comparability(doc: dict, arms) -> dict:
    """비교 조건이 실제로 맞았는지 본다. 안 맞으면 비율을 내지 않는다."""
    provs = {a: _arm_prov(doc, a) for a in arms}
    matched, mismatched = [], []
    for f in MATCH_FIELDS:
        vals = {a: provs[a].get(f) for a in arms}
        present = [v for v in vals.values() if v is not None]
        if not present:
            continue
        (matched if len(set(map(str, vals.values()))) == 1
         else mismatched).append(f)
    return {"matched": not mismatched, "matched_fields": matched,
            "mismatched_fields": mismatched,
            "note": ("이 필드들이 같아야 모델 효과와 환경 효과가 섞이지 않는다 "
                     "(CLAUDE.md 후보검증 규약 4번 동시점 대조군)")}


def profile(source=SOURCE, arms=(BASE_ARM, CAND_ARM)) -> dict:
    doc = _load(source)
    base, cand = arms
    provs = {a: _arm_prov(doc, a) for a in arms}
    lens = {a: ((doc.get("i1") or {}).get(a) or {}).get("len_mean")
            for a in arms}
    n_seg = doc.get("n_segments")

    out_arms = {}
    for a in arms:
        row = {f: provs[a].get(f) for f in COST_FIELDS}
        row["caption_len_mean_chars"] = lens.get(a)
        out_arms[a] = row

    comp = comparability(doc, arms)
    sb, sc = provs[base].get("sec_per_segment"), provs[cand].get("sec_per_segment")
    ratio = None
    if comp["matched"] and sb and sc:
        ratio = {
            "sec_per_segment_candidate_over_base": sc / sb,
            "sec_per_segment_delta": round(sc - sb, 4),
            "caption_len_candidate_over_base": (
                round(lens[cand] / lens[base], 4)
                if lens.get(base) and lens.get(cand) else None),
            "interpretation": ("1보다 작으면 후보가 더 싸다. 캡션이 짧으면 생성 토큰이 "
                              "적어 빨라진다 — 길이 비와 함께 읽어야 한다"),
        }

    proj = []
    if sb and sc:
        for c in CORPORA:
            proj.append({"name": c["name"], "n_segments": c["n_segments"],
                         "source": c["source"],
                         "base_hours": round(c["n_segments"] * sb / 3600, 2),
                         "candidate_hours": round(c["n_segments"] * sc / 3600, 2),
                         "basis": ("bf16 sec/segment를 그대로 곱했다 — 4bit에서는 "
                                   "달라진다")})

    return {
        "probe": "p3_operational_cost",
        "question": "3B를 4B로 바꾸면 운영상 무엇을 더 지불하는가",
        "source": (str(Path(source).relative_to(ROOT)).replace("\\", "/")
                   if Path(source).is_relative_to(ROOT) else str(source)),
        "read_keys": [k for k in READ_ALLOWLIST if k in doc],
        "forbidden_keys_not_read": list(FORBIDDEN_KEYS),
        "outcome_blind": True,
        "new_gpu_run": False,
        "n_segments_measured": n_seg,
        "arms": out_arms,
        "comparability": comp,
        "ratio": ratio,
        "sample_precision": "bf16",
        "deployment_precision": DEPLOYMENT_PRECISION,
        "precision_gap_warning": ("이 비교는 bf16이고 배포는 4bit다. 양자화는 두 모델에 "
                                  "같은 비율로 작용하지 않을 수 있으므로 상대 속도가 "
                                  "뒤집힐 수 있다 — 4bit 측정 없이 결론을 내지 마라"),
        "recaption_projection": proj,
        "p2_full_stage_timing": {
            "run_id": "p2idx_0821d",
            "n_segments": P2_STAGE["n_segments"],
            "m3_base_sec": P2_STAGE["m3_base_sec"],
            "m3_captions_sec": P2_STAGE["m3_captions_sec"],
            "base_stage_includes_stt": True,
            "base_caption_sec_per_segment_upper_bound": round(
                P2_STAGE["m3_base_sec"] / P2_STAGE["n_segments"], 3),
            "candidate_caption_sec_per_segment": round(
                P2_STAGE["m3_captions_sec"] / P2_STAGE["n_segments"], 3),
            "note": ("m3_base는 Whisper STT + 기준 arm 캡션이고 m3_captions는 후보 arm "
                     "캡션만이다. **단계 의미가 비대칭이므로 두 숫자를 모델 비교로 쓰면 "
                     "안 된다.** 기준 arm 값은 STT를 포함한 상한이다. 양 arm 4bit라는 "
                     "점은 이 실행의 장점이지만, 분리 측정이 없다"),
            "source": "docs/작업현황_2026-08-22.md §5",
        },
        "missing_measurements": [dict(m) for m in MISSING],
        "measurement_protocol": {k: (list(v) if isinstance(v, tuple) else v)
                                 for k, v in PROTOCOL.items()},
        "minimum_deployment_relevant_gain": "사용자_결정_사항",
        "decision": "사용자_결정_사항",
        "decision_note": ("운영비 차이를 보고 최소 가치 효과를 정하고, 그 다음에 필요한 "
                          "정밀도와 규모를 정한다. **라벨 부담이 작다는 이유로 최소 가치 "
                          "효과를 크게 잡는 역방향은 금지다**"),
        "limitations": [
            "표본이 하나다 — AI Hub 2×2 full. 다른 하드웨어·다른 배치 구조에서 같은 비율이 "
            "나온다고 보장하지 않는다",
            "bf16 측정이다. 배포 정밀도(4bit) 측정이 없다",
            "peak VRAM·로딩·저장량·OOM은 짝 맞춘 측정이 없다",
            "sec/segment는 출력 길이에 의존한다 — 모델 속도와 캡션 길이 효과가 섞여 있다",
            "AI Hub 구간은 짧은 클립이다. 장편에서 프레임 해상도·배치 구성이 달라지면 "
            "비율이 달라질 수 있다",
        ],
    }


def _fmt(r: dict) -> str:
    lines = [f"source: {r['source']}  (구간 {r['n_segments_measured']})",
             f"비교 조건 일치: {r['comparability']['matched']} "
             f"(불일치 {r['comparability']['mismatched_fields']})"]
    for a, v in r["arms"].items():
        lines.append(f"  {a:<16} {v['sec_per_segment']:>6.3f} s/seg · "
                     f"{v['elapsed_sec']:>9.1f} s · len {v['caption_len_mean_chars']} 자 · "
                     f"{v['dtype_effective']} quantized={v['quantized_effective']}")
    if r["ratio"]:
        lines.append(f"  후보/기준 = "
                     f"{r['ratio']['sec_per_segment_candidate_over_base']:.3f} "
                     f"(길이비 {r['ratio']['caption_len_candidate_over_base']})")
    for p in r["recaption_projection"]:
        lines.append(f"  재캡셔닝 {p['name']} {p['n_segments']}구간: "
                     f"기준 {p['base_hours']}h · 후보 {p['candidate_hours']}h")
    lines.append(f"  빠진 측정 {len(r['missing_measurements'])}건 · "
                 f"프로토콜 실행 {r['measurement_protocol']['executed']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="3B vs 4B 운영비 프로파일 (outcome-blind, 새 GPU run 없음)")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = profile()
    print(_fmt(r))
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
