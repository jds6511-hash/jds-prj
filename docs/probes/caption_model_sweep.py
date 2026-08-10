"""[캡션 모델 x 프롬프트 전면 재비교 — dev 전용, 채택 아님, 실측용]

**왜 다시 하나.** 앞선 캡션 비교 3건(varco / qwen3vl / qwen25vl_size)은 후보 검증
규약(DESIGN_SPEC 8-7) 5항목을 서로 다르게 위반했다. 특히 varco·qwen3vl은 5항목 중
0개를 충족한다 — α 재탐색 없음, 프롬프트는 현행 것 고정, 기준선이 **다른 환경에서
생성된 저장분**, 캡션 전량 미저장, 검출 한계 미병기. 그 상태의 Δ는 모델 차이를 잰
값이라고 말할 수 없다(VARCO의 Δ-0.0455는 나중에 측정된 **생성 환경 효과 Δ-0.0879**보다
작다). 이 프로브는 규약 5항목을 전부 지켜 처음부터 다시 잰다.

**설계.**
- **모델 6종 x 프롬프트 4종 = 24 arm.** 현행 모델은 P0~P3 ablation을 이미 거쳐 P0을
  골랐다(0.694 vs 0.617/0.589/0.583). **후보에게 같은 기회를 준다** — 계열이 다르면
  프롬프트가 옮겨가지 않는다는 것이 7B에서 실측됐다(같은 P0에서 캡션 길이 절반).
- **전 arm 서버 동일 환경 생성.** 저장된 노트북 산출분(`cur`)은 참고로만 병기하고
  대비의 기준선으로 쓰지 않는다.
- **채널 격리**: 주지표는 **캡션 단독 α=0.0**. 융합 α=0.5와 arm별 α*도 병기한다.
- **오염 재시도**를 운영과 동일하게 적용한다(감지 시 샘플링 최대 2회, 그래도 오염이면
  greedy 유지 — m3_generate.caption_all).
- **생성물 전량 저장**: arm별 캡션 655개를 `_scratch/caption_sweep_captions/`에 남긴다.
  요약만 남기면 다른 각도로 볼 때 GPU를 다시 써야 한다(1.5시간 낭비 전례).
- **비전 경로 sanity check**: arm마다 실제 프레임과 검은 이미지의 캡션을 비교한다.
  같으면 이미지가 안 들어간 것이다 — VARCO에 그 전례가 있다(device_map="auto"가
  image_newline을 meta device에 남겨 이미지와 무관한 동일 출력).

**한계로 남기는 것.** `vlm_max_pixels`와 `vlm_max_new_tokens`는 현행 모델 기준으로
정한 값인데 전 arm에 동일 적용한다(대칭). 후보별 재탐색은 하지 않으므로 결과에
절단율을 병기한다. 다중비교 보정도 하지 않는다 — arm이 24개이므로 개별 유의 판정을
독립적으로 강하게 읽지 마라.

**라이선스 주의.** HyperCLOVAX는 `hyperclovax-seed` 커스텀 라이선스, Kanana·VARCO는
각 저장소 조건을 따른다. 이 프로브는 dev 평가 목적의 로컬 추론만 하고 가중치나
생성물을 재배포하지 않는다. 두 모델은 `trust_remote_code=True`가 필요하다 —
저장소 코드를 실행하므로 공식 저장소만 쓴다.

work/·results/ 불변, 재임베딩은 메모리에서만, test 미접촉.
재현: python docs/probes/caption_model_sweep.py [--models ...] [--prompts P0,P1]
"""
import argparse, gc, json, statistics as st, sys, time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
from m4_index import embed_texts                       # noqa: E402
from m5_search import VideoIndex                       # noqa: E402
from m6_evaluate import evaluate, grid_search_alpha    # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
CAPDIR = OUT / "caption_sweep_captions"

