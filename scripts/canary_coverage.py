"""CANARY 입력 커버리지 — FULL 입력의 **종류**를 CANARY가 다 밟았는지 검사한다.

2026-08-21 사고 3건은 전부 "몇 편 돌렸나"로는 잡히지 않는 종류였다.

```
-_mgcIUbbX4    하이픈으로 시작하는 video_id → argparse가 옵션으로 읽었다
AV1 2편        서버 cv2 5.0.0에 AV1 소프트웨어 디코더가 없다 (m2에서 죽었다)
ffmpeg 4.4.2   `-fps_mode`가 5.1부터라 변환 스크립트가 죽었다
```

앞의 둘은 CANARY가 **신규 avc1 1편**만 돌려서 FULL 31편째에 드러났다. 그래서 판정
기준을 "CANARY N편 PASS"에서 **"FULL에 존재하는 입력 클래스를 CANARY가 전부 밟았는가"**로
바꾼다.

축은 다섯이고, **전부 corpus에서 실제로 관측되는 속성**이다.

```
codec       native_h264 · transcoded_h264 · … (실제 관측된 것만)
provenance  new · legacy (기확보·출처 해시 없음)
id_shape    plain · cli_sensitive (하이픈 시작)
duration    shortest · longest (corpus 상대 극단 1편씩)
audio       known · unresolved (플랫폼 audio-language proxy 판정)
```

**성능·캡션·자막·검색 결과는 입력으로 쓰지 않는다.** 대표 표본을 모델 산출물로 고르면
CANARY 선정 자체가 오염된다. 정렬 키는 구간 수와 video_id뿐이다.

**launcher 연결 (2026-08-24).** `gate_for_full`이 FULL 승인 경로의 fail-closed 게이트다.
적용 범위는 **계획이 `canary_coverage`를 선언한 경우로 한정**한다.

```
선언 없음   요구하지 않는다. 대신 required=False를 남긴다 — "검사했다"로 읽히지 않게
선언 있음   sample·CANARY 결과가 없거나 video_ids가 없으면 막는다(조용한 통과 없음)
CANARY 식별  예측하지 않고 **CANARY가 실제로 돌린 video_ids**를 결과 JSON에서 읽는다
읽는 키      video_ids 하나뿐. 같은 파일에 캡션·점수가 있어도 보지 않는다
```

**완료된 P2 계획(`docs/planning/p2_index_plan.json`)에는 선언을 넣지 않는다.** REPORT가
`plan_hash` 불일치를 거부하므로(exp_launcher L432) 계획 파일을 고치면 이미 끝난
`p2idx_0821d`의 정식 열람 경로가 막힌다. 소급 적용하지 않는다는 요구와도 같은 방향이다.

재현:
  python scripts/canary_coverage.py --canary OBxKlA5rxjQ,baekmansonghee_jirisan
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
VIDEOS = ROOT / "data" / "videos"
TRANSCODED_SUFFIX = ".av1source.mp4"
AXES = ("codec", "provenance", "id_shape", "duration", "audio")
AUDIO_KNOWN = "audio_track_ko"
# 사고가 실제로 난 조합만 여기에 승격한다. **기본값은 비어 있다** — 축의 Cartesian
# product를 요구하면 CANARY가 corpus만큼 커진다. 기본 검사는 축별 marginal이고 그
# 한계는 결과 JSON의 coverage_limit에 적힌다.
REQUIRED_COMBINATIONS = ()


class CoverageError(RuntimeError):
    pass


def load_corpus(path=SAMPLE) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))["selected"]


def probe_codec_class(vid: str, videos_dir=VIDEOS) -> str:
    """실파일에서 코덱을 읽는다. 변환본은 원본 보존 파일의 존재로 구분한다.

    `<id>.av1source.mp4`가 있으면 그 영상은 AV1을 h264로 옮긴 것이다 — 같은 h264라도
    디코드 경로가 달랐으므로 CANARY에서 따로 밟아야 한다.
    """
    f = Path(videos_dir) / f"{vid}.mp4"
    if not f.is_file():
        raise CoverageError(f"{vid}: 영상 파일이 없어 codec을 관측할 수 없다 ({f})")
    if (Path(videos_dir) / f"{vid}{TRANSCODED_SUFFIX}").is_file():
        return "transcoded_h264"
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name", "-of", "csv=p=0", str(f)],
        capture_output=True, encoding="utf-8", errors="replace")
    name = (r.stdout or "").strip()
    if not name:
        raise CoverageError(f"{vid}: codec을 읽지 못했다")
    return f"native_{name}"


def inventory(corpus: list, codec_of: dict) -> dict:
    """영상 → 클래스 집합. **corpus에 있는 속성만 쓴다.**"""
    if not corpus:
        raise CoverageError("corpus가 비었다")
    n_seg = {r["source_id"]: r["n_segments"] for r in corpus}
    shortest = min(sorted(n_seg), key=lambda v: (n_seg[v], v))
    longest = max(sorted(n_seg), key=lambda v: (n_seg[v], v))
    inv = {}
    for r in corpus:
        vid = r["source_id"]
        codec = codec_of.get(vid)
        if not codec:
            raise CoverageError(f"{vid}: codec 관측값이 없다 — 추측해 채우지 않는다")
        classes = {
            f"codec:{codec}",
            "provenance:legacy" if r.get("pre_indexed") else "provenance:new",
            "id_shape:cli_sensitive" if vid.startswith("-") else "id_shape:plain",
            "audio:known" if r.get("speech_status") == AUDIO_KNOWN
            else "audio:unresolved",
        }
        if vid == shortest:
            classes.add("duration:shortest")
        if vid == longest:
            classes.add("duration:longest")
        inv[vid] = classes
    return inv


def coverage(full_ids: list, canary_ids: list, inv: dict,
             required_combinations=REQUIRED_COMBINATIONS) -> dict:
    """FULL 입력의 클래스 집합과 CANARY가 밟은 집합을 비교한다.

    기본 검사는 **축별 marginal coverage**다 — 모든 클래스가 어딘가에서 한 번씩
    밟히면 통과한다. 클래스 조합(interaction)까지 보장하지 않는다. 예를 들어
    `legacy × transcoded_h264 × cli_sensitive`가 존재해도 각 클래스가 서로 다른
    영상에서 커버되면 marginal은 통과한다.

    `required_combinations`에 넣은 조합은 **한 영상이 동시에** 만족해야 한다. 사고가
    실제로 난 조합만 승격한다 — 전 조합을 요구하면 CANARY가 FULL만큼 커진다.
    """
    unknown = [v for v in list(full_ids) + list(canary_ids) if v not in inv]
    if unknown:
        raise CoverageError(f"inventory에 없는 영상: {sorted(set(unknown))}")
    outside = [v for v in canary_ids if v not in set(full_ids)]
    if outside:
        raise CoverageError(f"CANARY 영상이 FULL 입력에 없다: {sorted(outside)} — "
                            f"밟았다고 셀 수 없다")
    full_classes = {c for v in full_ids for c in inv[v]}
    canary_classes = {c for v in canary_ids for c in inv[v]}
    covered = sorted(full_classes & canary_classes)
    missing = sorted(full_classes - canary_classes)

    missing_combos = []
    for combo in required_combinations or ():
        want = set(combo)
        if not any(want <= inv[v] for v in full_ids):
            raise CoverageError(
                f"required_combination {sorted(want)}: FULL 입력에 그 조합이 없다 "
                f"— 영원히 통과할 수 없는 요구다")
        if not any(want <= inv[v] for v in canary_ids):
            missing_combos.append(sorted(want))

    return {"axes": list(AXES),
            "coverage_kind": "marginal_per_axis",
            "coverage_limit": ("축별 marginal이다 — 클래스 조합까지 보장하지 않는다. "
                               "사고가 난 조합만 required_combinations로 승격한다"),
            "required_combinations": [sorted(c) for c in
                                      (required_combinations or ())],
            "missing_combinations": missing_combos,
            "n_full": len(set(full_ids)), "n_canary": len(set(canary_ids)),
            "full_classes": sorted(full_classes),
            "canary_classes": sorted(canary_classes),
            "covered": covered, "missing": missing,
            "ok": not missing and not missing_combos,
            "note": ("클래스는 corpus에서 관측된 것만이다. 성능·캡션·검색 결과는 "
                     "입력으로 쓰지 않는다")}


def require_coverage(full_ids: list, canary_ids: list, inv: dict,
                     required_combinations=REQUIRED_COMBINATIONS) -> dict:
    """fail-closed 진입점. **아직 launcher에 연결하지 않았다.**"""
    r = coverage(full_ids, canary_ids, inv, required_combinations)
    if not r["ok"]:
        raise CoverageError(
            f"CANARY 미포함 입력 클래스 {len(r['missing'])}종: {r['missing']} · "
            f"미포함 조합 {r['missing_combinations']} — 이 상태로 FULL에 들어가면 "
            f"그 종류는 FULL에서 처음 밟는다")
    return r


COVERAGE_KEY = "canary_coverage"
CANARY_ID_KEY = "video_ids"


def _canary_ids(path: Path) -> list:
    """CANARY 결과에서 **video_ids만** 읽는다. 다른 키는 열지 않는다."""
    p = Path(path)
    if not p.is_file():
        raise CoverageError(
            f"CANARY 결과가 없다: {p} — 무엇을 밟았는지 관측할 수 없다. "
            f"CANARY를 먼저 돌려라")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise CoverageError(f"CANARY 결과를 읽지 못했다: {p} ({e})")
    ids = doc.get(CANARY_ID_KEY)
    if not isinstance(ids, list) or not ids:
        raise CoverageError(
            f"CANARY 결과에 {CANARY_ID_KEY}가 없거나 비었다: {p} — 밟은 영상을 "
            f"추측해 채우지 않는다")
    return [str(v) for v in ids]


def gate_for_full(plan: dict, run_dir, root, codec_of: dict = None) -> dict:
    """FULL 승인 경로의 게이트. **선언한 계획에만** 적용한다.

    선언이 없으면 요구하지 않되 `required=False`를 남긴다 — 검사하지 않은 것이
    통과로 읽히면 이 게이트를 만든 이유가 없어진다.
    """
    decl = plan.get(COVERAGE_KEY)
    if not decl:
        return {"required": False, "coverage_kind": None,
                "reason": f"계획에 {COVERAGE_KEY} 선언이 없다 — 요구하지 않았다. "
                          f"통과로 읽지 마라"}
    if run_dir is None:
        raise CoverageError(
            f"{COVERAGE_KEY}를 선언했는데 run_dir이 없다 — CANARY가 무엇을 밟았는지 "
            f"확인할 수 없다. 조용히 넘기지 않는다")
    sample = Path(decl["sample"])
    if not sample.is_absolute():
        sample = Path(root) / sample
    if not sample.is_file():
        raise CoverageError(f"선정표본이 없다: {sample}")
    result = Path(run_dir) / decl.get("canary_result",
                                      "p2_index_batch_run_canary.json")
    canary_ids = _canary_ids(result)

    corpus = load_corpus(sample)
    full_ids = [r["source_id"] for r in corpus]
    if codec_of is None:
        videos = Path(decl.get("videos_dir") or VIDEOS)
        if not videos.is_absolute():
            videos = Path(root) / videos
        codec_of = {v: probe_codec_class(v, videos_dir=videos)
                    for v in full_ids}
    inv = inventory(corpus, codec_of)
    combos = tuple(tuple(c) for c in (decl.get("required_combinations") or ()))
    r = require_coverage(full_ids, canary_ids, inv, combos)
    return dict(r, required=True, read_keys=[CANARY_ID_KEY],
                canary_result=str(result), sample=str(sample))


def select_representatives(inv: dict) -> list:
    """모든 클래스를 덮는 최소 표본을 결정적으로 고른다.

    희귀한 클래스부터 채우고, 동률이면 **구간이 적은 영상**을 고른다(CANARY는 배관
    확인이라 짧을수록 좋다). 모델 산출물은 정렬에 들어가지 않는다.
    """
    remaining = {c for cs in inv.values() for c in cs}
    n_class = {v: len(cs) for v, cs in inv.items()}
    picked = []
    while remaining:
        # 가장 희귀한 클래스를 먼저 채운다 — 그 클래스를 가진 영상이 적기 때문이다
        rarity = {c: sum(1 for cs in inv.values() if c in cs) for c in remaining}
        target = min(sorted(remaining), key=lambda c: (rarity[c], c))
        cands = sorted(v for v, cs in inv.items() if target in cs)
        best = max(cands, key=lambda v: (len(inv[v] & remaining), -n_class[v],
                                         [-ord(ch) for ch in v]))
        picked.append(best)
        remaining -= inv[best]
    return sorted(set(picked))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary", required=True, help="쉼표로 구분한 video_id")
    ap.add_argument("--out")
    ap.add_argument("--suggest", action="store_true",
                    help="모든 클래스를 덮는 최소 표본을 제안한다")
    a = ap.parse_args()
    corpus = load_corpus()
    codecs = {r["source_id"]: probe_codec_class(r["source_id"]) for r in corpus}
    inv = inventory(corpus, codecs)
    full_ids = [r["source_id"] for r in corpus]
    r = coverage(full_ids, [v for v in a.canary.split(",") if v], inv)
    if a.suggest:
        r["suggested_canary"] = select_representatives(inv)
    if a.out:
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    print(f"full {r['n_full']} / canary {r['n_canary']} / "
          f"classes {len(r['full_classes'])} / missing {len(r['missing'])} / "
          f"ok {r['ok']}")
    for c in r["missing"]:
        print(f"  missing {c}")
    if a.suggest:
        print("  suggested: " + ",".join(r["suggested_canary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
