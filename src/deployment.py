"""배포 identity 단일 출처 + **공식 지원 실행 진입점 목록**.

왜 필요한가. 2026-08-26 감사에서 `scripts/demo.py`만 α=0.5를 강제하고, README가 함께
안내하는 `python src/m7_webui.py --alpha …`는 아무 값이나 받는 것이 드러났다. 즉
**진입점에 따라 배포 identity가 달라졌다.** 어떤 실행 경로가 공식이고 각 경로가 무엇을
강제하는지 코드에 적어 두지 않으면 이 상태가 반복된다.

identity 값이 두 곳(demo.py·e2e_external.py)에 복사돼 있던 것도 여기로 모은다 —
표류를 테스트로 감시하는 것보다 출처를 하나로 두는 편이 낫다.

**이 파일의 값을 바꾸는 것은 배포 변경이고 별도 승인 사건이다** (CLAUDE.md).
"""

DEPLOYMENT = {
    "caption_model": "Qwen/Qwen2.5-VL-3B-Instruct",
    "vlm_4bit": True,
    "embed_model": "nlpai-lab/KURE-v1",
    "seg_len_sec": 5,
    "static_threshold": 0,
}

# α는 config에 없다 — CLI 주입값이고 확정값은 results/alpha_search_dev.json의 alpha_star.
ALPHA = 0.5

# 공식 지원 진입점. `enforces`는 그 진입점이 **실제로 실행 시 막는 것**이다.
# 선언이 아니라 구현 상태를 적는다 — 비어 있으면 그 경로는 아무것도 보장하지 않는다.
SUPPORTED_ENTRYPOINTS = {
    # alpha_strict = 우회 플래그가 없다. 배포 진입점은 다른 α로 열리지 않는다.
    "scripts/demo.py": {
        "role": "배포 데모 (권장 진입점)",
        "enforces": ("identity", "alpha_strict", "eligibility", "index", "text_hash"),
    },
    "src/m7_webui.py": {
        "role": "웹 UI 직접 실행 (preflight 없음)",
        "enforces": ("alpha", "eligibility"),
    },
    "src/m7_demo.py": {
        "role": "Gradio 데모 (단일 영상)",
        "enforces": ("alpha", "eligibility"),
    },
    "src/m5_search.py": {
        "role": "CLI 검색 — 연구·진단용",
        "enforces": ("alpha_range",),
    },
    "src/m6_evaluate.py": {
        "role": "평가 — dev 전용이 기본",
        "enforces": ("alpha_range", "test_opening"),
    },
    "src/m9_report_eval.py": {
        "role": "AAR 평가 — 실행 자체가 test 접촉",
        "enforces": ("test_opening",),
    },
}

ALPHA_OPT_OUT = "--allow-nondeployment-alpha"


class DeploymentIdentityError(RuntimeError):
    pass


def check_alpha(alpha: float, allow_nondeployment: bool = False) -> float:
    """데모 성격 진입점의 α 검증.

    범위 검증은 `m5_search.combine_scores`가 모든 경로에서 하고, 여기서는 **배포
    확정값인지**를 본다. dev 진단으로 다른 α를 보려면 명시적으로 열어야 한다 —
    기본값이 배포값이어야 진입점을 바꿔도 identity가 유지된다.
    """
    a = float(alpha)
    if not (0.0 <= a <= 1.0):
        raise DeploymentIdentityError(f"alpha={alpha}는 [0, 1] 밖이다")
    if allow_nondeployment:
        return a
    if abs(a - ALPHA) > 1e-9:
        raise DeploymentIdentityError(
            f"alpha={alpha}는 배포 확정값이 아니다 (배포 alpha={ALPHA}). "
            f"진단 목적이면 {ALPHA_OPT_OUT}를 붙여 명시해라 — 그 실행은 배포 구성이 아니다")
    return a