# 프롬프트 4종 — ablation_plan_draft.md 3-6에서 정의하고 현행 모델로 이미 비교한 것.
# 후보에게 같은 격자를 준다. P0이 현행 확정값(config.yaml caption_prompt).
PROMPTS = {
    "P0": ("이 장면을 한 문장의 한국어로 객관적으로 묘사하라. 화면에 보이지 않는 것은 "
           "쓰지 마라. 화면에 자막이나 글자가 보이더라도 그 글자를 그대로 옮겨 적지 "
           "말고, 인물의 행동과 배경 등 시각적 내용만 묘사하라."),
    "P1": ("이 장면에 보이는 인물의 행동, 주요 객체, 배경을 한국어 두 문장 이내로 "
           "객관적으로 묘사하라. 화면에 보이지 않는 것은 쓰지 마라."),
    "P2": ("이 장면에 보이는 주요 객체와 장소를 한국어 한 문장으로 나열하듯 묘사하라. "
           "추측하지 마라."),
    "P3": ("이 장면에서 인물이 무엇을 하고 있는지 한국어 한 문장으로 묘사하라. 인물이 "
           "없으면 화면의 상태 변화를 묘사하라. 보이지 않는 것은 쓰지 마라."),
    # 2단계 전용(기본 격자에 없다). P0~P3이 전부 문장 수를 제한하는데, 그 제한이
    # 모델마다 다르게 먹는다는 것이 1단계에서 드러났다 — 7B는 "한 문장"을 지켜
    # 64.9자에서 멈추고(절단율 0.3%) 3B는 같은 지시에서 127.1자를 쓴다. 길이를
    # 맞추면 순위가 뒤집힌다(caption_length_matched.json, 8개 대비 전부).
    # P4는 문장 수 제한을 빼서 **전 모델에 같은 여지**를 준다.
    "P4": ("이 장면에 보이는 인물의 행동, 주요 객체, 배경을 한국어로 구체적으로 "
           "묘사하라. 문장 수는 제한하지 않는다. 화면에 보이지 않는 것은 쓰지 마라. "
           "화면의 글자를 그대로 옮겨 적지 마라."),
}
# 1단계(사전 등록) 격자. P4는 사후 가설이라 기본값에서 뺀다 — 섞으면 사전 등록
# 격자의 다중비교 구조가 바뀐다. 2단계는 `--prompts P4 --max-new 256`로 따로 돈다.
STAGE1_PROMPTS = ["P0", "P1", "P2", "P3"]

# 모델 6종. 로딩 인자는 각 공식 모델카드 기준(2026-08-08 확인).
MODELS = {
    "qwen25_3b_4bit": {"id": "Qwen/Qwen2.5-VL-3B-Instruct", "family": "qwen25", "q4": True},
    "qwen25_7b":      {"id": "Qwen/Qwen2.5-VL-7B-Instruct", "family": "qwen25", "q4": False},
    "qwen3vl_4b":     {"id": "Qwen/Qwen3-VL-4B-Instruct", "family": "qwen3vl", "q4": False},
    # 4bit 변형 — 6GB 노트북에 올리려면 필수(실측 최대 3.27GB). 서버에서 같은 환경으로
    # 재서 **양자화 효과와 생성 환경 효과를 분리**한다(규약 4항 동일 환경 대조군).
    "qwen3vl_4b_q4":  {"id": "Qwen/Qwen3-VL-4B-Instruct", "family": "qwen3vl", "q4": True},
    "varco_1_7b":     {"id": "NCSOFT/VARCO-VISION-2.0-1.7B", "family": "varco", "q4": False},
    "hyperclovax_3b": {"id": "naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B",
                       "family": "hyperclovax", "q4": False},
    "kanana_3b":      {"id": "kakaocorp/kanana-1.5-v-3b-instruct",
                       "family": "kanana", "q4": False},
}


def _resize(img: Image.Image, max_pixels: int) -> Image.Image:
    """전 arm 동일 상한. 원본 rep_frame이 1920x1080이라 무캡이면 vision 토큰이
    폭증해 세그먼트당 수 분씩 걸린다(VARCO에서 실측: 87개/4시간)."""
    w, h = img.size
    if w * h <= max_pixels:
        return img
    s = (max_pixels / (w * h)) ** 0.5
    return img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def _gen_kwargs(sample: bool, max_new: int, rep_penalty: float = 1.0) -> dict:
    """전 계열 동일 디코딩. 기본 greedy, 오염 재시도 시에만 샘플링(운영과 동일).

    `rep_penalty`를 빠뜨리면 **현행 모델만** 운영 설정(`vlm_rep_penalty: 1.1`)을 받는
    비대칭이 생긴다 — m3_generate.caption_frame이 config에서 읽어 적용하기 때문이다.
    현행 전용으로 고른 값이지만(3B-4bit의 한자·가나 혼입 대책) 전 arm에 같이 걸어
    대칭을 맞추고, 그 사실을 결과에 남긴다 [규약 (3)].
    """
    g = {"max_new_tokens": max_new, "do_sample": False}
    if sample:
        g.update(do_sample=True, temperature=0.7, top_p=0.9)
    if rep_penalty and rep_penalty != 1.0:
        g["repetition_penalty"] = rep_penalty
    return g


