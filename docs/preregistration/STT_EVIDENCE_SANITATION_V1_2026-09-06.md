# STT_EVIDENCE_SANITATION_V1 — 사전등록 (2026-09-06)

```
트랙            post-v2.1 · 병렬 개선. 제출 산출물을 깨지 않는다
rollback point  tag submission-ready-2026-09-03  (FROZEN)
현재 report 재생성   HOLD
VAD로 즉시 재전사    HOLD
사람이 이상 문장 선별 삭제   금지
```

이 문서는 **내용을 고치지 않는 문서**다. 임계값은 characterization **뒤** 별도 freeze
문서에 적고, 그 뒤 한 번만 적용한다.

---

## 1. 문제 — 관찰은 충분하고 대응 신호는 미입증

제출 영상(`full_xekZO4n4QuE` · 40.4분 · 485구간)에서 무발화 구간에 문장이 나온다.
Whisper는 오디오만 보므로 화면 자막을 읽은 것이 아니라 **디코더 환각**이다.

```
발화 437 · 고유 300                     같은 문자열 반복 137
라틴/한자 혼입 발화 10건                 uxe Jonathan · Harteman · passionate으로 사랑합니다
연속 중복 구간 12 (4.1%)                 max_repeat_run_length 2
caption↔subtitle token Jaccard 0.001
```

**현행 sanitation(A-05)은 이것을 거의 걸러내지 못한다.** 같은 영상 ASR 채널 실측:

```
EMPTY 189 · VALID 294 · REJECTED 2 (overlay_or_url)
usable_for_claims 294
라틴 문자를 담은 구간 16건 → 그 16건 **전부** usable_for_claims = true
```

원인은 분명하다. 현행 규칙은 **텍스트 특징만** 본다(`_ECHO`·`_OVERLAY`·`_FOREIGN`
한자/가나·완전일치 반복 8회). 환각은 음향적 사건이므로 텍스트만으로는 실제 발화와
가르기 어렵다. `_FOREIGN`은 라틴을 보지 않고, 반복 규칙은 구간 병합 뒤 완전일치가
깨져 발동하지 않는다.

## 2. 가설

```
H-S1  무발화·저발화 구간에서 생성된 STT는 음향 신호(VAD 겹침 · no_speech_prob 등)로
      식별 가능하며, 그 신호는 텍스트 특징과 독립적이다.

H-S2  그 신호로 claim eligibility만 낮추면(원문 보존), 실제 발화 손실 없이
      저신뢰 STT가 요약 근거로 쓰이는 비율을 줄일 수 있다.
```

## 3. 하지 않는 것

```
raw transcript 삭제·수정          하지 않는다 (OPEN-7 · 삭제하지 않는다)
사람이 문장을 보고 고르는 판정      금지 (leakage)
내용 기반 첫 규칙                 금지 — 라틴 포함·특정 단어 반복으로 시작하지 않는다
                                 (2026-08-29 geoje: 캡션용 반복 규칙을 STT에 적용해
                                  실제 발화 11건 소실)
VAD를 Whisper 앞단 절단기로 사용    하지 않는다 — sidecar diagnostic으로만 쓴다
확정 인덱스(work/) 자막 재생성      하지 않는다
m3_generate·M1~M7 수정            하지 않는다 (동결)
work_full/ 산출물 수정             하지 않는다 — 실험은 격리 namespace에 쓴다
제출본 교체                        하지 않는다 (§9 조건 충족 전까지)
```

반복·언어 혼입은 **diagnostic feature로만 측정**한다. 판정 규칙에 넣지 않는다.

## 4. 계측 — 두 단계로 나눈다

### Phase A — VAD sidecar (GPU 불필요 · 재전사 없음)

```
입력   work_full/<vid>/audio.wav          읽기 전용
       work_full/<vid>/stt_cache.json     읽기 전용 (기존 437 발화)
도구   faster-whisper 1.2.1 번들 silero VAD · get_speech_timestamps
출력   runs/stt_sanitation_v1/<vid>/vad_sidecar.json

발화별   vad_overlap_sec · speech_overlap_ratio · nearest_speech_gap_sec
구간별   vad_speech_duration · vad_speech_ratio
```

원본 오디오를 자르지 않는다. VAD는 **측정만** 한다.

### Phase B — Whisper metadata 재기록 (GPU · 별도 승인 필요)

`stt_cache.json`은 `{text,t0,t1}`만 남긴다. 아래 값은 저장돼 있지 않으므로 같은
파라미터로 **격리 namespace에서** 다시 돌려야 얻는다.

```
avg_logprob · no_speech_prob · compression_ratio · language · language_probability
temperature · seek · (실험 arm 한정) word_timestamps
파라미터  large-v3 · ko · beam 5 · condition_on_previous_text=False
         hallucination_silence_threshold=1.0 · VAD 미사용   ← 현행과 동일
출력     work_sttv1/<vid>/  ·  runs/stt_sanitation_v1/<vid>/whisper_meta.json
```

