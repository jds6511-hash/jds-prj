"""[같은 프레임을 두 캡션 모델이 어떻게 서술하는가 — 사후 쌍대 기술 분석, 채택 근거 아님]

**목적은 우열 판정이 아니다.** 동일 프레임에 대해 `Qwen2.5-VL-3B`와 `Qwen3-VL-4B`가
캡션에 **무엇을 얼마나 남겼는지**를 기술한다. 새 가설검정도, p-value도 만들지 않는다.

```
PRIMARY      AI Hub 194편·2,328구간   3B/P0 ↔ 4B/P0      (prompt 고정)
SENSITIVITY  같은 표본               3B/P1 ↔ 4B/P1      prompt 민감도
CROSS-CHECK  dev 3편·655구간          3B/P0 ↔ 4B/P0
ILLUSTRATION pland 395구간            동시점 생성 2 arm   사례용
```

**접근 금지**: M8 C2 판정 패널 8편(라벨링 blind 유지) · 공식 test · P2/P3 자원.

한계는 결과에도 박는다 — 재사용 표본이고, 사후 기술 분석이며, 모델 일반 특성을
확정하지 않는다. 자동 탐지되는 "화면 글자 언급"은 **overlay GT가 아니다**.

재현: `python docs/probes/caption_style_paired.py --out docs/probes/_scratch/caption_style_paired.json`
"""
import argparse
import json
import re
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "docs" / "probes" / "_scratch"
AIHUB = SCRATCH / "aihub_2x2_captions" / "full_2026-08-17"
SWEEP = SCRATCH / "caption_sweep_captions"
CASESTUDY = ROOT / "runs" / "casestudy_caption_retrieval" / "cs_20260825"

# 두 모델이 공유한 생성 상한. 3B는 여기 자주 닿았고 4B는 거의 닿지 않았다(케이스 스터디
# 실측 57/395 vs 2/395). 길이 분포가 **우측에서 잘린** 상태라는 뜻이므로 평균만 보면 안 된다.
SHARED_MAX_NEW_TOKENS = 128

# ---- 텍스트 특징 휴리스틱 -------------------------------------------------
# POS 분석기가 이 환경에 없다(kiwipiepy·konlpy·mecab 전부 미설치). 새 무거운 의존성을
# 임의로 설치하지 않는다. 그래서 아래는 **저신뢰 표층 휴리스틱**이고, 지표처럼 포장하지
# 않는다 — 방향을 보는 용도다.
_WORD = re.compile(r"[가-힣]+|[A-Za-z][A-Za-z']*|\d+")
_SENT_END = re.compile(r"(다|요|음|임)[.!?]?\s*$")
_PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|이나|과|와|을|를|이|가|은|는|의|에|도|만|랑)$")

# 화면 글자를 언급하거나 전사한 것처럼 보이는 **후보**. overlay(편집 자막)와 in-scene
# text(간판·라벨·현수막)를 자동으로 가르지 못한다 — 그래서 이름이 candidate다.
_TEXT_REF = re.compile(
    r"[\"'“”‘’]|라고 (?:적|쓰|씌)|적혀|쓰여|문구|글씨|글자|자막|간판|표지판|현수막|"
    r"라벨|로고|간판에|메뉴판|표기|텍스트")
_LATIN_RUN = re.compile(r"[A-Z]{3,}")          # COSTCO 같은 대문자 문자열
_CJK = re.compile(r"[一-鿿]")          # 한자
_KANA = re.compile(r"[぀-ヿ]")         # 가나
_HANGUL = re.compile(r"[가-힣]")

# 행동 표현 — 이 캡션 레지스터에서 비교적 잘 잡히는 종결·연결 어미
_ACTION = re.compile(r"(하고 있|되고 있|있는|하는|하며|으며|고 있다|린다|한다|진다)")
# 장소·맥락 — 처소격 조사가 붙은 어절
_SCENE = re.compile(r"[가-힣]+(?:에서|에는|안에|앞에|위에|옆에|뒤에|주변|배경)")
# 인물
_PERSON = re.compile(r"(남성|여성|남자|여자|사람|아이|어린이|노인|직원|인물|손님|관광객)")


