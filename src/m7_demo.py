"""M7 데모: Gradio. 백엔드는 m5_search.search를 그대로 import(재구현 금지). [4-7]"""
import argparse
from pathlib import Path
import common
from m5_search import VideoIndex, search


def format_output(ranked, segments, k: int = 3) -> dict:
    return {"jump_to": int(ranked[0].start),
            "subtitle": segments[ranked[0].idx]["subtitle"],
            "windows": [[int(r.start), int(r.end)] for r in ranked[:k]]}


def main():
    import gradio as gr
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
        return (str(mp4), out["jump_to"]), out["subtitle"], "\n".join(lines)

    with gr.Blocks(title="영상 장면 검색") as app:
        q = gr.Textbox(label="질의")
        player = gr.Video(str(mp4), label="영상")
        sub = gr.Textbox(label="자막", interactive=False)
        tops = gr.Textbox(label="Top-3 구간", interactive=False)
        q.submit(run, q, [player, sub, tops])
    app.launch()


if __name__ == "__main__":
    main()
