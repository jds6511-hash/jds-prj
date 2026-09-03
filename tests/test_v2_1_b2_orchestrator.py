"""B2 orchestrator — dry-run(O)과 resume/failure(R) 계약.

```
O1   정상 다구간
O2   sparse eligible == 1  (TRI-005 end-to-end containment)
O3a  eligible == 0         → LLM 호출 자체 없음
O3b  근거 있음 + parse 실패  → raw 보존 + explicit content failure

R1   완전 재사용        stage 함수 호출 0
R2   부분 stage         artifact는 있으나 _SUCCESS 없음 → 재사용 금지
R3   산출물 변조        hash 불일치 → 재생성
R4   provenance 변경    prompt hash·model id 변경 → stale 재사용 0
R5   S2 hard failure    일부 raw 보존 · S2 미완료 · downstream 0
R6   S7 실패            canonical·MD 보존 · A1 호출 0
```

서버 없이 돈다. fake 생성기를 쓰지만 **경로는 전부 실물**이다 — raw 저장 → 실제 parser
→ binding → grounding → sparse → AAR → presentation → A2'. 중간 객체를 손으로 만들어
단계를 건너뛰면 orchestrator를 검증하는 것이 아니다.
"""
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from v2_1_fixtures import scenario
from v2_1_llm_adapter import GenerationConfig

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_b2_orchestrate.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b2 = _load(SCRIPT, "v2_1_b2_orchestrate")

GENERATION = GenerationConfig(model_id="fixture/qwen-stub", do_sample=False,
                              max_new_tokens=128)

NORMAL_PAYLOADS = (
    {"summary": "두 여성이 해변에 앉아 주변을 둘러본다."},
    {"summary": "두 여성이 가방을 열고 음료를 나눠 마신다.",
     "dialogue_note": "소스를 넣으면 된다고 말한다.", "stt_cites": [9]},
)
INVENTED = "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."
EVIDENCE = "남성이 문을 연다."


def _segments_file(tmp_path, name, *, asr=None, caption=None,
                   duration=60.0) -> Path:
    """B1 산출물 모양의 segments.json을 만든다(idx/start/end + subtitle/caption)."""
    fixture = scenario(name)
    asr = fixture.asr if asr is None else asr
    caption = fixture.caption if caption is None else caption
    segments = []
    for segment in fixture.segments:
        segments.append({
            "idx": segment.segment_id,
            "start": segment.start_sec,
            "end": segment.end_sec,
            "subtitle": asr.get(segment.segment_id, ""),
            "caption": caption.get(segment.segment_id, ""),
        })
    path = tmp_path / "segments.json"
    path.write_text(json.dumps({
        "video_id": name, "duration_sec": duration, "fps": 30.0,
        "n_segments": len(segments),
        "provenance": {"provenance_status": "recorded",
                       "source_url": "https://example.invalid/v",
                       "source_id": "fixture", "file_sha256": "0" * 64},
        "segments": segments,
    }, ensure_ascii=False), encoding="utf-8")
    return path


