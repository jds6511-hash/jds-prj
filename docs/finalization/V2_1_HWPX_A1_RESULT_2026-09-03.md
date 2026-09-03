# A1 — 한글 COM HWPX 경로 결과 (2026-09-03)

```
승인 범위   scripts/v2_1_hwpx_via_hangul.py 신규만
            src/v2_1_render_hwpx.py · canonical · presentation/synthesis 수정 0
            문장은 frozen `_lines()`가 낸 것만 쓴다
판정        A1-1 ~ A1-8 PASS · A1-9는 둘로 나눠 기록한다(§3)
```

hand-built 렌더러의 결함은 그대로 남아 있다(보고서 §5 KNOWN OPERATIONAL DEFECT).
이 경로는 그 결함을 **우회**하는 제출용 경로이고, 결함을 고친 것이 아니다.

---

## 1. 계약

```
canonical + presentation + synthesis  →  _lines()  →  한글 COM  →  SaveAs HWPX (+PDF)

COM 없음        HwpxComError로 즉시 실패
                손으로 만든(열리지 않는) 패키지로 대체하지 않는다
정본            읽기 전용 — 파일 바이트도 in-memory 객체도 바뀌지 않는다
서식            제목·본문·박스 줄의 글꼴/크기/정렬만 바꾼다. 문장은 건드리지 않는다
PDF             렌더 검증용 진단물이다. 제출물 계약에 넣지 않는다
```

## 2. A1-1 ~ A1-8

```
A1-1  normal COM 저장            PASS   36,903 B · 11 파트 · 4.2초
A1-2  sparse COM 저장            PASS   29,110 B · 11 파트 · 2.7초
A1-3  한글 Open() == True         PASS   둘 다 · 저장 직후 재열기로 확인
A1-4  _lines() 순서 보존          PASS   writer가 받은 줄 == frozen _lines() 출력(동일 리스트)
A1-5  새 semantic text 0          PASS   기록된 줄 집합 ⊆ _lines() 집합
A1-6  sparse 문장 보존            PASS   "남성이 문을 연다." 유지 · 건물·훔친·달아난다 0건
A1-7  canonical mutation 0        PASS   파일 바이트 동일 · 로드된 dict 동일
A1-8  COM 부재 시 명시적 실패      PASS   HwpxComError · 산출물 미생성 · fallback 호출 0
```

계약 테스트: `tests/test_v2_1_hwpx_via_hangul.py` (11건, COM 없이 실행된다).
실 저장·열기·렌더는 한글이 있는 기계에서만 잴 수 있어 **조건부 skip으로 숨기지 않고**
별도 검증 스크립트가 산출물(HWPX·PDF·PNG)을 남기는 방식으로 확인했다.

## 3. A1-9 — 둘로 나눠 기록한다

```
glyph integrity   PASS
    ■ ┌ │ └ ─ « » 전부 정상 표시 · □ · � 0건
    저장된 section0.xml에도 원문 그대로 (en dash · « » 포함)
    cp949 TEXT 내보내기에서만 – → &#8211; · « → ≪ 로 바뀐다 — 문서 손상 아님

box alignment     PARTIAL
    개선됨   박스 줄만 고정폭(굴림체 9.5pt) + 왼쪽정렬로 두어 세로선 열이 일정해졌다
             (그 전에는 양쪽정렬로 단어 간격이 늘어나 열이 어긋났다)
    남음 ①   위/아래 가로선과 세로선 열이 정확히 맞지 않는다 (글리프 좌우 여백 차이)
    남음 ②   긴 요약 줄이 wrap되면 이어지는 줄에 `│`가 없어 박스 밖으로 나간다
```

남은 둘의 원인은 서식이 아니다.

```
frozen `_lines()`가 박스를 **문자로** 그린다 (┌ ─ │ └).
문자 박스는 wrap을 모른다 — 줄이 접히면 테두리가 끊긴다.
서식으로 줄일 수 있는 범위는 여기까지다.
```

고치려면 표현 계층에서 **문자 박스 대신 한글 표(table)** 를 쓰거나 `_lines()`의 박스
구성을 바꿔야 하고, 둘 다 frozen 모듈 수정이라 이 승인 범위 밖이다.

## 4. 산출물

```
c:\Users\UserK\Desktop\hwpx_check\
    v2_1_normal_com.hwpx   36,903 B    v2_1_normal_com.pdf   v2_1_normal_p1.png
    v2_1_sparse_com.hwpx   29,110 B    v2_1_sparse_com.pdf   v2_1_sparse_p1.png
    normal_canonical.json · sparse_canonical.json · a1_verify.json
```

sparse 표본은 TRI-005 C3가 실제로 작동한 문서다.

```
모델 출력   "남성이 문을 열고 건물에 들어가 물건을 옮긴 뒤 이동한다."
정본        "남성이 문을 연다."            summary_mode = SPARSE_EVIDENCE_DETERMINISTIC
문서        정본 문장만 실린다
```

## 5. 이 결과가 주장하지 않는 것

```
hand-built 렌더러가 고쳐졌다      아니다 — 결함은 그대로다
박스가 완전히 정렬된다            아니다 — §3 PARTIAL
한글 없는 기계에서도 만들어진다     아니다 — COM 없으면 실패한다
acceptance 판정이 바뀐다          아니다 — baseline 6e79ac3 유지
```