def words(text: str) -> list:
    return _WORD.findall(text or "")


def content_tokens(text: str) -> set:
    """조사를 거칠게 떼어낸 내용어 집합. 형태소 분석이 아니다 — 겹침 계산용 근사다."""
    out = set()
    for w in words(text):
        if len(w) >= 2:
            out.add(_PARTICLE.sub("", w) or w)
    return {t for t in out if len(t) >= 2}


def features(text: str) -> dict:
    text = text or ""
    ws = words(text)
    sents = [s for s in re.split(r"(?<=[.!?])\s+|(?<=다)\s+", text) if s.strip()]
    bigrams = Counter(zip(ws, ws[1:]))
    return {
        "chars": len(text),
        "chars_nospace": len(re.sub(r"\s", "", text)),
        "words": len(ws),
        "sentences": len(sents),
        "unique_ratio": round(len(set(ws)) / len(ws), 4) if ws else 0.0,
        "repeated_bigrams": sum(c - 1 for c in bigrams.values() if c > 1),
        "unfinished": bool(text) and not bool(_SENT_END.search(text.strip())),
        "text_ref": bool(_TEXT_REF.search(text)) or bool(_LATIN_RUN.search(text)),
        "latin_run": bool(_LATIN_RUN.search(text)),
        "cjk": bool(_CJK.search(text)),
        "kana": bool(_KANA.search(text)),
        "no_hangul": bool(text.strip()) and not bool(_HANGUL.search(text)),
        "action": len(_ACTION.findall(text)),
        "scene": len(_SCENE.findall(text)),
        "person": len(_PERSON.findall(text)),
    }


def quantiles(vals: list) -> dict:
    if not vals:
        return {}
    s = sorted(vals)

    def q(p):
        return round(s[min(len(s) - 1, int(p * len(s)))], 2)
    return {"n": len(s), "mean": round(sum(s) / len(s), 2), "median": round(st.median(s), 2),
            "p25": q(0.25), "p75": q(0.75), "p90": q(0.90), "p95": q(0.95),
            "max": s[-1]}


def load_dict_arm(path: Path) -> dict:
    """{video_id: [caption, …]} 형식 저장분."""
    d = json.loads(path.read_text(encoding="utf-8"))
    return {v: [(i, c) for i, c in enumerate(caps)] for v, caps in d.items()}


