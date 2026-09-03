# A2' — 순수 Python OWPML HWPX 경로 결과 (2026-09-03)

```
승인 범위   scripts/v2_1_hwpx_owpml.py 신규만
            src/v2_1_render_hwpx.py 수정 0 · Node/npm·kordoc·한글 COM 런타임 의존 0
판정        A2-01 ~ A2-15 PASS · A2-16은 진단으로 기록(§4)
```

```
normative source      한컴 공개 OWPML 설명 (content.hpf = 패키지 manifest/spine,
                      header.xml = 글자·문단 모양, section이 header를 참조)
compatibility oracle  한글이 저장한 실제 HWPX (구조 대조용)
differential oracle   kordoc (MIT · Node) — **개발 시 대조에만** 쓴다
implementation        이 저장소의 Python 생성기 (XML은 독립 작성)
```

kordoc의 코드·템플릿을 옮기지 않았다. 파트 구성과 참조 그래프라는 **구조적 관찰**만
참고했고, XML은 직접 작성했다.

---

## 1. 만드는 것 — 최소 패키지

```
mimetype                 application/hwp+zip · STORED · 첫 항목
META-INF/container.xml   rootfile → Contents/content.hpf
Contents/content.hpf     manifest(header · section0) + spine
Contents/header.xml      fontface 2 · charPr 3 · paraPr 1 · borderFill 1 · style 1
Contents/section0.xml    문단 · 첫 run이 secPr(A4·여백)를 든다
Preview/PrvText.txt      진단·호환용 평문
```

version.xml · settings.xml · META-INF/manifest.xml · container.rdf · 미리보기 이미지는
**만들지 않는다.** 파트 개수를 한글 저장본(11개)에 맞추는 것이 목적이 아니라 참조
그래프가 닫힌 최소 문서를 만드는 것이 목적이다. 실측으로 그것만으로 열린다.

charPr는 `_lines()`를 표현하는 데 필요한 셋뿐이다.

```
0  본문 10pt        함초롬바탕
1  절 제목 13pt 굵게  함초롬바탕
2  박스 9.5pt        굴림체(고정폭) — 문자 박스 열을 맞춘다
```

## 2. 3중 교차 검증

```
Python structural validator   PASS   자기 subset의 invariant만 검사 (§3)
kordoc parser                 PASS   독립 구현이 패키지를 읽었다
한글 COM Open()                PASS   + PDF export 성공
```

```
kordoc 추출 문장 27줄  ==  우리 semantic_text 27줄   완전일치
산출물 크기            4,331 B   (한글 COM 저장본 36,903 B의 1/8)
```

## 3. A2-01 ~ A2-15

```
A2-01  zip testzip                     PASS
A2-02  mimetype 내용 + STORED + 첫 항목   PASS
A2-03  XML 전부 well-formed             PASS
A2-04  container rootfile 존재          PASS
A2-05  content.hpf manifest href 존재    PASS
A2-06  spine idref ⊆ manifest id        PASS
A2-07  section의 charPr/paraPr/style ref ⊆ header id   PASS
A2-08  `_lines()` 문장 정확 보존          PASS   문서 문장 == _lines() (빈 줄 제외)
A2-09  새 semantic text 0               PASS   문장 집합 ⊆ _lines() 집합
A2-10  sparse "남성이 문을 연다." 보존     PASS   건물·훔친·달아난다 0건
A2-11  kordoc parse 성공                 PASS
A2-12  kordoc 추출 text == 기대 문장       PASS   27/27 완전일치
A2-13  한글 COM Open() == True           PASS
A2-14  PDF export                       PASS
A2-15  ■ · « » glyph integrity          PASS   깨짐 0 · A1 산출물과 같은 모양
```

계약 테스트 `tests/test_v2_1_hwpx_owpml.py` 17건은 **한글 없이** 돈다.

## 4. A2-16 box alignment — 진단 (P0 아님)

```
세로선 열     일정하다 (박스 줄만 고정폭 + 왼쪽정렬)
남은 어긋남   ① 위/아래 가로선과 세로선 열이 정확히 맞지 않는다
             ② 긴 요약이 wrap되면 이어지는 줄에 `│`가 없어 테두리가 끊긴다
원인         frozen `_lines()`가 박스를 **문자로** 그린다 — 문자 박스는 wrap을 모른다
해결         표(table)·테두리 구조로 바꾸는 별도 presentation change가 필요하다
```

A1 산출물과 **같은 양상**이다. 렌더러 문제가 아니라 표현 형식 문제라는 뜻이다.

## 5. mutation

구조 mutation은 **한글을 켜기 전에** validator가 잡는다.

```
M1  content.hpf 제거                     RED   (validator)
M2  container rootfile을 없는 경로로       RED   (validator)
M3  spine idref를 없는 id로               RED   (validator · "spine" 사유)
M4  section charPrIDRef dangling         RED   (validator · 속성명 포함 사유)
M5  section paraPrIDRef dangling         RED   (validator)
M6  `_lines()` 한 줄 삭제                 구조 PASS · **문장 대조가 RED**
M7  sparse 문장을 발명 문장으로 치환         구조 PASS · **문장 대조가 RED**
```

M6·M7이 구조 검사를 통과하는 것은 설계대로다 — 참조 그래프는 멀쩡한데 내용만 바뀐
경우이고, 그 자리는 문장 대조가 맡는다. 둘을 한 검사로 합치지 않는다.

## 6. A1과의 관계

```
A1   scripts/v2_1_hwpx_via_hangul.py   한글 COM · Windows 전용   호환성 기준
A2'  scripts/v2_1_hwpx_owpml.py        순수 Python · 서버·CI 가능  portable
```

둘 다 남긴다. 문장은 같은 frozen `_lines()`에서 나오고, 두 경로의 semantic text가
같은지 differential test로 잰다. 하나가 어긋나면 어느 쪽 문제인지 갈린다.

## 7. 이 결과가 주장하지 않는 것

```
src/v2_1_render_hwpx.py가 고쳐졌다      아니다 — 결함은 역사적 사실로 남는다
OWPML 전체를 구현했다                   아니다 — 최소 subset이다
OWPML validator를 만들었다              아니다 — 자기 subset의 invariant만 본다
박스 정렬이 해결됐다                     아니다 — §4
kordoc이 정답 기준이다                   아니다 — 독립 대조 oracle이다
acceptance 판정이 바뀐다                 아니다 — baseline 6e79ac3 유지
```
