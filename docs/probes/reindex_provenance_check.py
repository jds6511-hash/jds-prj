"""[재캡셔닝 provenance 검증 — 무엇이 바뀌었고 무엇이 안 바뀌었나]

**왜.** 8회차에서 바꾸기로 한 것은 **캡션 모델뿐**이다. 자막(STT 출력)은 그대로여야
한다. 그런데 2026-08-17 배치 1차 시도에 `--force`가 잘못 들어가 있었다 —
그대로 돌았으면 Whisper가 재실행돼 **자막까지 바뀌었을 것**이고, 그러면 캡션 모델
효과와 STT 재생성 효과가 섞여 8회차 결과를 해석할 수 없게 된다.

플래그는 고쳤지만 **고쳤다는 말로 끝내지 않는다.** 재캡셔닝 전 백업과 대조해
자막이 실제로 한 글자도 안 바뀌었음을 확인한다.

동시에 개방 게이트 I1~I4(`docs/8회차_개방게이트_2026-08-16.md`)를 기계적으로 채운다.
사람이 눈으로 세지 않는다 — 세다가 틀리면 게이트가 무의미하다.

재현:
  python docs/probes/reindex_provenance_check.py \
      --config config_server.yaml --backup /path/to/backup_pre_8th_*
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                             # noqa: E402

EXPECT_DIM = 1024


def segs_of(doc):
    return doc["segments"] if isinstance(doc, dict) else doc


def field_hash(segments, field):
    """해당 필드만 이어붙인 SHA256. 순서를 포함해 본다 — 순서가 바뀌어도 사고다."""
    h = hashlib.sha256()
    for s in segments:
        h.update((s.get(field) or "").encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--backup", required=True,
                    help="재캡셔닝 전 segments.json 사본 디렉터리 (<video>.segments.json)")
    ap.add_argument("--out", default="reindex_provenance.json")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    bk = Path(args.backup)

    vids = sorted(p.name[: -len(".segments.json")]
                  for p in bk.glob("*.segments.json"))
    assert vids, f"백업이 비었다: {bk}"

    rows, i1, i2, i3, i4, sub_changed = {}, 0, 0, 0, 0, 0
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        cur = segs_of(json.loads((wdir / "segments.json").read_text(encoding="utf-8")))
        old = segs_of(json.loads((bk / f"{v}.segments.json").read_text(encoding="utf-8")))

        sub_old, sub_new = field_hash(old, "subtitle"), field_hash(cur, "subtitle")
        cap_old, cap_new = field_hash(old, "caption"), field_hash(cur, "caption")

        caps = [(s.get("caption") or "") for s in cur]
        n_corrupt = sum(1 for c in caps if common.is_corrupted_caption(c))
        all_blank = bool(caps) and not any(c.strip() for c in caps)

        meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
        doc = common.load_segments(wdir / "segments.json",
                                   require=["subtitle", "caption"],
                                   seg_len=cfg["seg_len_sec"])
        hash_ok = meta.get("text_hash") == common.index_text_hash(doc)

        shapes, shape_ok = {}, True
        for name in ("emb_sub", "emb_cap"):
            e = np.load(wdir / f"{name}.npy")
            shapes[name] = list(e.shape)
            shape_ok &= e.shape == (len(cur), EXPECT_DIM)

        rows[v] = {
            "n_segments": len(cur),
            "subtitle_unchanged": sub_old == sub_new,
            "caption_changed": cap_old != cap_new,
            "n_corrupted": n_corrupt,
            "all_blank_captions": all_blank,
            "text_hash_ok": hash_ok,
            "emb_shapes": shapes, "emb_shape_ok": shape_ok,
            "caption_len_mean_before": round(np.mean([len(s.get("caption") or "")
                                                     for s in old]), 1),
            "caption_len_mean_after": round(np.mean([len(c) for c in caps]), 1),
        }
        i1 += n_corrupt
        i2 += hash_ok
        i3 += shape_ok
        i4 += all_blank
        sub_changed += (sub_old != sub_new)

    n = len(vids)
    gates = {
        "I1_corrupted_total": {"value": i1, "pass": i1 == 0,
                               "criterion": "오염 캡션 잔존 0건"},
        "I2_text_hash": {"value": f"{i2}/{n}", "pass": i2 == n,
                         "criterion": "text_hash 전편 일치"},
        "I3_emb_shape": {"value": f"{i3}/{n}", "pass": i3 == n,
                         "criterion": f"(n_segments, {EXPECT_DIM}) x2"},
        "I4_all_blank_videos": {"value": i4, "pass": i4 == 0,
                                "criterion": "캡션 전량 공백 영상 0편"},
        # 게이트 문서에는 없지만 이번 배치의 사고 이력 때문에 반드시 본다.
        # 자막이 바뀌었다면 캡션 모델 효과와 STT 재생성 효과가 섞인 것이고,
        # 그 상태의 8회차는 해석이 불가능하다.
        "P0_subtitle_unchanged": {"value": f"{n - sub_changed}/{n}",
                                  "pass": sub_changed == 0,
                                  "criterion": "자막 해시 전편 불변 (캡션만 바꾼다)"},
    }
    all_pass = all(g["pass"] for g in gates.values())

    out = {"note": __doc__.strip().splitlines()[0], "backup": str(bk),
           "n_videos": n, "gates": gates, "all_pass": all_pass, "per_video": rows}
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)
    (rdir / args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    for k, g in gates.items():
        print(f"{k:<24} {str(g['value']):>10}   {'PASS' if g['pass'] else 'FAIL'}   {g['criterion']}")
    print(f"\n{'영상':<34}{'자막불변':>9}{'캡션변경':>9}{'오염':>5}{'해시':>5}{'길이 전→후':>16}")
    for v, r in rows.items():
        print(f"{v[:32]:<34}{str(r['subtitle_unchanged']):>9}{str(r['caption_changed']):>9}"
              f"{r['n_corrupted']:>5}{str(r['text_hash_ok']):>5}"
              f"{r['caption_len_mean_before']:>8.1f} → {r['caption_len_mean_after']:<6.1f}")
    print(f"\n전체: {'PASS' if all_pass else 'FAIL'}   저장: {rdir / args.out}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
