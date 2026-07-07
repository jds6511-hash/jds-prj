"""로컬 LLM 로더 (M8 리포트 생성·M9 judge 공용). 클라우드 API 금지."""
_cache = {}


def make_llm(model_name: str, max_new_tokens: int = 2048, load_4bit: bool = False):
    """prompt -> str 생성 함수 반환. 모델은 최초 1회만 로딩.

    load_4bit: True면 BitsAndBytesConfig(NF4)로 4bit 양자화 로딩 (로컬 저VRAM 대응).
    [m8m9-prompt-critique B-7]
    """
    def generate(prompt: str) -> str:
        if model_name not in _cache:
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
            _cache[model_name] = (tok, mdl)
        tok, mdl = _cache[model_name]
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        import torch
        inputs = tok([text], return_tensors="pt").to(mdl.device)
        with torch.inference_mode():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        return tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    return generate
