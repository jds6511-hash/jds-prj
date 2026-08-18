"""로컬 LLM 로더 (M8 리포트 생성·M9 judge 공용). 클라우드 API 금지."""
import hashlib

import common

_cache = {}


def make_llm(model_name: str, max_new_tokens: int = 2048, load_4bit: bool = False):
    """prompt -> str 생성 함수 반환. 모델은 최초 1회만 로딩.

    load_4bit: True면 BitsAndBytesConfig(NF4)로 4bit 양자화 로딩 (로컬 저VRAM 대응).
    [m8m9-prompt-critique B-7]
    """
    # 캐시 키에 load_4bit 포함 — 같은 모델을 다른 정밀도로 요청하면 먼저 로드된 쪽을
    # 조용히 재사용하는 무증상 오류 방지 [리뷰 2026-07-11 Major]
    cache_key = (model_name, load_4bit)

    def generate(prompt: str, **gen_kwargs) -> str:
        """gen_kwargs는 `mdl.generate`에 그대로 전달된다 — M8이 반복 루프를 감지했을 때
        `no_repeat_ngram_size`로 재생성하는 경로에만 쓴다(m8_report 참조).
        """
        if cache_key not in _cache:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(model_name)
            if load_4bit:
                from transformers import BitsAndBytesConfig
                quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                           bnb_4bit_compute_dtype=torch.bfloat16)
                mdl = AutoModelForCausalLM.from_pretrained(
                    model_name, quantization_config=quant, device_map="auto")
            else:
                mdl = AutoModelForCausalLM.from_pretrained(
                    model_name, torch_dtype=torch.bfloat16, device_map="auto")
            _cache[cache_key] = (tok, mdl)
        tok, mdl = _cache[cache_key]
        # provenance가 **실효값**을 읽을 수 있게 노출한다. 요청한 load_4bit이
        # 무시된 채 돌았던 전례가 캡션 쪽에 있어(2026-08-10), 요청값만으로는
        # 무엇이 실제로 올라갔는지 알 수 없다.
        generate.model, generate.tokenizer = mdl, tok
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        import torch
        inputs = tok([text], return_tensors="pt").to(mdl.device)
        with torch.inference_mode():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                               **gen_kwargs)
        return tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

    # 지연 로딩이라 첫 호출 전에는 실효값을 알 수 없다. 요청값은 지금 남긴다.
    generate.spec = {"model_name": model_name, "max_new_tokens": max_new_tokens,
                     "requested_4bit": load_4bit}
    generate.model = generate.tokenizer = None
    return generate


def llm_provenance(gen, role: str, prompts: dict) -> dict:
    """M8/M9 산출물에 붙일 생성 조건. **요청값과 실효값을 둘 다 남긴다.**

    캡션 쪽(m3_generate.caption_provenance)과 같은 원칙이다 — `vlm_4bit`가 무시된
    채 bf16으로 돌았던 사고가 있었고, config만 남겨서는 그것을 사후에 못 봤다.
    여기서는 `quantization_mismatch`로 불일치를 **명시적 신호**로 만든다.

    prompts: 이름 → 프롬프트 텍스트(또는 템플릿 소스). 내용 해시만 남긴다 —
    원문을 통째로 넣으면 결과 파일이 프롬프트 사본이 된다.

    **모델이 안 올라간 채로 부를 수 있다**(생성 호출 0회). 그때 실효값을 조용히
    None으로 두면 "기록됐는데 비어 있다"와 구분이 안 되므로 `model_loaded`로 밝힌다.
    """
    spec = getattr(gen, "spec", {}) or {}
    mdl = getattr(gen, "model", None)
    conf = getattr(mdl, "config", None)
    quant = getattr(conf, "quantization_config", None) if conf is not None else None
    effective_quantized = quant is not None

    prov = {
        "role": role,                                    # report / judge
        "model_loaded": mdl is not None,
        "requested_model": spec.get("model_name"),
        "requested_4bit": spec.get("requested_4bit"),
        "max_new_tokens": spec.get("max_new_tokens"),
        "do_sample": False,                              # generate()가 고정한 값
        "effective_model_id": getattr(conf, "_name_or_path", None),
        "effective_model_revision": getattr(conf, "_commit_hash", None),
        "effective_dtype": str(getattr(mdl, "dtype", None)) if mdl is not None else None,
        "effective_quantized": effective_quantized if mdl is not None else None,
        "attn_implementation": getattr(conf, "_attn_implementation", None),
        "prompt_sha256": {k: hashlib.sha256((v or "").encode("utf-8")).hexdigest()
                          for k, v in (prompts or {}).items()},
        "env": common.env_provenance(),
    }
    prov["quantization_mismatch"] = bool(
        mdl is not None and bool(spec.get("requested_4bit")) != effective_quantized)
    return prov
