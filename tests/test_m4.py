import numpy as np
import m4_index

def test_embed_texts_l2_normalized(monkeypatch):
    # sentence-transformers를 가짜 인코더로 대체 (GPU 불필요 단위 테스트)
    class FakeModel:
        def encode(self, texts, batch_size, normalize_embeddings, show_progress_bar=False):
            assert normalize_embeddings is True
            rng = np.random.default_rng(0)
            v = rng.normal(size=(len(texts), 8)).astype(np.float32)
            return v / np.linalg.norm(v, axis=1, keepdims=True)
    monkeypatch.setattr(m4_index, "_load_model", lambda name: FakeModel())
    out = m4_index.embed_texts(["안녕", "", "세 번째"], "any-model")
    assert out.shape == (3, 8) and out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-4)  # norm 편차 [4-4]

def test_empty_string_embedded_as_is(monkeypatch):
    # 무발화 subtitle="" 도 그대로 임베딩 (특별 처리 금지) [3-1]
    seen = []
    class FakeModel:
        def encode(self, texts, **kw):
            seen.extend(texts)
            return np.ones((len(texts), 4), dtype=np.float32) * 0.5
    monkeypatch.setattr(m4_index, "_load_model", lambda name: FakeModel())
    m4_index.embed_texts(["", "텍스트"], "m")
    assert seen == ["", "텍스트"]
