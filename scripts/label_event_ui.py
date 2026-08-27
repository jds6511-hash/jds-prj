"""사건 목록 작성 UI — 클릭으로 사건 범위를 잡고 한 줄만 적는다. **로컬 전용.**

2,075구간을 CSV에 손으로 타이핑하면 못 끝낸다. 이 도구가 줄이는 것은 **입력량**이고,
사건 정의는 줄이지 않는다 — 정의는 사전등록에 있고 여기서 바꾸지 않는다
(`docs/preregistration/event_inventory_사전등록_2026-08-18.md` §2).

```
사람이 하는 것   ① 시작 썸네일 클릭  ② 끝 썸네일 Shift+클릭  ③ 한 줄 설명
코드가 하는 것   event_id · start_sec · end_sec · 자동 저장 · CSV 내보내기
```

**blind 규약을 도구로 강제한다.**

```
내보내는 것   프레임 이미지 · 구간 번호 · 시각 · 영상 픽셀(무음 재생)
막는 것      caption · subtitle · STT · 검색 결과 · score · rank · M8 리포트 · pilot 수치
강제 방법     segments.json을 `label_guard.load_segments_for_labeling`으로만 읽는다
             (allowlist: idx · start · end · rep_frame). 대상 영상은 **동결 패널 8편만**
```

산출물은 `{video_id}.draft.json`이고 상태는 `DRAFT`다. `--export`로 사전등록 CSV 양식
(`start_sec,end_sec,event,unclear`)으로 내보낸 뒤 기존 `event_inventory_kit.py`의
`validate` → `freeze`를 그대로 탄다. **동결 경로를 새로 만들지 않는다.**

실행:
    python scripts/label_event_ui.py --serve
    python scripts/label_event_ui.py --export --video-id <video_id>
"""
import argparse
import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                   # noqa: E402
import label_guard                                              # noqa: E402

PANEL_MANIFEST = ROOT / "docs" / "finalization" / "m8_c2_panel_manifest_2026-08-27.json"
INVENTORY = ROOT / "label_kit" / "event_inventory"
HTML = Path(__file__).resolve().parent / "label_event_ui.html"


class UIError(RuntimeError):
    pass


def _rel(p) -> str:
    """저장소 밖(테스트 tmp) 경로면 절대경로 그대로 남긴다 — registry의 규칙과 같다."""
    p = Path(p)
    return (str(p.relative_to(ROOT)).replace("\\", "/")
            if p.is_relative_to(ROOT) else str(p))


def panel_videos(manifest=PANEL_MANIFEST) -> list:
    """작업 대상은 **동결 패널뿐이다.** test split·다른 실험 자원은 열 수 없다."""
    return list(json.loads(Path(manifest).read_text(encoding="utf-8"))["final_panel"])


def draft_path(video_id: str, root=INVENTORY) -> Path:
    return Path(root) / f"{video_id}.draft.json"


def load_draft(video_id: str, root=INVENTORY) -> dict:
    p = draft_path(video_id, root)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"video_id": video_id, "status": "DRAFT", "events": []}


def next_event_id(events: list) -> str:
    used = {e.get("event_id") for e in events}
    for i in range(1, 1000):
        eid = f"E{i:03d}"
        if eid not in used:
            return eid
    raise UIError("event_id 한도 초과")


def normalize(draft: dict, segs: list, duration_sec: float | None = None) -> dict:
    """사람이 준 것은 구간 번호뿐 — **시각은 코드가 채운다.**

    사람이 초를 타이핑하면 오탈자가 섞이고, 그 오탈자는 V1~V4 검증을 통과할 수도 있다.
    """
    by_idx = {s["idx"]: s for s in segs}
    out, used = [], set()
    for e in draft.get("events", []):
        a, b = int(e["start_seg"]), int(e["end_seg"])
        if a > b:
            a, b = b, a
        if a not in by_idx or b not in by_idx:
            raise UIError(f"구간 번호가 범위 밖이다: {a}~{b}")
        # **번호를 목록 길이로 매기지 않는다.** 가운데 사건을 지운 뒤 새로 추가하면
        # 번호가 재사용돼 같은 id가 둘 생긴다(실측 사고: E007 둘·E006 없음).
        # id는 UI가 사건을 고르고 지우는 유일한 손잡이라 겹치면 엉뚱한 사건이 지워진다.
        eid = e.get("event_id")
        if not eid or eid in used:            # 중복은 먼저 온 것을 살리고 뒤를 새로 준다
            eid = next_event_id([{"event_id": u} for u in used])
        used.add(eid)
        out.append({
            "event_id": eid,
            "start_seg": a, "end_seg": b,
            "start_sec": float(by_idx[a]["start"]),
            # 마지막 구간의 `end`가 영상 길이를 넘는 인덱스가 있다(m1 반올림 산물).
            # 그대로 내보내면 V2(영상 길이 안)에서 거부되고, 그것은 사람 입력 문제가 아니다.
            "end_sec": (min(float(by_idx[b]["end"]), float(duration_sec))
                        if duration_sec else float(by_idx[b]["end"])),
            "description": (e.get("description") or "").strip(),
            "unclear": 1 if e.get("unclear") else 0,
        })
    out.sort(key=lambda e: (e["start_seg"], e["end_seg"]))
    draft["events"] = out
    draft["status"] = "DRAFT"
    return draft