```
순서   3분 canary → 검증 → 사용자 승인 → 40.4분 전체
금지   파라미터 튜닝 · 모델 교체 · VAD filter 켜기 (이 단계에서는 전부 금지)
```

Phase B 재전사가 기존 전사와 **텍스트 수준에서 일치하는지**를 같이 기록한다.
불일치하면 그 자체가 결과이며(2026-08-18 결정성 관측과 비교), 숨기지 않는다.

## 5. characterization — 층으로 나눠 분포를 본다

임계값을 정하기 전에 신호가 층을 가르는지부터 본다.

```
A  명백한 실제 발화 구간
B  음악·무음 중심 구간
C  요리 소음 중심 구간
D  현재 이상 문자열이 나온 구간 (라틴 혼입 16 · 반복 상위)
E  dialogue-heavy 구간
```

층 배정은 **음향·메타데이터로만** 한다. "이 문장이 이상해 보인다"로 층을 만들지 않는다.
D는 예외적으로 텍스트 기준이지만 **관측 대상**일 뿐 규칙 입력이 아니다.

```
보고   층별 speech_overlap_ratio · no_speech_prob · avg_logprob · compression_ratio 분포
      (n · median · p10 · p90 · 겹침 정도)
```

## 6. 규칙 후보 — 형태만 미리 고정한다

```
SUSPECT_STT_V1 :=  speech_overlap_ratio < θ_overlap
                   AND no_speech_prob   > θ_nospeech
```

```
임계값 θ    이 문서에 적지 않는다. characterization 뒤 별도 freeze 문서에 적고
           **한 번만** 40.4분 전체에 적용한다.
금지        표본을 보며 θ를 움직이는 것 — 그 순간 leakage다
형태 변경    AND를 OR로 바꾸거나 항을 추가하는 것도 freeze 문서에서 사유와 함께 한다
```

판정 결과는 기존 상태 어휘를 그대로 쓴다(A-05 재사용 · 새 어휘를 만들지 않는다).

```
VALID      preserved true  · usable_for_claims true
SUSPECT    preserved true  · usable_for_claims false     ← 이번 트랙이 늘리는 것
REJECTED   preserved true  · usable_for_claims false
```

첫 실험은 **SUSPECT까지만** 시험한다. REJECTED로 올리지 않는다.

## 7. 반드시 측정할 회귀 — 환각 감소보다 발화 손실이 중요하다

```
STT 총 구간 · VALID / SUSPECT / REJECTED / EMPTY 비율
eligible evidence 수 변화 (구간 단위 · episode 단위)
episode별 evidence-empty 전환 수        ← ERR-009 증가 여부
summary가 바뀐 episode 수
presentation eligibility 변화 (현재 39/41)
GEO-001 회귀 · GEO-004 회귀             매핑 테스트 실측 (source-level 추론 금지)
dialogue-heavy fixture 회귀
canonical partition 변화                0이어야 한다
raw transcript 보존                     100%
```

```
경계 사고   STT sanitation 적용 → eligible evidence 0 → PromptError(ERR-009) 증가
           이 경로를 반드시 센다
```

## 8. 성공 기준 — human GT가 없으므로 "환각 제거"로 두지 않는다

```
primary mechanism   저발화 STT가 claim evidence로 흘러가는 비율 감소
safety              알려진 실제 발화 fixture 손실 0
                    GEO 회귀 0
                    canonical partition 변화 0
                    raw transcript 보존 100%
```

결과 문구는 이것만 쓴다.

```
A deterministic abstention layer reduced the use of low-speech-confidence STT
as claim evidence.
```

```
쓰지 않는다   STT hallucination was eliminated
             전사 정확도가 향상됐다
             요약이 더 사실적이다
```

## 9. 순서와 관문

```
1  submission-ready-2026-09-03 유지                     완료 (tag · rollback point)
2  본 사전등록                                          이 문서
3  Phase A  VAD sidecar 계측 (CPU · 재전사 없음)
4  Phase B  Whisper metadata 재기록 (GPU · canary → 승인 → 전체)
5  characterization 층별 분포 보고
6  θ freeze 문서 (별도) → 사용자 승인
7  synthetic + GEO + dialogue-heavy 회귀
8  40.4분 전체 재평가 · 기존 submission과 비교
9  개선이 명확할 때만 새 submission candidate 생성      ← 그 전에는 제출본 교체 없음
```

## 10. 승인이 필요한 것

```
A  Phase A 실행 (로컬 CPU · 읽기 전용 입력 · 격리 출력)
B  Phase B 3분 canary (로컬 GPU · 격리 namespace)
C  Phase B 40.4분 전체 (canary 결과 확인 후 별도 승인)
D  θ freeze (characterization 뒤 별도 문서)
```

```
불변   submission arm = episode_content_v3_summary_only · HWPX sha256 f874f643…
      repository default contract = episode_content_v2
      v2.1 baseline 6e79ac3 · GRD-004 P1 WAIVED · M9 HOLD · official test UNOPENED
      검색 파이프라인 M1~M7 동결 · 확정 인덱스 자막 무변경
```
