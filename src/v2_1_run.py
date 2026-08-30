"""v2.1 run layout + manifest — 산출물의 자리와 출처 (A-02).

```
<root>/<video_id>/<run_id>/
    manifest.json
    media/ raw/ evidence/ structure/ canonical/ presentation/ rendered/
```

manifest는 **provenance만** 담는다. 어떤 영상을, 어떤 run에서, 어떤 모드로, 어떤
config와 어떤 코드로 만들었는지다. parse·sanitation 판정 상태를 여기서 다시
정의하지 않는다 — 그것은 각 계층의 산출물에 이미 있고, 두 벌이 되면 갈라진다.

`analysis_mode`는 실행 불변식이다.

```python
if manifest.analysis_mode != "report":
    raise RenderRefused(...)
```

report로 자동 보정하지 않는다. 보정하면 15~20초 간격의 미리보기 산출물이 정식
근거로 둔갑한다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

#: 스펙이 정한 세 모드. preview는 미리보기, report는 정식, hybrid는 5초 유지 +
#: scene-change frame을 추가 근거로만 쓰는 모드다.
ANALYSIS_MODES = ("preview", "report", "hybrid")

RUN_DIRS = (
    "media",
    "raw",
    "evidence",
    "structure",
    "canonical",
    "presentation",
    "rendered",
)

MANIFEST_NAME = "manifest.json"


class RunError(RuntimeError):
    """run 레이아웃 계약 위반."""


class RenderRefused(RuntimeError):
    """정식 보고서 렌더 거부. 모드를 바꿔서 통과시키지 않는다."""


@dataclass(frozen=True, slots=True)
class Manifest:
    video_id: str
    run_id: str
    analysis_mode: str
    config_hash: str
    code_git_head: str


@dataclass(frozen=True, slots=True)
class RunLayout:
    path: Path
    manifest: Manifest

    def dir(self, name: str) -> Path:
        if name not in RUN_DIRS:
            raise RunError("unknown run directory: %s" % name)
        return self.path / name


def _require(value: str, field: str) -> str:
    if not str(value).strip():
        raise RunError("%s is required" % field)
    return value


def create_run(
    root: Path | str,
    *,
    video_id: str,
    run_id: str,
    analysis_mode: str,
    config_hash: str,
    code_git_head: str,
) -> RunLayout:
    """run 뼈대를 만든다. 기존 run을 덮어쓰지 않는다."""
    manifest = Manifest(
        video_id=_require(video_id, "video_id"),
        run_id=_require(run_id, "run_id"),
        analysis_mode=analysis_mode,
        config_hash=_require(config_hash, "config_hash"),
        code_git_head=_require(code_git_head, "code_git_head"),
    )
    if analysis_mode not in ANALYSIS_MODES:
        raise RunError(
            "unknown analysis_mode %r (declared: %s)"
            % (analysis_mode, ", ".join(ANALYSIS_MODES))
        )

    path = Path(root) / manifest.video_id / manifest.run_id
    if path.exists():
        raise RunError("run already exists: %s" % path)

    for name in RUN_DIRS:
        (path / name).mkdir(parents=True)
    (path / MANIFEST_NAME).write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return RunLayout(path=path, manifest=manifest)


def load_manifest(run_path: Path | str) -> Manifest:
    data = json.loads((Path(run_path) / MANIFEST_NAME).read_text(encoding="utf-8"))
    return Manifest(**data)


def require_report_mode(manifest: Manifest) -> None:
    """정식 보고서 렌더의 전제. 위반이면 여기서 멈춘다."""
    if manifest.analysis_mode != "report":
        raise RenderRefused(
            "report rendering requires analysis_mode=report (got %r)"
            % manifest.analysis_mode
        )


def hash_config(config: Mapping[str, Any]) -> str:
    """키 순서와 무관한 config 지문."""
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_git_head(root: Path | str) -> str:
    """실행 시점 commit. `.git`을 직접 읽는다 — 하위 프로세스를 띄우지 않는다."""
    git = Path(root) / ".git"
    head_file = git / "HEAD"
    if not head_file.is_file():
        raise RunError("no git repository at %s" % root)
    head = head_file.read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return head
    ref = head.split(" ", 1)[1].strip()
    ref_file = git / ref
    if ref_file.is_file():
        return ref_file.read_text(encoding="utf-8").strip()
    packed = git / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    raise RunError("no git ref for %s" % ref)
