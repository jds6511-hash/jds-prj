"""2인 라벨링 일치도(9-1(c) 선택지 B) 도구 테스트.

kappa 계산과 맹검 키트 생성의 계약만 검증한다. ffmpeg 클립 추출은
외부 프로세스라 호출 인자만 확인한다.
"""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import labeling_agreement as la                            # noqa: E402

CATS = ["자막형", "장면형", "복합형"]


class TestCohensKappa:
    def test_perfect_agreement_is_one(self):
        a = ["자막형", "장면형", "복합형", "자막형"]
        assert la.cohens_kappa(a, a, CATS) == pytest.approx(1.0)

    def test_known_two_by_two_example(self):
        """손계산 대조. A: yes 30/no 20, B: yes 30/no 20, 일치 셀 25+15=40.

        p_o = 40/50 = 0.80, p_e = .6*.6 + .4*.4 = 0.52
        k = (0.80 - 0.52) / (1 - 0.52) = 0.28/0.48 = 0.583333...
        """
        a = ["yes"] * 30 + ["no"] * 20
        b = ["yes"] * 25 + ["no"] * 5 + ["yes"] * 5 + ["no"] * 15
        assert la.cohens_kappa(a, b, ["yes", "no"]) == pytest.approx(7 / 12, abs=1e-9)

    def test_systematic_disagreement_is_negative(self):
        a = ["자막형", "장면형"] * 5
        b = ["장면형", "자막형"] * 5
        assert la.cohens_kappa(a, b, CATS) < 0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            la.cohens_kappa(["자막형"], ["자막형", "장면형"], CATS)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            la.cohens_kappa([], [], CATS)

    def test_unknown_category_raises(self):
        """오타·미정의 라벨을 조용히 흘리면 일치율이 조작된다."""
        with pytest.raises(ValueError):
            la.cohens_kappa(["자막형"], ["자막"], CATS)

    def test_single_category_everywhere_is_undefined_not_one(self):
        """둘 다 한 범주만 쓰면 기대 일치=1이라 kappa가 정의되지 않는다.

        여기서 1.0을 돌려주면 "완벽한 일치"로 읽혀 최악의 오보가 된다.
        """
        a = b = ["자막형"] * 10
        assert la.cohens_kappa(a, b, CATS) is None


class TestPercentAgreement:
    def test_counts_exact_matches(self):
        a = ["자막형", "장면형", "복합형", "자막형"]
        b = ["자막형", "복합형", "복합형", "자막형"]
        assert la.percent_agreement(a, b) == pytest.approx(0.75)


class TestConfusion:
    def test_rows_are_labeler1(self):
        a = ["자막형", "자막형", "장면형"]
        b = ["자막형", "장면형", "장면형"]
        m = la.confusion(a, b, CATS)
        assert m["자막형"]["자막형"] == 1
        assert m["자막형"]["장면형"] == 1
        assert m["장면형"]["장면형"] == 1
        assert m["복합형"]["복합형"] == 0


class TestBlindKit:
    """맹검 조건 — 라벨러에게 나가는 파일에 정답 유형이 없어야 한다."""

    def _queries(self):
        return [{"query_id": f"q{i:02d}", "video_id": "v1", "text": f"질의 {i}",
                 "type": CATS[i % 3], "gt_start": i * 10.0, "gt_end": i * 10.0 + 5.0,
                 "split": "test"} for i in range(6)]

    def test_blind_csv_has_no_type_column(self, tmp_path):
        la.write_blind_kit(self._queries(), tmp_path, seed=42)
        rows = list(csv.DictReader(
            (tmp_path / "labels_blind.csv").open(encoding="utf-8-sig")))
        assert "type" not in rows[0]
        assert "query_id" not in rows[0]          # 정답 파일과 대조 불가해야 한다
        assert rows[0]["유형"] == ""              # 라벨러가 채울 빈 칸

    def test_keymap_is_separate_and_complete(self, tmp_path):
        qs = self._queries()
        la.write_blind_kit(qs, tmp_path, seed=42)
        km = json.loads((tmp_path / "_keymap.json").read_text(encoding="utf-8"))
        assert set(km.values()) == {q["query_id"] for q in qs}
        assert len(km) == len(qs)

    def test_order_is_shuffled_but_deterministic(self, tmp_path):
        qs = self._queries()
        la.write_blind_kit(qs, tmp_path / "a", seed=42)
        la.write_blind_kit(qs, tmp_path / "b", seed=42)
        ids = lambda p: [r["item_id"] for r in csv.DictReader(          # noqa: E731
            (p / "labels_blind.csv").open(encoding="utf-8-sig"))]
        assert ids(tmp_path / "a") == ids(tmp_path / "b")

        km = json.loads((tmp_path / "a/_keymap.json").read_text(encoding="utf-8"))
        assert [km[i] for i in ids(tmp_path / "a")] != [q["query_id"] for q in qs]

    def test_clip_command_covers_gt_with_padding(self):
        cmd = la.clip_cmd(Path("v.mp4"), 100.0, 110.0, Path("out.mp4"), pad=2.0)
        assert "-ss" in cmd and "98.0" in cmd
        assert "-t" in cmd and "14.0" in cmd

    def test_clip_padding_never_goes_negative(self):
        cmd = la.clip_cmd(Path("v.mp4"), 1.0, 6.0, Path("out.mp4"), pad=2.0)
        assert "0.0" in cmd and "-98.0" not in cmd


class TestScore:
    def test_score_joins_on_keymap(self, tmp_path):
        gold = [{"query_id": "a", "type": "자막형"}, {"query_id": "b", "type": "장면형"}]
        (tmp_path / "_keymap.json").write_text(
            json.dumps({"i01": "b", "i02": "a"}, ensure_ascii=False), encoding="utf-8")
        with (tmp_path / "filled.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, ["item_id", "질의문", "유형"])
            w.writeheader()
            w.writerow({"item_id": "i01", "질의문": "-", "유형": "장면형"})
            w.writerow({"item_id": "i02", "질의문": "-", "유형": "복합형"})
        rep = la.score(gold, tmp_path / "_keymap.json", tmp_path / "filled.csv", CATS)
        assert rep["n"] == 2
        assert rep["percent_agreement"] == pytest.approx(0.5)
        assert rep["disagreements"][0]["query_id"] == "a"

    def test_missing_label_raises(self, tmp_path):
        gold = [{"query_id": "a", "type": "자막형"}]
        (tmp_path / "_keymap.json").write_text(
            json.dumps({"i01": "a"}, ensure_ascii=False), encoding="utf-8")
        with (tmp_path / "filled.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, ["item_id", "질의문", "유형"])
            w.writeheader()
            w.writerow({"item_id": "i01", "질의문": "-", "유형": ""})
        with pytest.raises(ValueError, match="미기입"):
            la.score(gold, tmp_path / "_keymap.json", tmp_path / "filled.csv", CATS)