class _Fake:
    """호출 순서대로 payload를 돌려준다. 호출 횟수를 센다."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        payload = self.payloads[min(self.calls - 1, len(self.payloads) - 1)]
        return payload if isinstance(payload, str) else json.dumps(
            payload, ensure_ascii=False)


def _config(tmp_path) -> Path:
    path = tmp_path / "config_b2.yaml"
    path.write_text("paths:\n  work: work_b2\n", encoding="utf-8")
    return path


def _run(tmp_path, *, name="S1", payloads=NORMAL_PAYLOADS, asr=None,
         caption=None, window_sec=30.0, generate=None, run_dir="run"):
    segments = _segments_file(tmp_path, name, asr=asr, caption=caption)
    fake = generate or _Fake(payloads)
    summary = b2.orchestrate(
        tmp_path / run_dir, segments, _config(tmp_path),
        video_id=name, run_id="b2-test", generate=fake,
        generation=GENERATION, producer_version="b1-code-head",
        window_sec=window_sec)
    return summary, fake, tmp_path / run_dir


def _canonical(run: Path) -> dict:
    return json.loads((run / "S5/aar_canonical.json").read_text(encoding="utf-8"))


def _hwpx_text(run: Path) -> str:
    with zipfile.ZipFile(run / "S7/report.hwpx") as package:
        return package.read("Contents/section0.xml").decode("utf-8")


# ── O1 정상 다구간 ───────────────────────────────────────────────────────
def test_o1_the_whole_chain_produces_every_stage_artifact(tmp_path):
    summary, fake, run = _run(tmp_path)
    assert [stage for stage in b2.STAGES] == list(summary["stages"])
    for stage in b2.STAGES:
        manifest = summary["stages"][stage]
        assert manifest["stage_complete"] and not manifest["reused"], stage
        for relative, digest in manifest["outputs"].items():
            assert (run / relative).is_file()
    assert fake.calls == 2                       # episode 수만큼만 부른다
    document = _canonical(run)
    assert document["boundary"]["provider_name"] == "fixed_window_v1"
    assert document["prompt"]["prompt_version"] == "episode_content_v2"
    assert all(e["summary_mode"] == "MODEL_ABSTRACTIVE"
               for e in document["episodes"])
    assert (run / "S7/report.hwpx").is_file() and (run / "S7/report.md").is_file()


def test_o1_the_evidence_producer_is_recorded_as_b1(tmp_path):
    """ASR·caption raw의 생성자는 B1이다 — B2가 만든 것처럼 적지 않는다."""
    _, _, run = _run(tmp_path)
    meta = json.loads((run / "raw/asr/seg000000.meta.json").read_text(
        encoding="utf-8"))
    assert meta["producer"] == "m3_generate"
    assert meta["producer_version"] == "b1-code-head"


def test_o1_the_hwpx_passes_the_pure_python_validator(tmp_path):
    _, _, run = _run(tmp_path)
    owpml = _load(ROOT / "scripts/v2_1_hwpx_owpml.py", "owpml_check")
    assert owpml.validate_package(run / "S7/report.hwpx") == []


# ── O2 sparse eligible == 1 ──────────────────────────────────────────────
def test_o2_the_invented_narrative_never_reaches_canonical_or_hwpx(tmp_path):
    sparse = {**{i: "" for i in range(12)}, 9: EVIDENCE}
    # S4는 caption이 없다. 앞 구간(seg 0~5)에는 자격 근거가 0이라 **프롬프트가 거부**되고
    # LLM은 뒤 구간에서 한 번만 불린다 — payload도 그 하나만 둔다.
    payloads = ({"summary": INVENTED, "dialogue_note": "문을 연다고 말한다.",
                 "stt_cites": [9]},)
    _, _, run = _run(tmp_path, name="S4", payloads=payloads, asr=sparse,
                     window_sec=30.0)
    document = _canonical(run)
    second = document["episodes"][1]
    assert second["summary"] == EVIDENCE
    assert second["summary_mode"] == "SPARSE_EVIDENCE_DETERMINISTIC"

    body = _hwpx_text(run)
    for invented in ("건물", "훔친", "달아난다"):
        assert invented not in body, invented
    assert EVIDENCE in body

    # raw에는 **남아 있어야** 한다 — 권한만 뺏고 기록은 지우지 않는다.
    raw = "".join(path.read_text(encoding="utf-8")
                  for path in (run / "raw/llm").glob("*.raw"))
    assert INVENTED in raw


# ── O3a eligible == 0 ────────────────────────────────────────────────────
def test_o3a_no_eligible_evidence_means_no_llm_call(tmp_path):
    empty = {i: "" for i in range(12)}
    fake = _Fake(({"summary": "이 문장은 나오면 안 된다."},))
    summary, fake, run = _run(tmp_path, name="S5", asr=empty, caption=empty,
                              generate=fake, window_sec=30.0)
    assert fake.calls == 0                        # 프롬프트가 거부된다
    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))
    assert all(record["raw"] is None and record["status"] == "EMPTY"
               for record in index["episodes"])
    document = _canonical(run)
    assert all(e["summary"] is None and e["content_status"] == "EMPTY"
               for e in document["episodes"])
    assert summary["stages"]["S7"]["stage_complete"]      # 구조는 살아 있다


def test_o3a_the_report_does_not_invent_filler(tmp_path):
    empty = {i: "" for i in range(12)}
    _, _, run = _run(tmp_path, name="S5", asr=empty, caption=empty,
                     window_sec=30.0)
    markdown = (run / "S7/report.md").read_text(encoding="utf-8")
    assert "NO_RELIABLE_CONTENT" in markdown or "—" in markdown
    for forbidden in ("생성 실패", "요약 없음", "죄송"):
        assert forbidden not in markdown, forbidden


# ── O3b parse 실패 ───────────────────────────────────────────────────────
def test_o3b_a_parse_failure_keeps_the_raw_and_reports_the_status(tmp_path):
    fake = _Fake(("{ this is not json", {"summary": "정상 문장이다."}))
    summary, fake, run = _run(tmp_path, payloads=None, generate=fake)
    assert fake.calls == 2
    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))
    assert index["episodes"][0]["status"] == "PARSE_CONTRACT_FAILURE"
    raw = (run / index["episodes"][0]["raw"]).read_text(encoding="utf-8")
    assert raw == "{ this is not json"          # raw는 그대로 남는다

    document = _canonical(run)
    assert document["episodes"][0]["content_status"] == "PARSE_CONTRACT_FAILURE"
    assert document["episodes"][0]["summary"] is None
    assert document["episodes"][1]["summary"] == "정상 문장이다."   # 다음 구간은 진행된다
    assert summary["stages"]["S5"]["stage_complete"]


# ── R1 완전 재사용 ───────────────────────────────────────────────────────
def test_r1_an_exact_rerun_calls_no_stage_body(tmp_path):
    segments = _segments_file(tmp_path, "S1")
    config = _config(tmp_path)
    first = b2.orchestrate(tmp_path / "run", segments, config, video_id="S1",
                           run_id="b2-test", generate=_Fake(NORMAL_PAYLOADS),
                           generation=GENERATION,
                           producer_version="b1-code-head", window_sec=30.0)
    assert all(not m["reused"] for m in first["stages"].values())

    fake = _Fake(NORMAL_PAYLOADS)
    second = b2.orchestrate(tmp_path / "run", segments, config, video_id="S1",
                            run_id="b2-test", generate=fake,
                            generation=GENERATION,
                            producer_version="b1-code-head", window_sec=30.0)
    assert all(m["reused"] for m in second["stages"].values())
    assert fake.calls == 0                        # LLM을 다시 부르지 않는다


# ── R2 부분 stage ────────────────────────────────────────────────────────
def test_r2_an_artifact_without_a_success_marker_is_not_reused(tmp_path):
    segments = _segments_file(tmp_path, "S1")
    config = _config(tmp_path)
    run = tmp_path / "run"
    b2.orchestrate(run, segments, config, video_id="S1", run_id="b2-test",
                   generate=_Fake(NORMAL_PAYLOADS), generation=GENERATION,
                   producer_version="b1-code-head", window_sec=30.0)

    (run / "S2" / b2.SUCCESS).unlink()            # crash 도중 상태를 흉내낸다
    assert (run / "S2/raw_index.json").is_file()

    fake = _Fake(NORMAL_PAYLOADS)
    again = b2.orchestrate(run, segments, config, video_id="S1",
                           run_id="b2-test", generate=fake,
                           generation=GENERATION,
                           producer_version="b1-code-head", window_sec=30.0)
    assert not again["stages"]["S2"]["reused"] and fake.calls == 2
    for stage in ("S3", "S4", "S5", "S6", "S7"):
        assert not again["stages"][stage]["reused"], stage


# ── R3 산출물 변조 ───────────────────────────────────────────────────────
def test_r3_a_corrupted_artifact_forces_regeneration(tmp_path):
    segments = _segments_file(tmp_path, "S1")
    config = _config(tmp_path)
    run = tmp_path / "run"
    b2.orchestrate(run, segments, config, video_id="S1", run_id="b2-test",
                   generate=_Fake(NORMAL_PAYLOADS), generation=GENERATION,
                   producer_version="b1-code-head", window_sec=30.0)

    target = run / "S4/grounded.json"
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")

    again = b2.orchestrate(run, segments, config, video_id="S1",
                           run_id="b2-test", generate=_Fake(NORMAL_PAYLOADS),
                           generation=GENERATION,
                           producer_version="b1-code-head", window_sec=30.0)
    assert not again["stages"]["S4"]["reused"]
    assert again["stages"]["S2"]["reused"]        # 앞 stage는 건드리지 않는다
    assert not again["stages"]["S5"]["reused"]    # 뒤는 전부 stale


# ── R4 provenance 변경 ───────────────────────────────────────────────────
def test_r4_a_model_change_invalidates_every_stage(tmp_path):
    segments = _segments_file(tmp_path, "S1")
    config = _config(tmp_path)
    run = tmp_path / "run"
    b2.orchestrate(run, segments, config, video_id="S1", run_id="b2-test",
                   generate=_Fake(NORMAL_PAYLOADS), generation=GENERATION,
                   producer_version="b1-code-head", window_sec=30.0)

    other = GenerationConfig(model_id="fixture/other-model", do_sample=False,
                             max_new_tokens=128)
    fake = _Fake(NORMAL_PAYLOADS)
    again = b2.orchestrate(run, segments, config, video_id="S1",
                           run_id="b2-test", generate=fake, generation=other,
                           producer_version="b1-code-head", window_sec=30.0)
    assert all(not m["reused"] for m in again["stages"].values())
    assert fake.calls == 2


def test_r4_a_config_change_also_invalidates(tmp_path):
    segments = _segments_file(tmp_path, "S1")
    config = _config(tmp_path)
    run = tmp_path / "run"
    b2.orchestrate(run, segments, config, video_id="S1", run_id="b2-test",
                   generate=_Fake(NORMAL_PAYLOADS), generation=GENERATION,
                   producer_version="b1-code-head", window_sec=30.0)
    config.write_text("paths:\n  work: work_b2_changed\n", encoding="utf-8")
    again = b2.orchestrate(run, segments, config, video_id="S1",
                           run_id="b2-test", generate=_Fake(NORMAL_PAYLOADS),
                           generation=GENERATION,
                           producer_version="b1-code-head", window_sec=30.0)
    assert all(not m["reused"] for m in again["stages"].values())


# ── R5 S2 hard failure ──────────────────────────────────────────────────
def test_r5_a_hard_s2_failure_stops_the_run_and_leaves_no_complete_stage(tmp_path):
    calls = {"n": 0}

    def dies(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"summary": "첫 구간은 생성됐다."},
                              ensure_ascii=False)
        raise RuntimeError("CUDA out of memory")

    segments = _segments_file(tmp_path, "S1")
    run = tmp_path / "run"
    with pytest.raises(b2.StageError) as failure:
        b2.orchestrate(run, segments, _config(tmp_path), video_id="S1",
                       run_id="b2-test", generate=dies, generation=GENERATION,
                       producer_version="b1-code-head", window_sec=30.0)
    assert failure.value.stage == "S2"
    assert failure.value.kind == b2.ENVIRONMENT_BLOCKED

    assert b2.stage_manifest(run, "S2") is None            # 완료 표시 없음
    assert list((run / "raw/llm").glob("*.raw"))           # 일부 raw는 남는다
    for stage in ("S3", "S4", "S5", "S6", "S7"):
        assert not (run / stage).exists(), stage           # downstream 미실행


def test_r5_a_partial_s2_is_never_reused_as_complete(tmp_path):
    calls = {"n": 0}

    def dies(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"summary": "첫 구간."}, ensure_ascii=False)
        raise RuntimeError("CUDA out of memory")

    segments = _segments_file(tmp_path, "S1")
    run = tmp_path / "run"
    with pytest.raises(b2.StageError):
        b2.orchestrate(run, segments, _config(tmp_path), video_id="S1",
                       run_id="b2-test", generate=dies, generation=GENERATION,
                       producer_version="b1-code-head", window_sec=30.0)

    fake = _Fake(NORMAL_PAYLOADS)
    again = b2.orchestrate(run, segments, _config(tmp_path), video_id="S1",
                           run_id="b2-test", generate=fake,
                           generation=GENERATION,
                           producer_version="b1-code-head", window_sec=30.0)
    assert not again["stages"]["S2"]["reused"]
    assert fake.calls == 2                        # 전건 재생성 · 부분 병합 없음


# ── R6 S7 실패 ───────────────────────────────────────────────────────────
def test_r6_an_s7_failure_keeps_canonical_and_never_calls_the_com_path(
        tmp_path, monkeypatch):
    segments = _segments_file(tmp_path, "S1")
    run = tmp_path / "run"

    called = {"a1": 0}
    import sys as _sys

    class _Trap:
        def __getattr__(self, name):
            called["a1"] += 1
            raise AssertionError("A1(COM) 경로가 호출됐다")

    monkeypatch.setitem(_sys.modules, "pyhwpx", _Trap())
    monkeypatch.setattr(b2, "s7_hwpx",
                        lambda *a, **k: (_ for _ in ()).throw(
                            b2.StageError("S7", "HWPX_FAILED", "주입된 실패")))

    with pytest.raises(b2.StageError) as failure:
        b2.orchestrate(run, segments, _config(tmp_path), video_id="S1",
                       run_id="b2-test", generate=_Fake(NORMAL_PAYLOADS),
                       generation=GENERATION, producer_version="b1-code-head",
                       window_sec=30.0)
    assert failure.value.stage == "S7"
    assert (run / "S5/aar_canonical.json").is_file()
    assert b2.stage_manifest(run, "S5")["stage_complete"]
    assert b2.stage_manifest(run, "S7") is None
    assert called["a1"] == 0


def test_the_orchestrator_has_no_fallback_paths():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "pyhwpx" not in source
    assert "v2_1_hwpx_via_hangul" not in source
    assert "render_hwpx" not in source            # broken 렌더러 호출 0
    assert "load_in_4bit" not in source
    for smaller in ("3B", "Qwen2.5-VL-3B", "1.5B"):
        assert smaller not in source, smaller


def test_the_run_manifest_records_environment_and_provenance(tmp_path):
    summary, _, run = _run(tmp_path)
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["fingerprint"]["prompt_version"] == "episode_content_v2"
    assert manifest["generation"]["do_sample"] is False
    for key in ("python", "torch", "transformers", "cuda", "gpu", "git_head"):
        assert key in manifest["environment"], key
    assert manifest["model_provenance"]                     # 비어 있지 않다
