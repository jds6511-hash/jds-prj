"""소스 스캔 helper 자체 검증 — 산문은 지나가고 코드는 걸려야 한다."""
from v2_1_scan import code_only


def test_prose_is_ignored(tmp_path):
    path = tmp_path / "good.py"
    path.write_text('"' * 3 + "work/ 이야기." + '"' * 3 + "\nx = 1\n", encoding="utf-8")
    assert "work/" not in code_only(path)


def test_comments_are_ignored(tmp_path):
    path = tmp_path / "commented.py"
    path.write_text("# work/segments.json 을 읽지 않는다\nx = 1\n", encoding="utf-8")
    assert "work/" not in code_only(path)


def test_real_code_is_caught(tmp_path):
    path = tmp_path / "bad.py"
    path.write_text('p = "work/segments.json"\n', encoding="utf-8")
    assert "work/" in code_only(path)


def test_inline_string_is_caught(tmp_path):
    """docstring이 아닌 문자열 리터럴은 코드다."""
    path = tmp_path / "inline.py"
    path.write_text('x = 1\ny = "SUSPECT"\n', encoding="utf-8")
    assert "SUSPECT" in code_only(path)
