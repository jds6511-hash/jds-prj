"""소스 스캔 helper — 산문이 아니라 코드만 본다.

여러 v2.1 테스트가 "이 모듈이 저 책임을 침범했는가"를 소스 문자열로 확인한다.
그런데 그 판단 근거를 설명한 **주석과 docstring 자체가 스캔에 걸린다.** A-10과
A-02에서 실제로 걸렸다. 그래서 비교 전에 주석·docstring을 떼어낸다.
"""
import tokenize


def code_only(path) -> str:
    """주석과 docstring을 뺀 코드 토큰만 이어 붙인다."""
    kept = []
    with open(path, "rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE):
                continue
            if token.type == tokenize.STRING:
                if token.line.strip().startswith(('"' * 3, "'" * 3)):
                    continue
            kept.append(token.string)
    return " ".join(kept)