def load_segments_arm(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    vid = doc["video_id"]
    return {vid: [(s["idx"], s.get("caption", "")) for s in doc["segments"]]}


def pair(arm_a: dict, arm_b: dict) -> list:
    """(video, idx, caption_a, caption_b). 양쪽에 다 있는 구간만."""
    out = []
    for v in sorted(set(arm_a) & set(arm_b)):
        b_by_idx = dict(arm_b[v])
        for i, ca in arm_a[v]:
            if i in b_by_idx:
                out.append((v, i, ca, b_by_idx[i]))
    return out


def analyse(pairs: list, label_a: str, label_b: str) -> dict:
    fa = [features(a) for _, _, a, _ in pairs]
    fb = [features(b) for _, _, _, b in pairs]

    def agg(fs, key):
        return quantiles([f[key] for f in fs])

    def rate(fs, key):
        return round(sum(bool(f[key]) for f in fs) / len(fs), 4) if fs else None

    jac, only_a, only_b, lendiff = [], Counter(), Counter(), []
    for (_, _, a, b), x, y in zip(pairs, fa, fb):
        ta, tb = content_tokens(a), content_tokens(b)
        u = ta | tb
        jac.append(len(ta & tb) / len(u) if u else 1.0)
        only_a.update(ta - tb)
        only_b.update(tb - ta)
        lendiff.append(x["chars"] - y["chars"])

    return {
        "n_pairs": len(pairs),
        "A_label": label_a, "B_label": label_b,
        "length": {"A_chars": agg(fa, "chars"), "B_chars": agg(fb, "chars"),
                   "A_chars_nospace": agg(fa, "chars_nospace"),
                   "B_chars_nospace": agg(fb, "chars_nospace"),
                   "A_words": agg(fa, "words"), "B_words": agg(fb, "words"),
                   "char_diff_A_minus_B": quantiles(lendiff)},
        "truncation_candidate": {
            "note": ("저장분에 token 수가 없어 **문장이 끝나지 않은 채 멈춘 캡션**을 "
                     f"절단 후보로 센다. 공유 상한 max_new_tokens={SHARED_MAX_NEW_TOKENS}"),
            "A_rate": rate(fa, "unfinished"), "B_rate": rate(fb, "unfinished")},
        "redundancy": {"A_unique_ratio": agg(fa, "unique_ratio"),
                       "B_unique_ratio": agg(fb, "unique_ratio"),
                       "A_repeated_bigrams": agg(fa, "repeated_bigrams"),
                       "B_repeated_bigrams": agg(fb, "repeated_bigrams"),
                       "A_sentences": agg(fa, "sentences"), "B_sentences": agg(fb, "sentences")},
        "text_reference_candidate": {
            "note": ("overlay(편집 자막)와 in-scene text(간판·라벨)를 자동으로 구분하지 "
                     "못한다. 오염률·전사율이 아니라 **후보 탐지**다"),
            "A_rate": rate(fa, "text_ref"), "B_rate": rate(fb, "text_ref"),
            "A_latin_run_rate": rate(fa, "latin_run"), "B_latin_run_rate": rate(fb, "latin_run"),
            "paired": dict(Counter(
                ("both" if x["text_ref"] and y["text_ref"] else
                 "A_only" if x["text_ref"] else
                 "B_only" if y["text_ref"] else "neither")
                for x, y in zip(fa, fb)))},
        "information_selection_lowconf": {
            "note": ("POS 분석기 미설치 — 표층 어미·조사 휴리스틱이다. 지표가 아니라 "
                     "방향 확인용이고, 정확한 semantic GT가 아니다"),
            "A_action": agg(fa, "action"), "B_action": agg(fb, "action"),
            "A_scene": agg(fa, "scene"), "B_scene": agg(fb, "scene"),
            "A_person": agg(fa, "person"), "B_person": agg(fb, "person")},
        "paired_divergence": {
            "lexical_overlap_jaccard": quantiles(jac),
            "A_only_top": only_a.most_common(25),
            "B_only_top": only_b.most_common(25)},
        "script": {"A_cjk_rate": rate(fa, "cjk"), "B_cjk_rate": rate(fb, "cjk"),
                   "A_kana_rate": rate(fa, "kana"), "B_kana_rate": rate(fb, "kana"),
                   "A_no_hangul_rate": rate(fa, "no_hangul"),
                   "B_no_hangul_rate": rate(fb, "no_hangul")},
    }


def divergent_examples(pairs: list, k: int = 30) -> list:
    """초점이 크게 갈린 쌍을 **결정적 규칙**으로 뽑는다 — 결과를 보고 고르지 않는다.

    정렬 키: (겹침 낮은 순, 길이차 큰 순, video, idx). 동점도 결정적으로 갈린다.
    """
    scored = []
    for v, i, a, b in pairs:
        ta, tb = content_tokens(a), content_tokens(b)
        u = ta | tb
        j = len(ta & tb) / len(u) if u else 1.0
        scored.append((round(j, 6), -abs(len(a) - len(b)), v, i, a, b))
    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return [{"video_id": v, "seg_idx": i, "jaccard": j, "A": a, "B": b}
            for j, _, v, i, a, b in scored[:k]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=SCRATCH / "caption_style_paired.json")
    ap.add_argument("--examples", type=int, default=30)
    args = ap.parse_args()

    result = {
        "probe": "caption_style_paired",
        "run_kind": "post_hoc_paired_descriptive",
        "adoption_evidence": False,
        "hypothesis_test": False,
        "boundary": {"m8_c2_panel_touched": False, "test_split_touched": False,
                     "p2_p3_touched": False, "gpu_used": False},
        "limits": [
            "AI Hub는 재사용 표본이다 — 새로 뽑은 확률표본이 아니다",
            "사후 기술 분석이다. 기존 2×2 성능 결론을 수정하지 않는다",
            "모델의 일반 특성을 확정하지 않는다 — 이 프롬프트·양자화·표본에서의 관찰이다",
            "text_reference_candidate는 overlay GT가 아니다 — 편집 자막과 실제 장면 글자를 "
            "자동으로 구분하지 못한다",
            "POS 분석기가 없어 정보 선택 지표는 표층 휴리스틱이다(저신뢰)",
        ],
        "runs": {},
    }

    # PRIMARY — prompt를 P0로 고정해 모델 차이만 남긴다
    a = load_dict_arm(AIHUB / "qwen25_3b__P0.json")
    b = load_dict_arm(AIHUB / "qwen3vl_4b__P0.json")
    p_primary = pair(a, b)
    result["runs"]["primary_aihub_P0"] = analyse(p_primary, "qwen25_3b/P0", "qwen3vl_4b/P0")

    # SENSITIVITY — 같은 표본, prompt P1
    p1 = pair(load_dict_arm(AIHUB / "qwen25_3b__P1.json"),
              load_dict_arm(AIHUB / "qwen3vl_4b__P1.json"))
    result["runs"]["sensitivity_aihub_P1"] = analyse(p1, "qwen25_3b/P1", "qwen3vl_4b/P1")

    # CROSS-CHECK — dev 저장분
    p_dev = pair(load_dict_arm(SWEEP / "qwen25_3b_4bit__P0.json"),
                 load_dict_arm(SWEEP / "qwen3vl_4b__P0.json"))
    result["runs"]["crosscheck_dev_P0"] = analyse(p_dev, "qwen25_3b_4bit/P0", "qwen3vl_4b/P0")

    # ILLUSTRATION — 동시점 생성 2 arm (케이스 스터디)
    cs3 = CASESTUDY / "3b_fresh" / "work" / "pland_costco_hosting" / "segments.json"
    cs4 = CASESTUDY / "4b_fresh" / "work" / "pland_costco_hosting" / "segments.json"
    if cs3.exists() and cs4.exists():
        p_cs = pair(load_segments_arm(cs3), load_segments_arm(cs4))
        result["runs"]["illustration_casestudy"] = analyse(p_cs, "3b_fresh", "4b_fresh")
        result["examples_casestudy"] = divergent_examples(p_cs, 10)

    result["examples_primary"] = divergent_examples(p_primary, args.examples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    for name, r in result["runs"].items():
        L = r["length"]
        print(f"\n[{name}] 쌍 {r['n_pairs']}")
        print(f"  길이 중앙값   A {L['A_chars']['median']:>6}  B {L['B_chars']['median']:>6}"
              f"   (p90 {L['A_chars']['p90']} / {L['B_chars']['p90']})")
        t = r["truncation_candidate"]
        print(f"  미완결 비율   A {t['A_rate']:>6}  B {t['B_rate']:>6}")
        x = r["text_reference_candidate"]
        print(f"  글자 언급     A {x['A_rate']:>6}  B {x['B_rate']:>6}   {x['paired']}")
        print(f"  어휘 겹침     중앙값 {r['paired_divergence']['lexical_overlap_jaccard']['median']}")
        s = r["script"]
        print(f"  한자/가나     A {s['A_cjk_rate']}/{s['A_kana_rate']}  "
              f"B {s['B_cjk_rate']}/{s['B_kana_rate']}")
    print(f"\n저장: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
