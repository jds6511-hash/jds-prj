# M8 redesign 종결 — 2026-08-28

```
M8 evaluation      COMPLETE
M8 acceptance      FAIL                       ← 확정. 소급 변경하지 않는다
M8 redesign        REDESIGN_ROUND_LIMIT_REACHED
ROUND 3            NO
후속 가설 H5~H7     future work (구현하지 않음)
M9                 HOLD — 별도 test-opening 결정 사항
official test      열지 않음
```

---

## 1. 왜 애매하지 않은가

동결 gate 6개 중 A·D만 통과했다. **수치가 조금 부족한 것이 아니라 회귀가 관찰됐다.**

```
A  unmatched GT < 22            22 → 10        PASS
B  unmatched generated <= 47    47 → 76        FAIL
C  C3 max <= 7.00             7.00 → 13.00     FAIL
D  median alignment > 0.3311  0.3311 → 0.4498  PASS
E  새 repetition_loop 0편          0 → 1편       FAIL
F  새 catastrophic 없음        C1 4 → 5편       FAIL
```

**회귀 증거 2건.**

```
jissi_farm      baseline에서 정상이던 편 (생성 11 · Compression 1.00)
                → 전역 고재현율 압력으로 후보 59까지 늘고 최종 생성 32 · Compression 2.91
repetition_loop baseline 0편 → 1편 (m8c2_cIxG7OHYMPU). V3 규칙 10으로도 막히지 않았다
```

즉 개선안이 **원래 문제가 없던 영상을 망가뜨렸다.** ROUND 2를 "거의 성공"으로 포장하지
않는다.

### 1-1. early_stop amendment를 당겨 판정을 살리지 않았다

ROUND 2의 `early_stop` 4편은 전부 분할로 회수된 청크이고, detector가
`chunk_splits` 회수를 모르는 **구현 결함**이다. 그 사실은 기록으로 유지한다
(`M8_C1_PROSPECTIVE_AMENDMENT_2026-08-27.md`).

**그러나 그것을 고쳐도 판정은 바뀌지 않는다.**

```
E  repetition_loop 1편          amendment와 무관한 새 파국          → FAIL 유지
F  새 catastrophic 없음         E 때문에 여전히                     → FAIL 유지
B  unmatched generated 76      amendment와 무관                    → FAIL 유지
C  C3 max 13.00                amendment와 무관                    → FAIL 유지
```

공식 C1 판정(4/8)도 소급 변경하지 않는다.

---

## 2. 후속 가설을 future work로 보내는 이유

```
H5  영상 전체 후보에 2차 수렴을 한 번 더 적용
H6  고재현율을 전역이 아니라 **짧은 사건이 실제로 누락된 구간에만** 선택 적용
H7  반복 생성을 프롬프트가 아니라 생성 파라미터(no_repeat_ngram 등)로 억제
```

**세 가설 모두 이번 결과를 보고 고안됐다.** 그 사실을 숨기지 않는다 —
outcome-informed 가설이므로 같은 표본으로 검증할 수 없다.

그리고 셋 다 "두 라운드의 후속 튜닝"이 아니라 **새 설계**다.

```
H5   새 파이프라인 단계가 하나 더 생긴다
H6   "어디에 고재현율을 적용할지" 정하는 새 detector/policy가 필요하다
H7   생성 정책 변경 — 결정성·재현성 전제가 다시 검토돼야 한다
```

각각 별도 사전등록과 fresh confirmation 경계를 요구한다. 남은 개발 라운드가
없으므로 구현하지 않는다.

**H3(출력 구조 2층화)도 future work다.** 긴 활동 안의 세부 단계를 표현할 자리가
현재 출력 형식에 없다는 진단은 유효하지만, 도입하면 `report.json` schema · M8 지표 ·
M9의 `sent_id`·`cites` 계약 · 최종 문서 렌더러까지 연쇄 변경이다.

---

## 3. M9 — HOLD. 세 확인 중 1·2가 이미 부정된다

`M9는 official test opening 사건`이고 test는 한 번 열면 되돌릴 수 없다.
"남은 파이프라인을 닫기 위해서"라는 이유로 자동 진행하지 않는다.

### 확인 ① 원래 M9 설계가 M8 PASS를 전제했는가

**명시된 전제 문장이 없고, 동시에 FAIL 상태 개방도 정의돼 있지 않다.**
이미 미결로 기록돼 있었다.

