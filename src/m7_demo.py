"""M7 데모: Gradio. 백엔드는 m5_search.search를 그대로 import(재구현 금지). [4-7]"""
import argparse
from pathlib import Path
import common
from m5_search import VideoIndex, search


def format_output(ranked, segments, k: int = 3) -> dict:
    return {"jump_to": int(ranked[0].start),
            "subtitle": segments[ranked[0].idx]["subtitle"],
            "windows": [[int(r.start), int(r.end)] for r in ranked[:k]]}


_SEEK_JS = (
    "(t) => { const v = document.querySelector('#player video'); "
    "if (v && t !== null) { v.currentTime = t; v.play(); } }"
)


def build_app(run_fn, mp4_path):
    """gr.Blocks 구성. run_fn(query) -> (jump_to:int, subtitle:str, windows_text:str).
    영상 소스는 질의마다 바뀌지 않으므로 고정 str로 두고, jump_to만 hidden
    gr.Number로 흘려보내 JS로 <video>.currentTime을 갱신한다
    (gr.Video.postprocess는 str|Path|None만 받고 (경로, 시작초) 튜플은 지원하지 않음)."""
    import gradio as gr
    with gr.Blocks(title="영상 장면 검색") as app:
        q = gr.Textbox(label="질의")
        player = gr.Video(str(mp4_path), label="영상", elem_id="player")
        sub = gr.Textbox(label="자막", interactive=False)
        tops = gr.Textbox(label="Top-3 구간", interactive=False)
        jump_to = gr.Number(visible=False)
        q.submit(run_fn, q, [jump_to, sub, tops]).then(
            None, jump_to, None, js=_SEEK_JS)
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--alpha", type=float, required=True,
                    help="eval에서 고정한 α (results/alpha_search_dev.json)")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    video = VideoIndex.load(cfg, args.video_id)
    mp4 = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"

    def run(query):
        ranked = search(query, video, args.alpha, cfg)
        out = format_output(ranked, video.segments)
        lines = [f"{i+1}. {w[0]}초~{w[1]}초" for i, w in enumerate(out["windows"])]
        return out["jump_to"], out["subtitle"], "\n".join(lines)

    build_app(run, mp4).launch()


if __name__ == "__main__":
    main()
