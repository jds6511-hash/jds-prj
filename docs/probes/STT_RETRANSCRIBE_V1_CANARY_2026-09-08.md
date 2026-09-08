# STT_RETRANSCRIBE_V1 canary 결과 (2026-09-08 · 600–780초 × 2회)

사전등록: `docs/preregistration/STT_RETRANSCRIBE_V1_2026-09-08.md` (commit 1d36bad)

```
FULL_RETRANSCRIPTION            HOLD 유지
CANARY_DETERMINISM              평가 불가 — 두 실행이 모두 빈 전사였다
게이트 C1~C8                     정의대로는 전부 true, 그러나 **공허한 통과**다
```

## 1. 무슨 일이 났나

`vad_filter=True` + Phase A freeze VAD 파라미터로 이 3분 클립을 돌리면
**전사가 0발화**로 나온다.

```
오디오                            180.0초
frozen VAD가 찾은 발화             1.68초 (speech chunk 1개 · 178.32–180.00초)
duration_after_vad                1.68초
새 전사 발화 수                    0
기존(현행 설정) 전사 발화 수         26
```

VAD가 오디오의 **0.93%만 발화로 판정**했고, 디코더에는 그 1.68초만 들어갔다.
그 1.68초에서도 출력이 나오지 않았다.

## 2. 게이트가 공허하게 통과했다

행이 0개면 대부분의 검사가 자동으로 통과한다. 숨기지 않고 적는다.

```
C2 determinism      run1 == run2 (ordered digest 4f53cda1… 동일)
                    그러나 **둘 다 빈 전사**다 — 재현성을 판정한 것이 아니다
C3 temperature      관측값 [] (행이 없어 관측 자체가 없다)
C5 lineage          0행 → 0행
C6 timestamp        0행 → 위반 0
C8 canonical mapping 원 실행에서 0행이었다 — 계측 결함(아래 §5)
C1 provenance       실질 통과 (decoding·VAD resolved 값 기록됨)
C7 old artifacts    실질 통과 (감시 6개 해시 무변경)
```

따라서 **사전등록의 첫 질문(run1 == run2)은 답을 얻지 못했다.** 빈 전사 두 개가
같다는 사실은 temperature 고정의 효과를 증명하지 못한다.

## 3. 겹쳤던 3발화도 출력되지 않았다 (원인 미분리 · 2026-09-08 정정)

기존 전사 26발화 중 VAD 발화 구간과 겹치는 것은 3건이고, 전부 자연스러운 한국어
대화다. 새 전사에서는 **이 3건도 출력되지 않았다.**

```
177.54–178.54  샘플 두께 이정도니까
178.54–178.92  아 네
178.92–179.98  앉아보시고 그러시면 됩니다
```

나머지 23건은 조리 지시문 형태다(`오븐에 2분간 구워주세요`, `크림치즈를 넣어주세요`
중복, `parmesan`, `깨`, `달걀` 등). GT가 없으므로 이것이 환각이라고 판정하지 않는다.

**정확한 표현은 이것뿐이다.**

```
Three utterances from the previous transcript that overlapped the frozen VAD
speech regions were not emitted by the VAD-constrained decoding run.
```

`VAD가 실제 발화를 잘랐다` · `false-negative가 실현됐다`고 쓰지 않는다 —
VAD는 1.68초를 **남겼고**, 그 오디오는 디코더에 들어갔다. 그런데도 출력이 0이다.
따라서 원인은 아직 분리되지 않았다.

```
A  Silero가 speech를 너무 적게 검출했다
B  chunk가 남았지만 너무 짧고 단절돼 디코더가 아무 token도 만들지 않았다
C  Whisper의 no_speech·log-prob 판정이 남은 chunk를 최종적으로 억제했다
```

`no_speech_threshold`는 log-probability 조건과 함께 segment를 silence로 판정하는
**별도 단계**다. 즉 VAD가 오디오를 남겨도 디코더가 텍스트를 내지 않을 수 있다.
이 셋을 가르는 것이 다음 사건이다(`STT_RETRANSCRIBE_DIAGNOSTIC_V1B`).

## 4. 해석 — GT 없이 가를 수 없다

```
해석 A   이 구간에 발화가 거의 없고, 기존 26발화 대부분이 무발화 생성이다
해석 B   발화가 있는데 frozen VAD 파라미터가 이 오디오에 엄격하다
해석 C   VAD 판정과 무관하게 디코더 쪽 억제가 출력 0을 만들었다
```

