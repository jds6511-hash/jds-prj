"""M8 AAR 리포트 생성: [seg#N] 인용 강제 + map-reduce. [DESIGN_SPEC 4-8, v2 13장]"""
import argparse, re
import common
from llm import make_llm

_SYSTEM = """당신은 영상 사후검토(AAR) 리포트 작성자입니다.
아래는 5초 단위 세그먼트별 자막(subtitle)과 장면 캡션(caption)입니다.
규칙:
1. 모든 문장은 반드시 하나 이상의 [seg#N] 인용을 포함할 것.
2. 세그먼트에 없는 내용은 절대 추측해 쓰지 말 것. 근거가 없으면 문장 자체를 생략할 것.
3. 시간 순서대로 사건을 서술할 것.
4. 인용한 seg#의 내용과 문장이 실제로 일치해야 함 (사후 검증됨).
5. 출력에는 '-'로 시작하는 사건 서술 문장 외에 어떤 머리말·설명·맺음말도 쓰지 말 것.

출력 형식 (한 줄에 한 문장). 아래는 형식 자리표시자일 뿐이며 내용·번호를 절대 복사하지 말 것:
- (실제 세그먼트에 근거한 사건 서술) [seg#9999]
- (사건 서술 — 인용이 여러 개인 경우) [seg#9998, seg#9999]
"""
# 예시 번호를 의도적으로 실영상 범위 밖(9999)으로 둔다 — 소형 모델이 예시를 복사하면
# save_report의 인용 범위 assert가 즉시 잡아낸다(3B 실측에서 유효 번호 예시가 전 영상에
# 복사돼 무증상 통과한 사고의 방어) [리뷰 2026-07-11 Major]


def _fmt_seg(s) -> str:
    def hms(t):
        t = int(t); return f"{t//60:02d}:{t%60:02d}"
    caption = s["caption"]
    if common.is_corrupted_caption(caption):    # 오염된 캡션을 근거로 인용하는 것 방지 [8-3(c) 대응]
        caption = "(캡션 품질 문제로 제외됨)"
    return (f'[seg#{s["idx"]}] {hms(s["start"])}-{hms(s["end"])} '
            f'subtitle: "{s["subtitle"]}" caption: "{caption}"')


def build_map_prompt(chunk: list[dict]) -> str:
    return _SYSTEM + "\n입력:\n" + "\n".join(_fmt_seg(s) for s in chunk)


def build_reduce_prompt(partials: list[str]) -> str:
    joined = "\n\n---\n\n".join(partials)
    return (
        "아래는 같은 영상의 구간별 부분 리포트들입니다. 하나의 최종 리포트로 통합하세요.\n"
        "규칙:\n"
        "1. 중복 사건은 하나로 합칠 것.\n"
        "2. 시간 순서([seg#N] 번호 순)로 재정렬할 것.\n"
        "3. 부분 리포트에 없는 새로운 사실을 절대 추가하지 말 것.\n"
        "4. 각 문장의 [seg#N] 인용은 부분 리포트의 인용을 그대로 유지할 것.\n"
        "출력 형식은 동일: '- 문장 [seg#N]'. 그 외 텍스트 금지.\n\n부분 리포트:\n" + joined)


def parse_citations(text: str) -> list[dict]:
    """줄 단위 파싱. [seg#N, seg#M] → cites 리스트, 인용 없으면 cites=[]. [4-8]

    주의: DESIGN_SPEC 4-8의 반복그룹 정규식(r"\\[seg#(\\d+)(?:,\\s*seg#(\\d+))*\\]")은
    Python re의 반복 그룹이 마지막 매치만 캡처하는 특성 때문에 3개 이상 인용에서
    중간 캡처가 유실된다. 의도적으로 느슨한 findall(r"seg#(\\d+)")를 쓴다.
    스펙 정규식으로 되돌리지 말 것. [m8m9-prompt-critique B-4]
    """
    sents = []
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        # 공백·대소문자 변형([seg# 3], [Seg#3]) 유실 방지 [리뷰 2026-07-11 Minor]
        cites = [int(m) for m in re.findall(r"seg\s*#\s*(\d+)", line, re.IGNORECASE)]
        sents.append({"sent_id": len(sents), "text": line, "cites": sorted(set(cites))})
    return sents


def generate_report(segments: list[dict], llm, chunk_size: int = 60,
                    overlap: int = 5) -> dict:
    assert overlap < chunk_size, \
        f"map_chunk_overlap({overlap}) >= map_chunk_size({chunk_size})"  # [m8m9-prompt-critique B-3]
    if len(segments) <= chunk_size:                    # 단일 호출 [4-8]
        raw = llm(build_map_prompt(segments))
        return {"sentences": parse_citations(raw), "raw_output": raw,
                "map_raw_outputs": []}
    # Map: overlap 세그먼트를 두고 청크 분할 [13-2]
    partials, start = [], 0
    while start < len(segments):
        chunk = segments[start:start + chunk_size]
        partials.append(llm(build_map_prompt(chunk)))
        if start + chunk_size >= len(segments):
            break
        start += chunk_size - overlap
    # Reduce + 안전장치: reduce 인용 ⊆ map 인용 검사 [13-2]
    map_cites = {c for p in partials for s in parse_citations(p) for c in s["cites"]}
    raw = llm(build_reduce_prompt(partials))
    sents = parse_citations(raw)
    for s in sents:
        dropped = [c for c in s["cites"] if c not in map_cites]
        if dropped:
            print(f"[warn] reduce 인용 유실/오귀속 필터: sent {s['sent_id']} {dropped}")
            s["cites"] = [c for c in s["cites"] if c in map_cites]
    return {"sentences": sents, "raw_output": raw, "map_raw_outputs": partials}


def save_report(out, video_id: str, cfg: dict, rep: dict, n: int) -> None:
    """report.json을 먼저 저장한 뒤 인용 범위를 검증한다 (raw_output은 항상 보존). [DESIGN_SPEC 3-5]

    LLM이 out-of-range 인용을 환각해 assert가 실패해도 report.json은 이미
    기록된 상태로 남는다 (raw_output 포함). [m8m9-final-review Finding 1]
    """
    common.atomic_write_json(out, {"video_id": video_id,
                                   "model": cfg["report_model"],
                                   "map_chunk_size": cfg["map_chunk_size"], **rep})
    for s in rep["sentences"]:                          # 검증 포인트 [4-8]
        assert all(0 <= c < n for c in s["cites"]), \
            f"인용 범위 위반 (report.json은 저장됨): {s}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    out = wdir / "report.json"
    if out.exists() and not args.force:
        print("이미 존재 (--force로 재생성)"); return

    llm = make_llm(cfg["report_model"], load_4bit=cfg.get("llm_4bit", False))
    rep = generate_report(doc["segments"], llm,
                          cfg["map_chunk_size"], cfg["map_chunk_overlap"])
    save_report(out, args.video_id, cfg, rep, doc["n_segments"])
    print(f"M8 완료: 문장 {len(rep['sentences'])}개 → {out}")


if __name__ == "__main__":
    main()
