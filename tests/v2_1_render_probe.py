"""렌더 산출물에서 의미만 뽑는 공용 probe (C-07 · C-08).

서식이 다른 두 문서를 대조하려면 **서식을 벗긴 뒤** 비교해야 한다. byte/text
동일은 목표가 아니다.

문서 전체에서 id가 한 번 보이는 것으로는 부족하다는 것을 C-06에서 겪었으므로
(종합 분석 절이 모든 id를 다시 적는다) **블록 단위**로 자른다.
"""
import re

from v2_1_render import LABELS


def _blocks(text):
    """highlight id로 블록을 가른다. 서식이 무엇이든 id 다음의 label 줄들이 블록이다.

    id는 문서에 여러 번 나온다(종합 분석 절이 다시 적는다). **첫 등장만** 블록의
    시작으로 보고, label이 없는 줄이 나오면 블록을 닫는다. 그래야 다른 절의 언급이
    블록에 섞여 들어오지 않는다.
    """
    blocks, current = {}, None
    for line in text.splitlines():
        found = re.search(r"\bH\d{2}\b", line)
        has_label = any(name in line for name in LABELS.values())
        if found and found.group(0) not in blocks and not has_label:
            current = found.group(0)
            blocks[current] = [line]
        elif current is not None:
            if has_label:
                blocks[current].append(line)
            elif blocks[current][1:]:
                current = None
    return {key: "\n".join(value) for key, value in blocks.items()}


def _projection(text):
    """서식을 벗기고 의미만 남긴다. 두 renderer를 이것으로 대조한다."""
    def value(source, key):
        found = re.search(r"%s\s*[:：]\s*(.+)" % LABELS[key], source)
        return found.group(1).strip() if found else None

    highlights = {
        key: (value(block, "time"), value(block, "summary"),
              tuple(sorted(set(re.findall(r"\bEP\d{2}\b", value(block, "sources")
                                          or "")))),
              value(block, "summary_sources"))
        for key, block in _blocks(text).items()
    }
    return {
        "highlights": highlights,
        "synthesis_sources": value(text, "synthesis_sources"),
        "limitation": value(text, "limitation"),
    }