```
M8_M9_DECISIONS_2026-08-26 §미결
  "M9 개방 전제 — 'M8 acceptance FAIL이어도 M9를 여는가'는 기존 설계에 없다.
   D2-1이 두 상태를 분리했으므로 별도 결정 사항이다"

M8_M9_PROTOCOL_2026-08-26 §3
  "D1~D5가 정해지기 전에는 M8 freeze를 할 수 없고, freeze 없이는 M9를 열 수 없다"
  순서: M8 freeze → m9_dryrun --freeze PASS → test 개방 승인 → test 실행
```

`m8_freeze.py`는 실행하지 않았다. 그 도구는 통과한 M8을 닫기 위한 것이다.

### 확인 ② FAIL 산출물에 적용해도 사전 정의된 endpoint가 유효한가

**아니다. M9 acceptance 기준 자체가 없다.**

```
M8_M9_PROTOCOL §2  "④ M9 acceptance threshold 부재 — 저장소 전체에서 M9 PASS 기준을
                    찾지 못했다"
M8_M9_PROTOCOL §4  "기존 설계에 M9 PASS 기준이 없다. 아래는 제안이며 사용자 승인 후
                    동결한다"
D3                 "절차만 확정, 값은 미정" — dev judge validation → 후보 → 승인 → freeze
```

D3가 정한 절차의 1단계(dev judge validation)조차 실행되지 않았다. endpoint가 없는
상태에서 test를 열면 **무엇을 관찰하려는지 정의되지 않은 채 비가역 자원을 쓴다.**

### 확인 ③ official test를 소비할 만큼 그 질문이 중요한가

M9가 이 상태에서 얻을 수 있는 것은 제한적이다.

```
얻는 것   acceptance에 실패한 upstream 산출물을 downstream judge가 어떻게 평가하는지에
         대한 **진단적 관찰**
얻지 못하는 것
         M8 실패 상쇄 · 파이프라인 전체 유효성 증명 · candidate acceptance 소급 회복
```

①②가 부정되므로 ③을 논할 단계가 아니다. **M9는 HOLD로 둔다.**

M9를 열려면 먼저 (a) FAIL 상태 개방 여부를 결정하고 (b) 그 경우의 endpoint·해석
규칙을 동결해야 하며, 그것 자체가 amendment 사건이다.

---

## 4. 최종 보고서 문구

이번 결과를 기술할 때 쓸 문장을 여기에 고정한다.

> 두 차례의 사전 정의된 redesign round를 수행했으나 동결된 acceptance gate를
> 충족하지 못했다. ROUND 2의 consolidation은 ROUND 1에서 발생한 과분할을 상당 부분
> 줄이고 alignment를 개선했지만, 생성량과 최대 compression은 baseline 수준으로
> 회복되지 않았으며 baseline에서 정상적이던 일부 영상에서 새로운 회귀와 repetition
> failure가 발생했다. 따라서 candidate를 freeze하지 않고 redesign round limit에 따라
> M8을 acceptance FAIL로 종료했다. 후속 가설은 현재 결과에 의해 제안된 새로운
> 설계이므로 본 과정에서는 구현하지 않고 future work로 이관했다.

### 4-1. 쓰지 않을 문구

```
쓰지 않는다   "방향은 옳았고 크기가 부족했다"
             — 정상 영상을 망가뜨린 회귀가 있어 과소진술이다
대신          "consolidation은 ROUND 1의 일부 과분할을 완화했지만, acceptance에
              필요한 수준까지 안정적으로 수렴시키지는 못했다"
```

내부 진단 문서(`M8_REDESIGN_R1_RESULT`·`R2_RESULT`)의 표현은 그 시점 기록으로
남기고, **외부 보고 문구는 위 문장을 쓴다.**

---

## 5. 이 종결의 성격

```
기준을 움직이지 않았다        임계·통계량·지표·taxonomy 무변경
판정을 구하지 않았다          amendment 소급 적용 안 함
실패를 실패로 닫았다          evaluation COMPLETE · acceptance FAIL
가설의 출처를 밝혔다          H3·H5~H7은 결과를 보고 고안됐다고 명시
```

기준을 먼저 정해두고 실패했을 때 기준을 움직이지 않은 것이 이 과정의 결과물이다.
