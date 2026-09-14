"""v2.1 sparse-evidence safe mode — TRI-005 remediation (C3).

```
eligible 0   프롬프트가 이미 거부한다        ERR-009 · 여기 들어오지 않는다
eligible 1   summary 권한을 모델에게 주지 않는다   ← 이 모듈
eligible 2+  기존 경로 그대로               GRD-004 P1 한계가 남는다
```

**의미 판정을 하지 않는다.** 모델 요약이 근거를 넘었는지 비교하지 않고, 넘었는지
묻지도 않는다. 비교를 시작하면 C2(entailment verifier)의 축소판이 되고, GRD-004
waiver가 거부한 경로로 되돌아간다. 이 모듈이 하는 것은 하나다.

> sparse이면 모델 요약의 정본 권한이 0이다.

근거 원문은 **그대로** 옮긴다. 접속어·도입구("근거에 따르면", "영상에서는")를 붙이지
않고, 어색한 발화를 다듬지도 않는다. 다듬는 순간 생성 권한이 다시 생긴다.

`summary_mode`는 **provenance이지 판정이 아니다.** grounding 상태를 새로 세우거나
덮어쓰지 않는다 — 바뀌는 것은 "이 문장이 어디서 왔는가"뿐이다.

사전등록: `docs/finalization/V2_1_TRI_005_REMEDIATION_PREREG_2026-09-02.md`
"""
from __future__ import annotations

import dataclasses

from v2_1_parse import VALID_PARSE
from v2_1_prompt import split_evidence

#: 모델이 쓴 문장이 정본이다.
MODEL_ABSTRACTIVE = "MODEL_ABSTRACTIVE"
#: sparse라 근거 원문이 정본이다.
SPARSE_EVIDENCE_DETERMINISTIC = "SPARSE_EVIDENCE_DETERMINISTIC"

#: 닫힌 집합이다. 모르는 값을 조용히 MODEL_ABSTRACTIVE로 떨어뜨리지 않는다.
SUMMARY_MODES = (MODEL_ABSTRACTIVE, SPARSE_EVIDENCE_DETERMINISTIC)


def sparse_claim_evidence(episode, timeline):
    """SPARSE_V1이면 그 근거 하나를 돌려준다. 아니면 None이다.

    개수는 **프롬프트 계약과 같은 함수**로 센다(`split_evidence`). timeline ref나
    binding evidence를 여기서 다시 세면 두 벌이 갈라지고, "프롬프트가 허용하는 가장
    희소한 상태"라는 정의 근거가 사라진다.
    """
    claim, _ = split_evidence(episode, timeline)
    return claim[0] if len(claim) == 1 else None


def apply_sparse_summary(grounded, episode, timeline, store):
    """sparse 구간의 정본 summary를 근거 원문으로 세운다.

    구조·grounding·dialogue는 건드리지 않는다. 실패한 내용(`content_status`가
    `VALID_PARSE`가 아닌 것)에도 손대지 않는다 — 그것은 B-04의 계약이다.
    """
    if grounded.content_status != VALID_PARSE or not grounded.summary:
        return grounded

    ref = sparse_claim_evidence(episode, timeline)
    if ref is None:
        return grounded

    text = store.load(ref.source_type, ref.segment_id).read_text().strip()
    return dataclasses.replace(
        grounded,
        summary=text,
        summary_mode=SPARSE_EVIDENCE_DETERMINISTIC,
    )
