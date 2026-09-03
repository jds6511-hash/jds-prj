"""B2 — v2.1 report orchestrator. B1 산출물을 소비해 정본·표현·HWPX까지 잇는다.

사전등록: `docs/finalization/V2_1_B2_ORCHESTRATOR_PREREG_2026-09-03.md`

```
S0 ingest validation     segments 계약 · provenance · raw store 적재(ASR·caption)
S1 canonical episodes    fixed_window_v1 · partition 검증
S2 raw LLM outputs       episode별 raw 응답 (parse 이전)
S3 parsed content        parse + merge_content
S4 grounding/sparse-safe binding → grounding → sparse safe mode
S5 aar                   aar_canonical.json + validate_aar
S6 presentation          highlight · lineage · synthesis · presentation
S7 HWPX                  A2'(순수 Python) + MD
```

두 가지를 하지 않는다.

```
M1~M3 재실행      하지 않는다. B1이 만든 evidence를 그대로 소비한다
자동 대체 경로     모델 하향 · 4bit 전환 · A1 렌더러 fallback — 전부 금지.
                실패는 명시적으로 실패한다
```

**stage 재사용은 지문이 맞을 때만.** 파일이 있다는 것만으로 완성된 stage로 보지 않는다.

```
재사용 조건   지문 5종 일치 (config · code · prompt version · prompt hash · model id)
             AND upstream artifact hash 일치
             AND 선언한 산출물 전부 존재
             AND 산출물 hash 일치
             AND stage_complete == true (`_SUCCESS.json`은 검증 후 **마지막에** 쓴다)
무효 전파     stage N이 무효면 N을 다시 만들고 N+1 ~ S7은 전부 stale로 버린다
부분 병합     금지. episode 23에서 죽은 S2의 raw 22건은 진단용으로만 남는다
```
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_aar import build_aar_canonical, validate_aar          # noqa: E402
from v2_1_binding import bind_cites                             # noqa: E402
from v2_1_content import merge_content                          # noqa: E402
from v2_1_episode import build_episodes                         # noqa: E402
from v2_1_fixed_window import FixedWindowV1                     # noqa: E402
from v2_1_grounding import (                                    # noqa: E402
    GroundedEpisode,
    Reason,
    apply_grounding,
    validate_grounding,
)
from v2_1_highlight import HighlightSpec, build_highlights       # noqa: E402
from v2_1_lineage import build_lineage                          # noqa: E402
from v2_1_llm_adapter import GenerationConfig                   # noqa: E402
from v2_1_parse import EMPTY, ParseResult, SegmentRegistry, parse_json_payload  # noqa: E402
from v2_1_presentation import build_presentation                # noqa: E402
from v2_1_presentation_input import presentation_input          # noqa: E402
from v2_1_prompt import PROMPT_VERSION, PromptError, build_episode_prompt, contract_hash  # noqa: E402
from v2_1_raw_store import RawStore                             # noqa: E402
from v2_1_render import render_markdown                         # noqa: E402
from v2_1_sanitation import classify_channel                    # noqa: E402
from v2_1_segments import legacy_segments_to_canonical          # noqa: E402
from v2_1_sparse_summary import apply_sparse_summary            # noqa: E402
from v2_1_synthesis import build_synthesis                      # noqa: E402
from v2_1_timeline import build_timeline                        # noqa: E402

STAGES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")
SUCCESS = "_SUCCESS.json"

#: hard stage failure. downstream을 돌리지 않는다.
ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
ENVIRONMENT_BLOCKED = "ENVIRONMENT_BLOCKED"


class StageError(RuntimeError):
    """stage 자체가 실패했다. episode 내용 실패와 **다르다.**"""

    def __init__(self, stage: str, kind: str, detail: str):
        super().__init__("%s %s: %s" % (stage, kind, detail))
        self.stage, self.kind, self.detail = stage, kind, detail


@dataclass(frozen=True)
class Fingerprint:
    """"환경이 같은가"를 재는 다섯. 산출물 무결성은 별도로 본다."""

    config_hash: str
    code_revision: str
    prompt_version: str
    prompt_hash: str
    model_id: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def code_revision() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def fingerprint(config_path: Path, model_id: str) -> Fingerprint:
    return Fingerprint(
        config_hash=sha256_file(config_path),
        code_revision=code_revision(),
        prompt_version=PROMPT_VERSION,
        prompt_hash=contract_hash(),
        model_id=model_id,
    )


# ── stage 실행기 ─────────────────────────────────────────────────────────
def _stage_dir(run: Path, stage: str) -> Path:
    return run / stage


def _manifest_path(run: Path, stage: str) -> Path:
    return _stage_dir(run, stage) / SUCCESS


def stage_manifest(run: Path, stage: str) -> dict | None:
    path = _manifest_path(run, stage)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def artifact_hash(run: Path, stage: str) -> str | None:
    """그 stage 산출물 전체의 지문. 없으면 None이다."""
    manifest = stage_manifest(run, stage)
    if not manifest:
        return None
    joined = json.dumps(manifest["outputs"], sort_keys=True)
    return sha256_bytes(joined.encode("utf-8"))


def reusable(run: Path, stage: str, print_: Fingerprint, upstream: str | None) -> bool:
    """존재만으로 신뢰하지 않는다 — 지문·upstream·산출물 hash·완료 표시를 전부 본다."""
    manifest = stage_manifest(run, stage)
    if not manifest or not manifest.get("stage_complete"):
        return False
    if manifest.get("fingerprint") != asdict(print_):
        return False
    if manifest.get("upstream_artifact_hash") != upstream:
        return False
    outputs = manifest.get("outputs") or {}
    if not outputs:
        return False
    for relative, digest in outputs.items():
        path = run / relative
        if not path.is_file() or sha256_file(path) != digest:
            return False
    return True


def _purge(run: Path, stage: str, owned: tuple = ()) -> None:
    shutil.rmtree(_stage_dir(run, stage), ignore_errors=True)
    for relative in owned:
        shutil.rmtree(run / relative, ignore_errors=True)


def _stale_downstream(run: Path, stage: str, owned: dict) -> None:
    """무효 전파는 단방향이다 — N을 다시 만들면 N+1 이후는 전부 버린다."""
    index = STAGES.index(stage)
    for later in STAGES[index + 1:]:
        _purge(run, later, owned.get(later, ()))


#: stage가 소유한 stage 디렉터리 밖 경로. 재생성 시 함께 버린다.
OWNED = {"S0": ("raw/asr", "raw/vlm"), "S2": ("raw/llm",)}


def run_stage(run: Path, stage: str, print_: Fingerprint, upstream: str | None,
              body) -> dict:
    """stage 하나를 돌리거나 재사용한다. 완료 표시는 검증 뒤 마지막에 쓴다."""
    if reusable(run, stage, print_, upstream):
        manifest = stage_manifest(run, stage)
        manifest["reused"] = True
        return manifest

    _purge(run, stage, OWNED.get(stage, ()))
    _stale_downstream(run, stage, OWNED)
    directory = _stage_dir(run, stage)
    directory.mkdir(parents=True, exist_ok=True)

    started = time.time()
    declared = body(directory)                  # 산출물 상대경로 목록을 돌려준다
    outputs = {}
    for relative in declared:
        path = run / relative
        if not path.is_file():
            raise StageError(stage, "MISSING_OUTPUT", str(relative))
        outputs[str(relative)] = sha256_file(path)

    manifest = {
        "stage": stage,
        "fingerprint": asdict(print_),
        "upstream_artifact_hash": upstream,
        "outputs": outputs,
        "stage_complete": True,
        "reused": False,
        "wall_seconds": round(time.time() - started, 2),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    # **마지막에** 쓴다 — 도중에 죽은 실행이 완성 stage로 오인되지 않게.
    _manifest_path(run, stage).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


# ── 공용 로더 ────────────────────────────────────────────────────────────
def _store(run: Path, video_id: str, run_id: str) -> RawStore:
    return RawStore(run / "raw", run_id=run_id, video_id=video_id)


def _load_world(run: Path, video_id: str, run_id: str):
    """S0 산출물에서 canonical segments · 판정 · timeline을 되세운다."""
    ingest = json.loads((run / "S0/ingest.json").read_text(encoding="utf-8"))
    segments = legacy_segments_to_canonical(ingest["legacy_segments"])
    store = _store(run, video_id, run_id)
    judged = {}
    for source_type, channel in ingest["channels"].items():
        judged[source_type] = classify_channel(
            {int(k): v for k, v in channel.items()}, source_type)
    timeline = build_timeline(segments, judged)
    return ingest, segments, store, timeline


def _load_episodes(run: Path, segments, timeline):
    spans = [tuple(span) for span in
             json.loads((run / "S1/episodes.json").read_text(
                 encoding="utf-8"))["spans"]]
    return build_episodes(spans, segments, timeline=timeline)


# ── stage 본체 ───────────────────────────────────────────────────────────
def s0_ingest(directory: Path, run: Path, segments_path: Path, video_id: str,
              run_id: str, producer_version: str):
    document = json.loads(segments_path.read_text(encoding="utf-8"))
    legacy = document["segments"]
    segments = legacy_segments_to_canonical(legacy)          # 계약 검증도 여기서 난다

    # 채널 키는 **canonical segment_id**로 만든다. legacy 필드(idx/start/end)는
    # adapter 밖에서 소비하지 않는다(A-01 · OPEN-1). 짝은 순서로 맞춘다 —
    # adapter가 1:1 순서 보존이고 그 계약은 A-01이 잰다.
    channels = {"asr": {}, "vlm": {}}
    for segment, row in zip(segments, legacy):
        key = str(segment.segment_id)
        channels["asr"][key] = row.get("subtitle") or ""
        channels["vlm"][key] = row.get("caption") or ""
    store = _store(run, video_id, run_id)
    for source_type, channel in channels.items():
        for segment_id, text in channel.items():
            # 생성자는 **B1**이다. B2가 만든 것처럼 적지 않는다.
            store.store(segment_id=int(segment_id), source_type=source_type,
                        producer="m3_generate",
                        producer_version=producer_version, payload=text)

    index = sorted(
        (str(path.relative_to(run)), sha256_file(path))
        for path in (run / "raw").rglob("*") if path.is_file())
    payload = {
        "video_id": video_id,
        "segment_count": len(segments),
        "duration_sec": document.get("duration_sec"),
        "provenance": document.get("provenance"),
        "source_segments_sha256": sha256_file(segments_path),
        "legacy_segments": legacy,
        "channels": channels,
        "raw_index": index,
    }
    (directory / "ingest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return ["S0/ingest.json"]


def s1_episodes(directory: Path, run: Path, video_id: str, run_id: str,
                window_sec: float | None):
    _, segments, _, timeline = _load_world(run, video_id, run_id)
    provider = FixedWindowV1()
    config = {"window_sec": window_sec} if window_sec else {}
    boundary = provider(segments, config=config)
    positions = list(boundary.boundary_positions) + [len(segments)]
    spans = [(positions[i], positions[i + 1] - 1)
             for i in range(len(positions) - 1)]
    episodes = build_episodes(spans, segments, timeline=timeline)  # partition 검증
    (directory / "episodes.json").write_text(json.dumps({
        "provider_name": boundary.provider_name,
        "provider_version": boundary.provider_version,
        "provider_config": dict(boundary.provider_config),
        "spans": [list(span) for span in spans],
        "episode_ids": [episode.episode_id for episode in episodes],
    }, ensure_ascii=False), encoding="utf-8")
    return ["S1/episodes.json"]


def s2_raw(directory: Path, run: Path, video_id: str, run_id: str, generate,
           generation: GenerationConfig):
    _, segments, store, timeline = _load_world(run, video_id, run_id)
    episodes = _load_episodes(run, segments, timeline)
    registry = SegmentRegistry(segments)
    records = []
    counters = {"llm_calls": 0, "prompt_refusals": 0, "llm_failures": 0,
                "retries": 0}
    for index, episode in enumerate(episodes):
        episode_started = time.time()
        try:
            bundle = build_episode_prompt(episode, timeline, store)
        except PromptError as error:
            # **episode 내용 실패다.** orchestrator 실패로 올리지 않는다(ERR-009).
            counters["prompt_refusals"] += 1
            records.append({"episode_id": episode.episode_id, "raw": None,
                            "status": EMPTY, "reason": "no_usable_evidence",
                            "detail": str(error),
                            "wall_seconds": round(time.time() - episode_started, 2)})
            continue
        try:
            counters["llm_calls"] += 1
            raw = generate(bundle.text)
        except Exception as error:                       # noqa: BLE001
            counters["llm_failures"] += 1
            kind = (ENVIRONMENT_BLOCKED
                    if "out of memory" in str(error).lower()
                    else ENVIRONMENT_FAILURE)
            # **재시도하지 않는다.** 설정을 낮춰 다시 부르는 경로를 만들지 않는다.
            (directory / "s2_partial.json").write_text(json.dumps(
                {"counters": counters, "episodes": records}, ensure_ascii=False),
                encoding="utf-8")
            raise StageError("S2", kind, "%s: %s" % (type(error).__name__, error))
        outcome = store.store_then_parse(
            lambda text: parse_json_payload(text, registry),
            segment_id=index, source_type="llm", producer="b2_orchestrator",
            producer_version=generation.model_id, payload=raw)
        records.append({
            "episode_id": episode.episode_id,
            "raw": str(store.load("llm", index).raw_path.relative_to(run)),
            "status": outcome.parsed.status,
            "prompt_cites": list(bundle.claim_cites),
            "raw_chars": len(raw),
            "wall_seconds": round(time.time() - episode_started, 2),
        })
    (directory / "raw_index.json").write_text(json.dumps({
        "generation": generation.as_dict(),
        "counters": counters,
        "episodes": records,
    }, ensure_ascii=False), encoding="utf-8")
    return ["S2/raw_index.json"]


def s3_content(directory: Path, run: Path, video_id: str, run_id: str):
    _, segments, store, timeline = _load_world(run, video_id, run_id)
    episodes = _load_episodes(run, segments, timeline)
    registry = SegmentRegistry(segments)
    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))

    payload = []
    for episode, record in zip(episodes, index["episodes"]):
        if record["raw"] is None:
            outcome = ParseResult(status=record["status"],
                                  reason=record.get("reason"))
        else:
            raw = (run / record["raw"]).read_text(encoding="utf-8")
            outcome = parse_json_payload(raw, registry)
        result = merge_content(episode, outcome)
        payload.append({
            "episode_id": episode.episode_id,
            "content_status": result.content_status,
            "reason": result.reason,
            "error": result.error,
            "error_type": result.error_type,
            "summary": result.content.summary if result.content else None,
            "dialogue_note": result.content.dialogue_note if result.content else None,
            "stt_cites": list(result.content.stt_cites) if result.content else [],
            "ignored_fields": list(result.ignored_fields),
        })
    (directory / "content.json").write_text(
        json.dumps({"episodes": payload}, ensure_ascii=False), encoding="utf-8")
    return ["S3/content.json"]


def s4_grounding(directory: Path, run: Path, video_id: str, run_id: str):
    _, segments, store, timeline = _load_world(run, video_id, run_id)
    episodes = _load_episodes(run, segments, timeline)
    registry = SegmentRegistry(segments)
    content = json.loads((run / "S3/content.json").read_text(encoding="utf-8"))

    payload = []
    for episode, record in zip(episodes, content["episodes"]):
        outcome = ParseResult(
            status=record["content_status"],
            value=None if record["summary"] is None else {
                "summary": record["summary"],
                **({"dialogue_note": record["dialogue_note"]}
                   if record["dialogue_note"] else {}),
                **({"stt_cites": record["stt_cites"]}
                   if record["stt_cites"] else {}),
            },
            reason=record["reason"], error=record["error"],
            error_type=record["error_type"])
        result = merge_content(episode, outcome)
        binding = bind_cites(result, timeline, registry)
        verdict = validate_grounding(binding, store)
        grounded = apply_sparse_summary(apply_grounding(binding, verdict),
                                        episode, timeline, store)
        payload.append({
            "episode_id": grounded.episode_id,
            "content_status": grounded.content_status,
            "summary": grounded.summary,
            "dialogue_note": grounded.dialogue_note,
            "support_span": dict(grounded.support_span),
            "anchor_cites": list(grounded.anchor_cites),
            "source": grounded.source,
            "provenance": list(grounded.provenance),
            "grounding_status": grounded.grounding_status,
            "grounding_reasons": [
                {"code": reason.code, "detail": reason.detail,
                 "cite": reason.cite, "status": reason.status}
                for reason in grounded.grounding_reasons],
            "summary_mode": grounded.summary_mode,
        })
    (directory / "grounded.json").write_text(
        json.dumps({"episodes": payload}, ensure_ascii=False), encoding="utf-8")
    return ["S4/grounded.json"]


def _grounded_objects(run: Path):
    document = json.loads((run / "S4/grounded.json").read_text(encoding="utf-8"))
    for record in document["episodes"]:
        yield GroundedEpisode(
            episode_id=record["episode_id"],
            content_status=record["content_status"],
            summary=record["summary"],
            dialogue_note=record["dialogue_note"],
            support_span=record["support_span"],
            anchor_cites=tuple(record["anchor_cites"]),
            source=record["source"],
            provenance=tuple(record["provenance"]),
            grounding_status=record["grounding_status"],
            grounding_reasons=tuple(
                Reason(r["code"], r["detail"], r["cite"], r["status"])
                for r in record["grounding_reasons"]),
            summary_mode=record["summary_mode"],
        )


def s5_aar(directory: Path, run: Path, video_id: str, run_id: str):
    _, segments, _, timeline = _load_world(run, video_id, run_id)
    boundary = json.loads((run / "S1/episodes.json").read_text(encoding="utf-8"))
    document = build_aar_canonical(
        video_id=video_id, run_id=run_id, segments=segments,
        grounded=list(_grounded_objects(run)), timeline=timeline)
    document["boundary"] = {
        "provider_name": boundary["provider_name"],
        "provider_version": boundary["provider_version"],
        "provider_config": boundary["provider_config"],
    }
    document["prompt"] = {"prompt_version": PROMPT_VERSION,
                          "prompt_hash": contract_hash()}
    verdict = validate_aar(document)
    if not verdict.ok:
        raise StageError("S5", "INVALID_CANONICAL", "; ".join(verdict.failures))
    (directory / "aar_canonical.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    return ["S5/aar_canonical.json"]


def s6_presentation(directory: Path, run: Path):
    document = json.loads(
        (run / "S5/aar_canonical.json").read_text(encoding="utf-8"))
    presented = presentation_input(document)
    groups = [(episode.episode_id,) for episode in presented.episodes]
    highlights = build_highlights(presented, [HighlightSpec(g) for g in groups])
    lineage = build_lineage(presented, highlights)
    synthesis = build_synthesis(presented, lineage)
    presentation = build_presentation(presented, highlights)
    (directory / "presentation.json").write_text(json.dumps({
        "groups": [list(group) for group in groups],
        "highlights": [{
            "highlight_id": item.highlight_id,
            "start_sec": item.start_sec, "end_sec": item.end_sec,
            "source_episode_ids": list(item.source_episode_ids),
            "summary": item.summary, "summary_status": item.summary_status,
            "summary_source_episode_ids": list(item.summary_source_episode_ids),
            "excluded_summary_episode_ids": list(
                item.excluded_summary_episode_ids),
        } for item in presentation],
        "synthesis": {
            "conclusion": synthesis.conclusion,
            "source_episode_ids": list(synthesis.source_episode_ids),
        },
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return ["S6/presentation.json"]


def s7_hwpx(directory: Path, run: Path, config_path: Path, video_id: str,
            run_id: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "v2_1_hwpx_owpml", ROOT / "scripts/v2_1_hwpx_owpml.py")
    owpml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owpml)

    from v2_1_run import Manifest

    document = json.loads(
        (run / "S5/aar_canonical.json").read_text(encoding="utf-8"))
    groups = tuple(tuple(g) for g in json.loads(
        (run / "S6/presentation.json").read_text(encoding="utf-8"))["groups"])
    manifest = Manifest(video_id=video_id, run_id=run_id,
                        analysis_mode="report",
                        config_hash=sha256_file(config_path)[:16],
                        code_git_head=code_revision()[:8])
    try:
        # A2'가 primary다. 실패하면 **여기서 실패한다** — A1으로 넘어가지 않는다.
        owpml.render(document, directory / "report.hwpx", manifest=manifest,
                     groups=groups)
    except SystemExit as error:
        raise StageError("S7", "HWPX_FAILED", str(error)) from None

    presented = presentation_input(document)
    highlights = build_highlights(
        presented, [HighlightSpec(group) for group in groups])
    synthesis = build_synthesis(presented, build_lineage(presented, highlights))
    (directory / "report.md").write_text(
        render_markdown(manifest, build_presentation(presented, highlights),
                        synthesis), encoding="utf-8")
    return ["S7/report.hwpx", "S7/report.md"]


# ── 오케스트레이션 ───────────────────────────────────────────────────────
def environment() -> dict:
    """실행 환경을 적는다. 알 수 없는 값은 **추정하지 않고** unavailable로 둔다."""
    record = {"python": sys.version.split()[0], "git_head": code_revision()}
    for name in ("torch", "transformers"):
        try:
            module = __import__(name)
            record[name] = getattr(module, "__version__", "unknown")
        except Exception:                                # noqa: BLE001
            record[name] = "unavailable"
    try:
        import torch

        record["cuda"] = torch.version.cuda or "unavailable"
        record["gpu"] = (torch.cuda.get_device_name(0)
                         if torch.cuda.is_available() else "unavailable")
    except Exception:                                    # noqa: BLE001
        record["cuda"] = record["gpu"] = "unavailable"
    return record


class GpuPoll:
    """실행 내내 VRAM·이용률을 적는다. 계측만 하고 실행에 개입하지 않는다."""

    def __init__(self, path: Path, interval: float = 5.0):
        self.path, self.interval = path, interval
        self.samples = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            while not self._stop.is_set():
                out = subprocess.run(
                    ["nvidia-smi",
                     "--query-gpu=memory.used,memory.total,utilization.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True)
                if out.returncode == 0 and out.stdout.strip():
                    used, total, util = [
                        int(x) for x in out.stdout.strip().splitlines()[0].split(", ")]
                    sample = {"t": round(time.time(), 1), "used_mib": used,
                              "total_mib": total, "util_pct": util}
                    self.samples.append(sample)
                    handle.write(json.dumps(sample) + "\n")
                    handle.flush()
                self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(timeout=self.interval * 2)

    def summary(self) -> dict:
        used = [s["used_mib"] for s in self.samples]
        if not used:
            return {"samples": 0, "note": "측정 실패 — 값을 추정해 적지 않는다"}
        ordered = sorted(used)
        return {"samples": len(used), "interval_sec": self.interval,
                "peak_mib": max(used), "median_mib": ordered[len(ordered) // 2],
                "p95_mib": ordered[max(int(len(ordered) * 0.95) - 1, 0)],
                "total_mib": self.samples[0]["total_mib"],
                "util_peak_pct": max(s["util_pct"] for s in self.samples)}


def distributions(run: Path) -> dict:
    """산출물에서 분포를 센다. 판정하지 않는다."""
    def counts(values):
        table = {}
        for value in values:
            table[value] = table.get(value, 0) + 1
        return table

    index = json.loads((run / "S2/raw_index.json").read_text(encoding="utf-8"))
    document = json.loads(
        (run / "S5/aar_canonical.json").read_text(encoding="utf-8"))
    episodes = document["episodes"]
    per_episode = [record.get("wall_seconds") for record in index["episodes"]
                   if record.get("wall_seconds") is not None]
    return {
        "expected_episodes": len(index["episodes"]),
        "canonical_episodes": len(episodes),
        "counters": index.get("counters", {}),
        "parse_status": counts(record["status"] for record in index["episodes"]),
        "content_status": counts(e["content_status"] for e in episodes),
        "grounding_status": counts(e["grounding_status"] for e in episodes),
        "summary_mode": counts(e["summary_mode"] for e in episodes),
        "raw_outputs_present": sum(
            1 for record in index["episodes"]
            if record["raw"] and (run / record["raw"]).is_file()),
        "episode_wall_seconds": {
            "n": len(per_episode),
            "total": round(sum(per_episode), 1),
            "min": min(per_episode) if per_episode else None,
            "max": max(per_episode) if per_episode else None,
            "mean": round(sum(per_episode) / len(per_episode), 2) if per_episode else None,
        },
    }


def orchestrate(run: Path, segments_path: Path, config_path: Path, *,
                video_id: str, run_id: str, generate, generation: GenerationConfig,
                producer_version: str, window_sec: float | None = None,
                model_provenance: dict | None = None,
                poll_gpu: bool = False) -> dict:
    run.mkdir(parents=True, exist_ok=True)
    print_ = fingerprint(config_path, generation.model_id)

    bodies = {
        "S0": lambda d: s0_ingest(d, run, segments_path, video_id, run_id,
                                  producer_version),
        "S1": lambda d: s1_episodes(d, run, video_id, run_id, window_sec),
        "S2": lambda d: s2_raw(d, run, video_id, run_id, generate, generation),
        "S3": lambda d: s3_content(d, run, video_id, run_id),
        "S4": lambda d: s4_grounding(d, run, video_id, run_id),
        "S5": lambda d: s5_aar(d, run, video_id, run_id),
        "S6": lambda d: s6_presentation(d, run),
        "S7": lambda d: s7_hwpx(d, run, config_path, video_id, run_id),
    }

    manifests, upstream = {}, None
    poll = GpuPoll(run / "gpu_poll.jsonl") if poll_gpu else None
    try:
        if poll:
            poll.__enter__()
        for stage in STAGES:
            manifests[stage] = run_stage(run, stage, print_, upstream,
                                         bodies[stage])
            upstream = artifact_hash(run, stage)
    finally:
        if poll:
            poll.__exit__(None, None, None)

    summary = {
        "video_id": video_id,
        "run_id": run_id,
        "fingerprint": asdict(print_),
        "environment": environment(),
        "model_provenance": model_provenance or {"note": "unavailable"},
        "generation": generation.as_dict(),
        "stages": manifests,
        "gpu": poll.summary() if poll else {"samples": 0, "note": "폴링 없음"},
        "distributions": distributions(run),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (run / "run_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def transformers_provider(generation: GenerationConfig, *, llm_4bit: bool = False):
    """서버용 생성기. 모델을 못 올리면 **명시적으로 실패한다.**

    더 작은 모델이나 4bit로 자동 전환하지 않는다 — 무엇이 실행됐는지 사후에
    모르게 되기 때문이다(사전등록 §6).
    """
    if llm_4bit:
        raise StageError("S2", ENVIRONMENT_FAILURE,
                         "llm_4bit=true는 이 경로에서 허용되지 않는다 (서버 계약: false)")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as error:                           # noqa: BLE001
        raise StageError("S2", ENVIRONMENT_FAILURE,
                         "transformers 사용 불가: %s" % error) from None
    try:
        tokenizer = AutoTokenizer.from_pretrained(generation.model_id)
        model = AutoModelForCausalLM.from_pretrained(
            generation.model_id, torch_dtype=torch.bfloat16, device_map="auto")
    except Exception as error:                           # noqa: BLE001
        raise StageError("S2", ENVIRONMENT_FAILURE,
                         "모델 로드 실패: %s" % error) from None

    # 로드 **직후** 실제 값에서 읽는다. 얻지 못하면 unavailable로 두고 꾸미지 않는다.
    def _snapshot(obj) -> str:
        for attr in ("_commit_hash", "_name_or_path"):
            value = getattr(obj, attr, None)
            if value and "snapshots" in str(value):
                return Path(str(value)).parts[-1]
            if attr == "_commit_hash" and value:
                return str(value)
        return "unavailable"

    provenance = {
        "model_id": generation.model_id,
        "resolved_revision": _snapshot(model.config),
        "model_local_path": str(getattr(model.config, "_name_or_path", "unavailable")),
        "tokenizer_revision": _snapshot(tokenizer),
        "tokenizer_local_path": str(getattr(tokenizer, "name_or_path", "unavailable")),
        "torch_dtype": str(getattr(model, "dtype", "unavailable")),
        "llm_4bit": False,
        "do_sample": generation.do_sample,
        "max_new_tokens": generation.max_new_tokens,
    }

    def generate(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        output = model.generate(**inputs, do_sample=generation.do_sample,
                                max_new_tokens=generation.max_new_tokens)
        return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True)

    return generate, provenance


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", required=True, help="B1 segments.json")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--producer-version", required=True,
                        help="B1 code revision — evidence의 생성자 기록")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--window-sec", type=float, default=None)
    parser.add_argument("--poll-gpu", action="store_true",
                        help="5초 간격 VRAM·이용률 기록")
    parser.add_argument("--clean", action="store_true",
                        help="run 디렉터리를 비우고 처음부터 — 첫 실행은 이것으로 한다")
    args = parser.parse_args(argv)

    run = Path(args.run_dir)
    if args.clean and run.exists():
        shutil.rmtree(run)

    generation = GenerationConfig(model_id=args.model_id, do_sample=False,
                                  max_new_tokens=args.max_new_tokens)
    generate, provenance = transformers_provider(generation)
    summary = orchestrate(
        run, Path(args.segments), Path(args.config),
        video_id=args.video_id, run_id=args.run_id, generate=generate,
        generation=generation, producer_version=args.producer_version,
        window_sec=args.window_sec, model_provenance=provenance,
        poll_gpu=args.poll_gpu)
    print(json.dumps({
        "stages": {stage: {"reused": m["reused"],
                           "wall_seconds": m.get("wall_seconds")}
                   for stage, m in summary["stages"].items()},
        "gpu": summary["gpu"],
        "distributions": summary["distributions"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
