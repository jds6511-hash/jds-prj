import numpy as np
import common
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

def test_partial_artifacts_do_not_skip(monkeypatch, tmp_path, capsys):
    # emb_sub.npy만 남고 meta.json이 없는 상태(중단된 실행) → --force 없이도 재생성해야 함
    # (emb_sub.npy만 보고 skip하면 emb_cap.npy·meta.json이 영영 안 생김) [리뷰 반영]
    video_id = "v1"
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
                "subtitle": "s", "caption": "c"} for i in range(2)]
    common.save_segments(wdir / "segments.json", {"n_segments": 2, "segments": segments})
    np.save(wdir / "emb_sub.npy", np.zeros((2, 4), dtype=np.float32))  # 중단된 이전 실행의 잔여물

    class FakeModel:
        def encode(self, texts, batch_size, normalize_embeddings, show_progress_bar=False):
            return np.full((len(texts), 4), 0.5, dtype=np.float32)  # norm=1

    monkeypatch.setattr(m4_index, "_load_model", lambda name: FakeModel())
    cfg = {"paths": {"work": str(tmp_path)}, "embed_model": "m", "embed_batch_size": 2,
           "seg_len_sec": 5}
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr("sys.argv", ["m4_index.py", "--config", "dummy.yaml",
                                     "--video-id", video_id])
    m4_index.main()
    out = capsys.readouterr().out
    assert "이미 존재" not in out
    assert (wdir / "emb_cap.npy").exists() and (wdir / "meta.json").exists()