def save_draft(video_id: str, draft: dict, segs: list, root=INVENTORY,
               duration_sec: float | None = None) -> dict:
    draft = normalize({**draft, "video_id": video_id}, segs, duration_sec)
    common.atomic_write_json(draft_path(video_id, root), draft)
    return draft


def _sec(x: float) -> str:
    """초를 문자열로. **`%g`를 쓰지 않는다** — 유효숫자 6자리라 1637.999가 1638이 되고,
    그 0.001 때문에 V2(영상 길이 안)가 거부한다."""
    s = f"{float(x):.3f}".rstrip("0").rstrip(".")
    return s or "0"


def to_csv_rows(draft: dict) -> list:
    """사전등록 CSV 양식 그대로. 설명이 빈 사건은 내보내지 않는다(V3에서 거부된다)."""
    rows = [["start_sec", "end_sec", "event", "unclear"]]
    for e in draft["events"]:
        if not e["description"]:
            raise UIError(f"{e['event_id']}: 설명이 비어 있다 — 내보내기 전에 채워라")
        rows.append([_sec(e["start_sec"]), _sec(e["end_sec"]),
                     e["description"], "1" if e["unclear"] else ""])
    return rows


def export_csv(video_id: str, root=INVENTORY) -> Path:
    """`{video_id}.csv`로 내보낸다 — 그 뒤는 기존 validate·freeze 경로다."""
    draft = load_draft(video_id, root)
    if not draft["events"]:
        raise UIError(f"{video_id}: 사건이 0건이다")
    rows = to_csv_rows(draft)
    out = Path(root) / f"{video_id}.csv"
    lines = [",".join(f'"{c}"' if ("," in c or '"' in c) else c for c in r) for r in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def create_app(cfg: dict, videos=None, root=INVENTORY) -> FastAPI:
    allowed = list(videos if videos is not None else panel_videos())
    app = FastAPI()

    def check(video_id: str) -> str:
        if video_id not in allowed:
            raise HTTPException(403, f"{video_id}는 이번 라벨링 대상이 아니다 — "
                                     f"동결 패널만 열 수 있다")
        return video_id

    def doc_of(video_id: str) -> dict:
        """**allowlist를 지나는 유일한 경로.** caption·subtitle은 여기서 이미 없다."""
        wdir = common.work_dir(cfg, video_id)
        return label_guard.load_segments_for_labeling(wdir / "segments.json")

    def segments(video_id: str) -> list:
        return doc_of(video_id)["segments"]

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(HTML.read_text(encoding="utf-8"))

    @app.get("/api/videos")
    def videos_list() -> dict:
        out = []
        for v in allowed:
            d = load_draft(v, root)
            out.append({"video_id": v, "n_events": len(d.get("events", [])),
                        "status": d.get("status", "DRAFT")})
        return {"videos": out}

    @app.get("/api/segments/{video_id}")
    def segs(video_id: str) -> dict:
        check(video_id)
        s = segments(video_id)
        return {"video_id": video_id, "n_segments": len(s),
                "segments": [{"idx": x["idx"], "start": x["start"], "end": x["end"]}
                             for x in s]}

    @app.get("/api/frame/{video_id}/{idx}")
    def frame(video_id: str, idx: int):
        check(video_id)
        s = {x["idx"]: x for x in segments(video_id)}
        if idx not in s:
            raise HTTPException(404, "구간 없음")
        p = common.work_dir(cfg, video_id) / s[idx]["rep_frame"]
        if not p.exists():
            raise HTTPException(404, "프레임 파일 없음")
        return FileResponse(p, media_type="image/jpeg")

    @app.get("/api/video/{video_id}")
    def video(video_id: str):
        """경계 확인용 무음 재생. 프레임과 같은 픽셀이고 오디오는 UI가 끈다."""
        check(video_id)
        p = Path(cfg["paths"]["data"]) / "videos" / f"{video_id}.mp4"
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise HTTPException(404, "영상 파일 없음")
        return FileResponse(p, media_type="video/mp4")

    @app.get("/api/draft/{video_id}")
    def get_draft(video_id: str) -> dict:
        check(video_id)
        return load_draft(video_id, root)

    @app.put("/api/draft/{video_id}")
    def put_draft(video_id: str, draft: dict) -> dict:
        check(video_id)
        try:
            d = doc_of(video_id)
            return save_draft(video_id, draft, d["segments"], root,
                              d.get("duration_sec"))
        except UIError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/export/{video_id}")
    def post_export(video_id: str) -> dict:
        check(video_id)
        try:
            p = export_csv(video_id, root)
        except UIError as e:
            raise HTTPException(400, str(e))
        return {"csv": _rel(p),
                "next": [f"python scripts/event_inventory_kit.py validate --video-id {video_id}",
                         f"python scripts/event_inventory_kit.py freeze   --video-id {video_id}"]}

    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--video-id")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--port", type=int, default=8010)
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    if a.export:
        if not a.video_id:
            ap.error("--export에는 --video-id가 필요하다")
        p = export_csv(a.video_id)
        print(f"내보냄: {p}")
        print(f"다음: python scripts/event_inventory_kit.py validate --video-id {a.video_id}")
        return 0
    if not a.serve:
        ap.error("--serve 또는 --export")

    import uvicorn
    print(f"대상 {len(panel_videos())}편 · http://127.0.0.1:{a.port}")
    print("보이는 것: 프레임·시각·무음 영상뿐. 캡션·자막·검색 결과는 도구가 막는다")
    uvicorn.run(create_app(cfg), host="127.0.0.1", port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
