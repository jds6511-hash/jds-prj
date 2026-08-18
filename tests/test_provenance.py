"""M8/M9 provenance — 어떤 조건에서 나온 산출물인지 사후에 복원 가능한가.

M3에서 provenance가 **요청값과 실효값의 불일치**를 잡았다(`vlm_4bit`가 무시된 채
bf16으로 돈 전례). M8/M9에는 그 장치가 없다. judge 모델·프롬프트·생성 kwargs가
바뀌어도 결과 파일만 보고는 알 수 없다.

여기서 검증하는 것:
  (1) 환경 캡처가 필요한 키를 빠뜨리지 않는가
  (2) **요청값과 실효값을 둘 다** 남기는가 — 하나만 남기면 불일치를 못 본다
  (3) 프롬프트 해시가 프롬프트가 바뀌면 같이 바뀌는가
  (4) M9가 judge의 **원문 응답**을 남기는가 — 파싱 결과만 남기면 재검증이 불가능하다
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
import llm as llm_mod                                      # noqa: E402
import m8_report                                           # noqa: E402
import m9_report_eval                                      # noqa: E402


class FakeConfig:
    _name_or_path = "Qwen/Qwen2.5-7B-Instruct"
    _commit_hash = "abc123"
    _attn_implementation = "sdpa"
    quantization_config = None


class FakeModel:
    config = FakeConfig()
    dtype = "torch.bfloat16"


def _fake_gen(load_4bit=False, loaded=True):
    def gen(prompt, **kw):
        return ""
    gen.spec = {"model_name": "Qwen/Qwen2.5-7B-Instruct", "max_new_tokens": 2048,
                "requested_4bit": load_4bit}
    gen.model = FakeModel() if loaded else None
    return gen


# ---- (1) 환경 캡처 -------------------------------------------------------

def test_env_provenance_has_required_keys():
    env = common.env_provenance()
    for k in ("git_head", "git_dirty", "python", "torch", "transformers",
              "gpu", "generated_at"):
        assert k in env, k


# ---- (2) 요청값 vs 실효값 ------------------------------------------------

def test_llm_provenance_records_requested_and_effective():
    prov = llm_mod.llm_provenance(_fake_gen(load_4bit=True), role="judge",
                                  prompts={"grounded": "abc"})
    assert prov["role"] == "judge"
    assert prov["requested_4bit"] is True
    # 실효값: FakeModel은 quantization_config가 None이므로 양자화되지 않았다
    assert prov["effective_quantized"] is False
    # 요청과 실효가 갈리면 그 자체가 사고다 — 플래그로 드러나야 한다
    assert prov["quantization_mismatch"] is True
    assert prov["effective_model_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert prov["effective_model_revision"] == "abc123"
    assert prov["effective_dtype"] == "torch.bfloat16"
    assert prov["max_new_tokens"] == 2048


def test_llm_provenance_no_mismatch_when_consistent():
    prov = llm_mod.llm_provenance(_fake_gen(load_4bit=False), role="report",
                                  prompts={"map": "x"})
    assert prov["quantization_mismatch"] is False


def test_llm_provenance_marks_model_not_loaded():
    """생성 호출이 한 번도 없었으면 실효값을 알 수 없다 — 조용히 None으로
    두지 말고 명시한다."""
    prov = llm_mod.llm_provenance(_fake_gen(loaded=False), role="report", prompts={})
    assert prov["model_loaded"] is False
    assert prov["effective_model_id"] is None


def test_make_llm_exposes_spec_before_any_call():
    gen = llm_mod.make_llm("some/model", max_new_tokens=512, load_4bit=True)
    assert gen.spec["model_name"] == "some/model"
    assert gen.spec["max_new_tokens"] == 512
    assert gen.spec["requested_4bit"] is True
    assert gen.model is None            # 지연 로딩 — 아직 안 올라왔다


# ---- (3) 프롬프트 해시 ---------------------------------------------------

def test_prompt_hashes_change_with_prompt():
    a = llm_mod.llm_provenance(_fake_gen(), role="r", prompts={"p": "hello"})
    b = llm_mod.llm_provenance(_fake_gen(), role="r", prompts={"p": "hello!"})
    assert a["prompt_sha256"]["p"] != b["prompt_sha256"]["p"]


def test_m8_prompt_sources_cover_all_builders():
    """M8 프롬프트는 상수가 아니라 **함수**다 — 소스를 해시해야 템플릿 변경이 잡힌다."""
    src = m8_report.prompt_sources()
    for k in ("build_map_prompt", "build_reduce_prompt", "build_event_prompt"):
        assert k in src and len(src[k]) > 50


def test_m9_prompt_sources_cover_both_judge_prompts():
    src = m9_report_eval.prompt_sources()
    assert set(src) == {"grounded", "coverage"}


# ---- (4) M9 원문 응답 보존 ------------------------------------------------

SEGS = [{"idx": 0, "start": 0, "end": 5, "subtitle": "안녕하세요", "caption": "사람이 걷는다"},
        {"idx": 1, "start": 5, "end": 10, "subtitle": "", "caption": "문이 열린다"}]
REPORT = {"sentences": [{"sent_id": 0, "text": "사람이 걸어 들어온다", "cites": [0]},
                        {"sent_id": 1, "text": "인용 없는 문장", "cites": []}]}


def test_eval_report_keeps_raw_judge_output():
    judge = lambda p: '{"match": true}'      # noqa: E731
    out = m9_report_eval.eval_report(REPORT, SEGS, [0, 1], judge)
    cited = [p for p in out["per_sentence"] if p["cites"]][0]
    assert cited["judge_raw"] == '{"match": true}'
    # coverage는 청크마다 물으므로 원문이 여러 개일 수 있다 — 리스트로 남긴다
    assert isinstance(out["per_gt_segment"][0]["judge_raw"], list)
    assert out["per_gt_segment"][0]["judge_raw"][0] == '{"match": true}'


def test_uncited_sentence_has_no_raw_because_judge_not_called():
    judge = lambda p: '{"match": true}'      # noqa: E731
    out = m9_report_eval.eval_report(REPORT, SEGS, [0], judge)
    uncited = [p for p in out["per_sentence"] if not p["cites"]][0]
    assert uncited["judge_raw"] is None


# ---- 스키마 버전 ---------------------------------------------------------

def test_save_report_writes_schema_version_and_provenance(tmp_path):
    rep = {"sentences": [{"sent_id": 0, "text": "사람이 걷는다", "cites": [0]}],
           "raw_output": "x"}
    cfg = {"report_model": "m", "map_chunk_size": 60}
    out = tmp_path / "report.json"
    m8_report.save_report(out, "vid", cfg, rep, n=2, provenance={"role": "report"})
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["schema_version"] == m8_report.SCHEMA_VERSION
    assert d["provenance"] == {"role": "report"}


def test_save_report_provenance_optional(tmp_path):
    """provenance 없이 부르는 기존 호출부가 깨지지 않아야 한다."""
    rep = {"sentences": [{"sent_id": 0, "text": "사람이 걷는다", "cites": [0]}],
           "raw_output": "x"}
    out = tmp_path / "report.json"
    m8_report.save_report(out, "vid", {"report_model": "m", "map_chunk_size": 60},
                          rep, n=2)
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["schema_version"] == m8_report.SCHEMA_VERSION
    assert d.get("provenance") is None