def load_captioner(spec: dict, cfg: dict, max_new: int | None = None):
    """(captioner, closer) 반환. captioner(image_path, prompt, sample=False) -> str.

    max_new를 주면 config의 토큰 상한을 덮어쓴다 — 후속 절단 확인용(§arm_key 참조).
    """
    fam, mid = spec["family"], spec["id"]
    maxpx = cfg["vlm_max_pixels"]
    max_new = max_new or cfg.get("vlm_max_new_tokens", 128)
    rp = cfg.get("vlm_rep_penalty", 1.0)
    print(f"  로딩: {mid} ({fam})", flush=True)

    if fam == "qwen25":
        from m3_generate import load_vlm, caption_frame
        acfg = {**cfg, "caption_model": mid, "vlm_4bit": spec["q4"]}
        model, proc = load_vlm(acfg)

        def cap(p, prompt, sample=False):
            return caption_frame(p, prompt, model, proc, acfg, sample=sample)

    elif fam == "qwen3vl":
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        # q4를 반영한다. 이 분기가 dtype을 하드코딩하고 있어서, 4bit arm을 추가해도
        # 조용히 bf16으로 돌아 중복 arm이 나왔다(VRAM 11.4GB로 발각, 2026-08-10).
        kw = dict(device_map={"": 0})
        if spec["q4"]:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
        else:
            kw["dtype"] = torch.bfloat16
        model = Qwen3VLForConditionalGeneration.from_pretrained(mid, **kw).eval()
        proc = AutoProcessor.from_pretrained(mid, min_pixels=256 * 28 * 28,
                                             max_pixels=maxpx)

        def cap(p, prompt, sample=False):
            msgs = [{"role": "user", "content": [
                {"type": "image", "image": str(p)}, {"type": "text", "text": prompt}]}]
            inputs = proc.apply_chat_template(
                msgs, tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                g = model.generate(**inputs, **_gen_kwargs(sample, max_new, rp))
            return proc.batch_decode(g[:, inputs["input_ids"].shape[1]:],
                                     skip_special_tokens=True)[0].strip()

    elif fam == "varco":
        from transformers import LlavaOnevisionForConditionalGeneration, AutoProcessor
        # device_map="auto"는 이 구조를 잘못 프로파일링해 image_newline을 meta device에
        # 남기고 CPU 오프로드 → 비전 경로가 깨져 이미지와 무관한 동일 출력이 나온다(실측).
        model = LlavaOnevisionForConditionalGeneration.from_pretrained(
            mid, dtype=torch.float16, attn_implementation="sdpa",
            device_map={"": 0}).eval()
        proc = AutoProcessor.from_pretrained(mid)

        def cap(p, prompt, sample=False):
            img = _resize(Image.open(p).convert("RGB"), maxpx)
            conv = [{"role": "user", "content": [
                {"type": "image", "image": img}, {"type": "text", "text": prompt}]}]
            inputs = proc.apply_chat_template(
                conv, add_generation_prompt=True, tokenize=True,
                return_dict=True, return_tensors="pt").to(model.device, torch.float16)
            with torch.inference_mode():
                g = model.generate(**inputs, **_gen_kwargs(sample, max_new, rp))
            return proc.batch_decode(g[:, inputs["input_ids"].shape[1]:],
                                     skip_special_tokens=True)[0].strip()

    elif fam == "hyperclovax":
        from transformers import AutoModelForCausalLM, AutoProcessor
        model = AutoModelForCausalLM.from_pretrained(
            mid, trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval()
        proc = AutoProcessor.from_pretrained(mid, trust_remote_code=True)

        def cap(p, prompt, sample=False):
            chat = [{"role": "user", "content": [
                {"type": "text", "text": prompt}, {"type": "image", "image": str(p)}]}]
            inputs = proc.apply_chat_template(
                chat, tokenize=True, return_dict=True, return_tensors="pt",
                add_generation_prompt=True).to(model.device)
            with torch.inference_mode():
                g = model.generate(**inputs, **_gen_kwargs(sample, max_new, rp))
            n = inputs["input_ids"].shape[1]
            return proc.batch_decode(g[:, n:], skip_special_tokens=True)[0].strip()

    elif fam == "kanana":
        # 저장소 config의 auto_map이 **AutoModelForVision2Seq만** 선언하는데 그 Auto
        # 클래스는 transformers 5.x에서 제거됐다. 후속 이름(AutoModelForImageTextToText)
        # 으로 바꿔도 매핑에 없어 "Unrecognized configuration class"가 난다(실측 2건).
        # 벤더 코드를 고치는 대신 원격 모듈에서 클래스를 직접 가져온다 — transformers가
        # 공식 지원하는 경로다.
        # 추가 벽 2건(실측): ① einops·timm 미설치 → 원격 모듈 import 실패.
        # ② 벤더 코드가 비전 인코더를 flash_attention_2로 만든다. 폴백 try/except가
        #    있긴 한데 **망가져 있다** — 첫 시도가 config.vision_config에 flash를
        #    써넣고 실패하고, 폴백이 같은 config 객체를 재사용해 또 flash로 간다.
        #    from_pretrained의 attn_implementation="sdpa"도 하위 config까지 못 내려간다.
        #    벤더 파일을 고치지 않고, transformers가 구현을 확정하는 지점만 잠시
        #    가로채 flash 요청을 sdpa로 바꾼다(로드 동안만, 끝나면 원복).
        from transformers import AutoProcessor
        from transformers.modeling_utils import PreTrainedModel
        from transformers.dynamic_module_utils import get_class_from_dynamic_module
        cls = get_class_from_dynamic_module(
            "modeling.KananaVForConditionalGeneration", mid)
        _orig = PreTrainedModel.get_correct_attn_implementation

        def _no_flash(self, requested, is_init_check=False):
            if isinstance(requested, str) and "flash_attention" in requested:
                requested = "sdpa"
            return _orig(self, requested, is_init_check)

        PreTrainedModel.get_correct_attn_implementation = _no_flash
        try:
            model = cls.from_pretrained(
                mid, dtype=torch.bfloat16, device_map={"": 0},
                attn_implementation="sdpa", trust_remote_code=True).eval()
        finally:
            PreTrainedModel.get_correct_attn_implementation = _orig
        proc = AutoProcessor.from_pretrained(mid, trust_remote_code=True)

        def cap(p, prompt, sample=False):
            # KananaVProcessor는 표준 apply_chat_template을 안 쓴다(프로세서 쪽
            # chat_template이 비어 있어 ValueError). 벤더가 정의한 형식 그대로 준다:
            #   {"conv": [{"role": "user", "content": "<image>"}, {...텍스트}],
            #    "image": [PIL.Image]}
            img = _resize(Image.open(p).convert("RGB"), maxpx)
            data = {"conv": [{"role": "user", "content": "<image>"},
                             {"role": "user", "content": prompt}],
                    "image": [img]}
            batch = proc.batch_encode_collate([data], add_generation_prompt=True,
                                              max_length=None)
            batch = {k: (v.to(model.device) if hasattr(v, "to") else v)
                     for k, v in batch.items()}
            with torch.inference_mode():
                g = model.generate(**batch, **_gen_kwargs(sample, max_new, rp))
            n = batch["input_ids"].shape[1]
            return proc.batch_decode(g[:, n:], skip_special_tokens=True)[0].strip()

    else:
        raise ValueError(f"알 수 없는 계열: {fam}")

    def close():
        # `del model` 을 쓰면 안 된다 — 중첩 함수 안의 del은 그 이름을 **close의 지역
        # 변수로 만들어** UnboundLocalError를 낸다(파일럿 1차에서 6.5시간 날린 원인).
        # nonlocal로 바깥 이름을 잡고 참조만 끊는다.
        nonlocal model, proc
        model = proc = None
        gc.collect()
        torch.cuda.empty_cache()

    return cap, close


def seg_similarity(idx, vids) -> dict:
    """영상 안 캡션 임베딩의 유사도. **낮을수록 세그먼트가 서로 구별된다.**

    MRR이 안 움직여도 이 값이 내려가면 "변별력은 늘었는데 지표가 못 잡는다"를 볼 수
    있다. AI Hub 외부 벤치마크에서 절대값이 무작위 근처였던 이유를 설명한 지표와 같다
    (AI Hub 전체 쌍 0.760 vs 본 인덱스 0.563).
    """
    adj, allp = [], []
    for v in vids:
        e = idx[v].emb_cap
        e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
        if len(e) < 2:
            continue
        adj.append(float(np.mean(np.sum(e[:-1] * e[1:], axis=1))))
        s = e @ e.T
        allp.append(float(s[np.triu_indices(len(e), 1)].mean()))
    return {"adjacent": round(float(np.mean(adj)), 4),
            "all_pairs": round(float(np.mean(allp)), 4),
            "gap": round(float(np.mean(adj) - np.mean(allp)), 4)}


def arm_key(pkey: str, max_new: int | None, default_max_new: int) -> str:
    """arm·캡션파일 식별자. 토큰 상한을 덮어쓰면 반드시 키가 갈려야 한다.

    안 갈리면 128토큰으로 만든 캡션을 상한 512 arm이 조용히 재사용해서
    "상한을 올려도 안 변한다"는 완전히 틀린 결론이 나온다.
    """
    if max_new is None or max_new == default_max_new:
        return pkey
    return f"{pkey}@{max_new}"


def _cached_caps(mkey, pkey, vids, segs):
    """이미 저장된 캡션 파일이 이번 실행의 세그먼트 수와 맞으면 그대로 쓴다."""
    f = CAPDIR / f"{mkey}__{pkey}.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    if any(v not in d or len(d[v]) != len(segs[v]) for v in vids):
        return None
    return d


def vision_sanity(cap, frame: Path, prompt: str, tmp: Path) -> dict:
    """실제 프레임 vs 검은 이미지. 출력이 같으면 이미지가 안 들어간 것이다.

    VARCO에서 실제로 났던 사고(비전 경로가 죽어 이미지와 무관한 동일 출력)를
    arm마다 자동으로 걸러낸다. 이걸 안 하면 '후보가 졌다'가 아니라 '후보에게
    이미지를 안 줬다'를 측정하게 된다.
    """
    Image.new("RGB", (640, 360), (0, 0, 0)).save(tmp)
    real, black = cap(frame, prompt), cap(tmp, prompt)
    return {"ok": real.strip() != black.strip(),
            "real": real[:120], "black": black[:120]}


def gen_captions(cap, vids, segs_by_vid, prompt, wdirs) -> tuple[dict, dict]:
    caps, retried, still, truncated = {}, 0, 0, 0
    for v in vids:
        out = []
        for i, s in enumerate(segs_by_vid[v]):
            img = wdirs[v] / s["rep_frame"]
            c = cap(img, prompt)
            if common.is_corrupted_caption(c):
                retried += 1
                for _ in range(2):
                    r = cap(img, prompt, sample=True)
                    if r and not common.is_corrupted_caption(r):
                        c = r
                        break
                else:
                    still += 1
            # 문장 종결부호 없이 끝나면 토큰 상한에서 잘렸을 가능성 — 절단율로 병기
            if c and c[-1] not in ".!?。":
                truncated += 1
            out.append(c)
            if i % 100 == 0:
                print(f"    {v[:18]} {i}", flush=True)
        caps[v] = out
    return caps, {"retried": retried, "unresolved": still, "truncated": truncated}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--prompts", default=",".join(STAGE1_PROMPTS))
    ap.add_argument("--limit", type=int, default=None,
                    help="파일럿용: 영상당 프레임 수 제한(절단율·sanity만 볼 때)")
    ap.add_argument("--max-new", type=int, default=None,
                    help="토큰 상한 덮어쓰기. 절단율이 높은 arm의 재측정용 "
                         "(arm 키가 'P0@512'로 갈려 기존 캡션과 섞이지 않는다)")
    a = ap.parse_args()
    models = [m for m in a.models.split(",") if m]
    prompts = [p for p in a.prompts.split(",") if p]

    cfg = common.load_config(str(ROOT / "config.yaml"))
    default_max_new = cfg.get("vlm_max_new_tokens", 128)
    akey = lambda p: arm_key(p, a.max_new, default_max_new)          # noqa: E731
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}
    segs = {v: (base[v].segments[:a.limit] if a.limit else base[v].segments) for v in vids}

    CAPDIR.mkdir(parents=True, exist_ok=True)
    rep_path = OUT / ("caption_sweep_pilot.json" if a.limit else "caption_sweep.json")
    rep = {"note": "dev-only, 채택 아님. 전 arm 서버 동일 환경 생성. test 미접촉.",
           "prompts": PROMPTS, "models": {k: MODELS[k] for k in models},
           "limit": a.limit, "seed": cfg["seed"],
           "caveat": ("arm 24개, 다중비교 보정 없음. vlm_max_pixels·max_new_tokens는 "
                      "현행 기준값을 전 arm 대칭 적용(후보별 재탐색 없음, 절단율 병기)."),
           "arms": {}}
    if rep_path.exists():                      # 재개: 이미 끝난 arm은 건너뛴다
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        rep["arms"] = rep.get("arms", {})

    # ── 사전 등록 (결과 보기 전 확정, 2026-08-08) ──────────────────────────────
    # 경합 부분집합: 현행이 캡션 단독에서 **1위를 못 잡은** 질의만. 이미 만점인 질의는
    # 어떤 모델도 못 올리므로 신호를 희석시킬 뿐이다(dev 96 중 44건이 이미 rank 1,
    # 여지 0.447, CI 폭 ±0.08 — 작은 개선은 전체 집계에서 검출되지 않는다).
    cur_texts = {v: [s.get("caption") or "" for s in base[v].segments] for v in vids}
    cur_rr = np.array([x["mrr"] for x in evaluate(dev, base, 0.0, cfg)["per_query"]])
    contested = [i for i, x in enumerate(cur_rr) if x < 1.0]
    rep["prereg"] = {
        "primary": "캡션 단독 α=0.0 MRR (전체 dev 96)",
        "secondary": f"경합 부분집합 n={len(contested)} (현행이 캡션 단독에서 rank 1 아님)",
        "tertiary": "세그먼트 간 캡션 임베딩 유사도(변별력) — 낮을수록 좋다",
        "independent": ("AI Hub 사람 묘사 대비 chrF·KURE 코사인 — "
                        "docs/probes/aihub_caption_reference.py, 파이프라인 밖 지표"),
        "null_result_rule": ("전 arm이 비유의면 '모델 간 차이 없음'이 아니라 "
                             "'이 평가로는 구분 불가'로 보고하고 independent 지표로 넘긴다"),
        "declared_before_run": True}

    def sub_mrr(rr):
        return round(float(np.mean([rr[i] for i in contested])), 4) if contested else None

    if not a.limit and "cur_laptop" not in rep["arms"]:
        rep["arms"]["cur_laptop"] = {
            "note": "노트북 생성분(참고). 환경이 달라 대비 기준선으로 쓰지 않는다.",
            "mrr_caption_only": round(float(cur_rr.mean()), 4),
            "mrr_caption_only_contested": sub_mrr(cur_rr),
            "mrr_alpha_fixed": evaluate(dev, base, 0.5, cfg)["metrics"]["mrr"],
            "seg_similarity": seg_similarity(base, vids),
            "len_mean": round(st.mean([len(t) for v in vids for t in cur_texts[v]]), 1)}

    for mkey in models:
        spec = MODELS[mkey]
        todo = [p for p in prompts if f"{mkey}/{akey(p)}" not in rep["arms"]]
        if not todo:
            print(f"[{mkey}] 전 프롬프트 완료 — 건너뜀", flush=True)
            continue
        # 이미 생성된 캡션 파일이 있으면 모델을 아예 안 올린다. 두 가지에 쓴다:
        #  (a) 중단 후 재개, (b) **격리 환경에서 만든 캡션 채점** — HyperCLOVAX처럼
        #      원격 코드가 구버전 transformers를 요구하는 모델은 별도 venv에서 생성만
        #      하고, 채점은 본 환경에서 한다(벤더 코드를 고치지 않는다).
        need_gen = [p for p in todo
                    if not _cached_caps(mkey, akey(p), vids, segs)]
        if not need_gen:
            cap, close = (lambda *a, **k: "", lambda: None)
            print(f"[{mkey}] 캡션 파일 재사용 — 모델 로딩 생략", flush=True)
        else:
            cap, close = load_captioner(spec, cfg, a.max_new)
        try:
            sanity = ({"ok": None, "note": "캡션 파일 재사용 — 생성 없음"} if not need_gen
                      else vision_sanity(cap, wdirs[vids[0]] / segs[vids[0]][0]["rep_frame"],
                                         PROMPTS["P0"], OUT / f"_black_{mkey}.png"))
            print(f"[{mkey}] 비전 경로 {sanity.get('ok')}", flush=True)
            for pkey in todo:
                t0 = time.time()
                print(f"[{mkey}/{akey(pkey)}] 생성 시작", flush=True)
                cached = _cached_caps(mkey, akey(pkey), vids, segs)
                if cached is not None:
                    caps = cached
                    stats = {"retried": None, "unresolved": None, "truncated": None,
                             "source": "cached"}
                    print(f"[{mkey}/{akey(pkey)}] 저장된 캡션 재사용", flush=True)
                else:
                    caps, stats = gen_captions(cap, vids, segs, PROMPTS[pkey], wdirs)
                    stats["source"] = "generated"
                n = sum(len(caps[v]) for v in vids)
                arm = {"model": spec["id"], "prompt": pkey,
                       "max_new_tokens": a.max_new or default_max_new,
                       "vision_sanity": sanity,
                       "n_captions": n, "elapsed_sec": round(time.time() - t0, 1),
                       "len_mean": round(st.mean([len(t) for v in vids for t in caps[v]]), 1),
                       "corrupted": sum(1 for v in vids for t in caps[v]
                                        if common.is_corrupted_caption(t)),
                       "truncate_rate": (round(stats["truncated"] / max(n, 1), 4)
                                         if stats["truncated"] is not None else None),
                       **stats}
                (CAPDIR / f"{mkey}__{akey(pkey)}.json").write_text(
                    json.dumps(caps, ensure_ascii=False), encoding="utf-8")
                if not a.limit:
                    idx = {v: VideoIndex(segments=base[v].segments,
                                         emb_sub=base[v].emb_sub,
                                         emb_cap=embed_texts(caps[v], cfg["embed_model"]),
                                         static_mask=base[v].static_mask) for v in vids}
                    arm["seg_similarity"] = seg_similarity(idx, vids)
                    for alpha, name in ((0.0, "caption_only"), (0.5, "alpha_fixed")):
                        r = evaluate(dev, idx, alpha, cfg)
                        rr = np.array([x["mrr"] for x in r["per_query"]])
                        arm[f"mrr_{name}"] = r["metrics"]["mrr"]
                        arm[f"mrr_{name}_contested"] = sub_mrr(rr)
                        arm[f"by_type_{name}"] = {t: m["mrr"]
                                                  for t, m in r["metrics"]["by_type"].items()}
                        arm[f"rr_{name}"] = rr.tolist()
                    gs = grid_search_alpha(dev, idx, cfg)
                    arm["alpha_star"] = gs["alpha_star"]
                    arm["alpha_best_point"] = gs["alpha_best_point"]
                    arm["alpha_curve"] = {str(x["alpha"]): x["mrr"] for x in gs["per_alpha"]}
                rep["arms"][f"{mkey}/{akey(pkey)}"] = arm
                rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
                print(f"[{mkey}/{akey(pkey)}] 길이 {arm['len_mean']} 오염 {arm['corrupted']} "
                      f"절단 {arm['truncate_rate']:.1%} "
                      f"캡션단독 {arm.get('mrr_caption_only', '-')} "
                      f"({arm['elapsed_sec']/60:.1f}분)", flush=True)
        finally:
            close()

    print("->", rep_path)


if __name__ == "__main__":
    main()
