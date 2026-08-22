"""기확보 4편의 영상 길이를 재서 **canonical artifact로 남긴다.**

선정표본(`docs/P2_선정표본_2026-08-20.json`)에는 기확보 4편의 `duration_sec`이 없다 —
취득 시점에 기록하지 않았기 때문이다. 소비자가 없는 값을 `n_segments * 5`로 추정해
채우면 실제보다 최대 한 구간(≤5초) 느슨한 값이 사실처럼 남는다. 실측했더니 그 폭은
0.57~3.37초였다.

**추정하지 않고 재고, 재본 값을 출처와 함께 기록한다.** 측정은 m1과 같은 경로다 —
cv2 `frame_count / fps`이고 ffprobe duration이 아니다(격자가 어긋날 수 있다).
`ceil(duration / 5)`가 사전등록된 `n_segments`와 다르면 멈춘다.

산출물: `docs/P2_FREE4_duration_2026-08-22.json`. registry·intake 같은 소비자는 이
파일을 **참조**하고, 없으면 duration을 `unknown`으로 두되 조용히 행을 빼지 않는다.

재현: python scripts/p2_free4_duration.py --out docs/P2_FREE4_duration_2026-08-22.json
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
VIDEOS = ROOT / "data" / "videos"
OUT = ROOT / "docs" / "P2_FREE4_duration_2026-08-22.json"
SEG_LEN = 5
MEASUREMENT_PATH = "cv2 CAP_PROP_FRAME_COUNT / CAP_PROP_FPS (m1과 동일)"


class MeasureError(RuntimeError):
    pass


def load_selection(path=SELECTION) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))["selected"]


def targets(path=SELECTION) -> list:
    """길이가 기록되지 않은 영상만. **목록을 손으로 적지 않는다.**"""
    return sorted(r["source_id"] for r in load_selection(path)
                  if r.get("duration_sec") is None)


def _measure(path: Path) -> tuple:
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise MeasureError(f"cv2가 열지 못한다: {path}")
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if not fps:
        raise MeasureError(f"fps를 읽지 못한다: {path}")
    return n / fps, fps, int(n)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tool() -> str:
    try:
        import cv2
        return f"opencv-python {cv2.__version__}"
    except Exception:                                            # noqa: BLE001
        return "opencv-python (버전 확인 불가)"


def build(videos_dir=None, path=SELECTION) -> dict:
    vdir = Path(videos_dir) if videos_dir else VIDEOS
    sample = {r["source_id"]: r for r in load_selection(path)}
    tool, rows = _tool(), []
    for vid in targets(path):
        f = vdir / f"{vid}.mp4"
        if not f.is_file():
            raise MeasureError(f"{vid}: 영상 파일이 없다 ({f}) — 길이를 추정해 "
                               f"채우지 않는다")
        dur, fps, frames = _measure(f)
        derived = math.ceil(dur / SEG_LEN)
        pre = sample[vid]["n_segments"]
        if derived != pre:
            raise MeasureError(
                f"{vid}: 재본 길이 {dur:.2f}s의 격자 {derived}가 사전등록 "
                f"n_segments {pre}와 다르다 — 기록하지 않는다")
        rows.append({"video_id": vid, "duration_sec": round(dur, 2),
                     "fps": fps, "frame_count": frames,
                     "file_sha256": _sha256(f),
                     "n_segments_preregistered": pre,
                     "n_segments_derived": derived,
                     "grid_matches_preregistered": True,
                     "measurement_path": MEASUREMENT_PATH, "tool": tool,
                     "grid_upper_bound_sec": pre * SEG_LEN,
                     "looseness_closed_sec": round(pre * SEG_LEN - dur, 2)})
    return {
        "artifact": "p2_free4_duration",
        "why": ("선정표본에 이 4편의 duration_sec이 없다. 소비자가 n_segments*5로 "
                "추정하면 최대 한 구간만큼 느슨한 값이 사실로 남는다"),
        "measurement_path": MEASUREMENT_PATH,
        "source_ref": str(Path(path).relative_to(ROOT)).replace("\\", "/"),
        "seg_len_sec": SEG_LEN,
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                 capture_output=True,
                                 encoding="utf-8").stdout.strip(),
        "n": len(rows), "rows": rows,
        "not_claimed": ("취득 시점 provenance를 복원한 것이 아니다 — 현재 파일의 "
                        "바이트와 길이를 관측한 기록이다. legacy_exempt는 유지된다"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    rep = build()
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"{a.out} : {rep['n']}편")
    for r in rep["rows"]:
        print(f"  {r['video_id']:26s} {r['duration_sec']:9.2f}s  "
              f"격자 {r['n_segments_derived']} (사전등록 "
              f"{r['n_segments_preregistered']})  닫은 폭 "
              f"{r['looseness_closed_sec']:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