**어느 것도 지금 확정되지 않았다.** 그래서 `VAD hypothesis`는 기각되지 않았고,
`VAD decode-time adoption`도 승인되지 않았다.

Phase A의 전체 영상 측정(사용 가능 STT 294 중 210이 zero-overlap)과 방향은 같지만,
어느 해석이 맞는지는 **여기서 가릴 수 없다.**

## 5. 계측 결함 하나 (보정)

C8은 요청 범위(600–780초 절대 시간)로 클립 `segments.json`(0–180초 상대 시간)을
필터해 **0행**이 됐다. 0행은 통과가 아니다.

```
보정          runs/stt_retranscribe_v1/canary_600_780_mapping_correction.json
방법          재전사 없이 오프라인 재계산
결과          36행 · segment_id 0–35 · 5초 격자 경계 무변경
코드 수정      segments_range()로 segments 자체 시간 기준을 쓰게 했고,
              0행이면 C8이 통과하지 않도록 막았다 (테스트 1건 추가)
실행 코드      ef8c148f4b9bfc77… (이 canary가 돌린 파일)
보정 코드      cfe9932c3720…     (계측 수정 후)
```

## 6. 사전등록의 결함

사전등록에 **비퇴화(non-degeneracy) 전제조건이 없었다.** "run1 == run2"만 요구했고,
"전사가 비어 있지 않아야 한다"를 넣지 않았다. 그래서 가장 나쁜 결과가 형식상
전부 PASS로 보인다.

이 조건을 지금 추가해 재판정하지 않는다 — 결과를 본 뒤 게이트를 고치는 것이다.
**새 사전등록 사건으로 남긴다.**

## 7. 판정

```
이번 canary                CLOSED / INCONCLUSIVE-DEGENERATE — 그대로 동결한다
                          acceptance evidence로 재활용하지 않는다
VAD hypothesis            NOT REJECTED
VAD decode-time adoption  NOT APPROVED
temperature=0 determinism NOT ESTABLISHED
FULL_RETRANSCRIPTION      HOLD 유지
threshold 조정으로 살리기   하지 않는다 (사전등록 §6)
```

정확한 진단은 이것이다 — **sidecar에서 유효했던 VAD를 decode-time gate로 옮겼을 때
거의 모든 오디오가 사라지고, 남은 짧은 speech chunk조차 출력되지 않는 메커니즘을
아직 분리하지 못했다.**

허용 문구는 이것뿐이다.

```
At the frozen Phase-A VAD parameters, VAD-constrained decoding produced no
transcript for this canary interval; the run-to-run comparison is therefore
degenerate and does not establish determinism.
```

쓰지 않는 문구:

```
VAD-constrained deterministic decoding reduced transcription emitted outside
the frozen VAD speech regions.       ← 결과가 지지하지 않는다 (전사가 0이다)
hallucination이 줄었다 · ASR이 정확해졌다 · 무발화가 확인됐다
```

## 8. 다음 단계 — threshold 조정보다 mechanism 분리가 먼저다

```
STT_RETRANSCRIBE_DIAGNOSTIC_V1B    파라미터는 이번 것 그대로. 아무것도 튜닝하지 않는다
  D1  남은 1.68초에 무슨 일이 났는지 추적
      Silero chunk 경계·길이 · duration before/after VAD
      no_speech_prob · avg_logprob · compression_ratio
      **token을 안 만들었는가 vs 만든 뒤 억제됐는가**를 가른다
  D2  그 1.68초 오디오만 잘라 vad_filter=False로 디코드
      0이면 VAD threshold만의 문제가 아니다 (fragment 디코딩 상호작용)
      텍스트가 나오면 VAD 통합·chunk 조립·후단 필터 경로를 본다
  D3  비퇴화 canary 구간을 **frozen Phase-A 측정만으로** 결정적으로 고른다
      180초 bin별 VAD speech duration argmax · 동률은 이른 bin
      transcript 내용은 선택에 쓰지 않는다
  판정 조건  양 run이 non-empty일 때만 exact parity로 determinism을 판정한다
```

## 9. 산출물

```
runs/stt_retranscribe_v1/canary_600_780.json                    2회 실행 결과·게이트
runs/stt_retranscribe_v1/canary_600_780_mapping_correction.json C8 보정(재전사 없음)
work_sttv2/canary_run1/transcript.json · canary_run2/transcript.json
scripts/stt_retranscribe_canary.py · tests/test_stt_retranscribe_canary.py (23건)
```

기존 산출물 무변경 확인(감시 6개): 기존 stt_cache 2종 · 클립 segments · 전체
segments · 현행 제출본 hwpx · rollback hwpx.
