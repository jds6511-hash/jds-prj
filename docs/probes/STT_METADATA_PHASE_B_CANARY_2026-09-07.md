# Phase B canary — 600–780초 metadata 회수 결과 (2026-09-07)

트랙: `STT_EVIDENCE_SANITATION_V1` · 사전등록
`docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
B-C1 격리 namespace          PASS
B-C2 provenance 기록          PASS
B-C3 metadata 유한·비결측     PASS   41/41 · missing 0 · nonfinite 0
B-C4 raw→merged lineage      PASS   버려진 것까지 완결
B-C5 baseline transcript parity   FAIL   ← 아래 §2
B-C6 Phase-A join 완결        PASS
B-C7 기존 판정 무변경          PASS   확정 인덱스 해시 불변
B-C8 제출 산출물 무변경        PASS   HWPX sha f874f643…

PHASE_B_PAIRING = FAIL
Phase C (전체 40.4분) = HOLD           사전등록 규약대로다
새 metadata를 기존 294 evidence의 속성처럼 붙이지 않는다
```

## 1. 실행 환경 — 사고 1건과 그 수정

1차 실행이 1시간 무진행으로 멈췄다(GPU 5.4 GB 점유 · util 0% · CPU 23초).

```
원인   RuntimeError: Library cublas64_12.dll is not found or cannot be loaded
       모델 로드는 4.8초에 성공, 첫 encode에서 실패한 뒤 네이티브 계층에서 정지
수정   site-packages/nvidia/{cublas,cudnn}/bin을 os.add_dll_directory로 등록
       **환경 문제이므로 여기서만 고쳤다** — decoding 파라미터는 그대로다
기록   manifest.whisper.dll_directories_added · ladder_attempts
```

```
device/compute      cuda / float16
faster_whisper      1.2.1
decoding_resolved   large-v3 · ko · beam 5 · best_of 5 · word_timestamps true
                    condition_on_previous_text false · hallucination_silence_threshold 1.0
                    vad_filter false · temperature 미지정(라이브러리 기본 사다리)
audio_sha256        cc5d975b1740a68066110ce803b785bb09cab008dc4dcdb2ec1847fcb2b6afc3
code_revision       6624cb528d1df5a3c27d01873359e2f1083bad16
```

## 2. B-C5 FAIL — 같은 오디오가 매번 다른 전사를 낸다

```
baseline clip cache (2026-09-03 · 생산 경로)   26 발화
이번 실행 (2026-09-07 · 같은 파라미터)          41 발화
첫 불일치   baseline "오븐에 2분간 구워주세요"  ↔  이번 "파 provolone"
timestamp_max_abs_diff  89.48초
```

환경 차이 때문인지 확인하려고 **같은 환경에서 한 번 더** 돌렸다.

```
run1  41 발화   첫 6개: 파 provolone | 단팥 | 상추 | 깻잎 | 고추를 감사합니다 | 두부
run2  25 발화   첫 6개: 통깨 | 소금 | 소금과 후추 | 간장 | 소금과 후추 | 소금과 후추
동일 문자열 7개
```

즉 **환경 드리프트만으로 설명되지 않는다.** 같은 기계·같은 커밋·같은 파라미터에서도
연속 두 실행이 다르다.

세 번째 대조로, 같은 시간대를 **전체 오디오** 문맥에서 전사한 결과(2026-09-03 B1 본
실행)도 다르다.

```
600–780초 창    baseline clip 26 · full-audio 31 · 이번 clip 41 / 25
겹치는 내용      거의 없다
```

## 3. 왜 흔들리는가 — 온도 사다리가 개입한다

세그먼트별 `temperature`를 같이 회수했다.

```
run1  temperature 분포  {1.0: 20, 0.4: 12, 0.2: 3, 0.0: 6}   temp>0 35개
run2  temperature 분포  {1.0: 14, 0.0: 11}                    temp>0 14개
```

두 실행에서 **같게 나온 7개 문자열은 거의 전부 temperature 0.0** 구간이다.

```
t=172.7  temp 0.0  alp -0.44  nsp 0.219  안녕하세요
t=174.4  temp 0.0  alp -0.44  nsp 0.219  스테이크 띠즈도 있나요?
t=176.0  temp 0.0  alp -0.44  nsp 0.219  가격은 여기 있으니까 보시고
t=177.5  temp 0.0  alp -0.44  nsp 0.219  샘플 두께 이정도니까
t=179.5  temp 0.0  alp -0.44  nsp 0.219  앉아보시고 그러시면 됩니다
t=126.5  temp 0.2  alp -1.00  nsp 0.132  감사합니다.
```

기본 fallback 조건(`log_prob_threshold` −1.0 등)에 걸리면 Whisper는 온도를 올려
**샘플링**한다. 샘플링 구간은 실행마다 달라지고, 온도 0 구간은 재현된다.

이 관측은 2026-08-18의 "통제된 조건에서 결정적" 결과와 모순되지 않는다. 그 실험은
온도 0으로 끝나는 구간(AI Hub 발화)이었고, 여기는 fallback이 걸리는 구간이다.

## 4. 그래서 원래 Phase B/C 설계는 성립하지 않는다

Phase B의 전제는 "같은 전사를 다시 만들어 metadata만 회수한다"였다. 그 전제가 이
영상에서 깨졌다.

```
확정 인덱스의 전사는 특정 과거 실행의 산물이다
그 실행의 decoder metadata는 저장돼 있지 않다
재실행으로는 같은 전사가 나오지 않는다
→ 기존 294 evidence에 붙일 metadata를 재전사로 복원할 수 없다
```

## 5. 선택지 (고르지 않는다 — 승인 사건이다)

```
(i)   Phase A 신호만으로 간다
      VAD overlap·gap은 저장된 전사 구간에 대해 결정적으로 계산된다
      추가 GPU·재전사 불필요 · 확정 인덱스 무변경
(ii)  metadata를 구간 속성이 아니라 **영역 속성**으로 쓴다
      재전사 N회의 안정성(예: 반복 일치율)을 영역 신호로 삼는다 — 새 설계가 필요하다
(iii) 재전사로 인덱스를 교체한다
      확정 인덱스 재생성 = 별도 대형 승인 사건. 제출본 baseline과의 관계도 다시 정의해야 한다
```

## 6. 이 결과가 주장하지 않는 것

```
환각이 확정됐다              아니다 — GT가 없다. 재현되지 않는다는 관측이다
temperature > 0 = 환각       아니다 — 규칙 후보로 쓰려면 Phase D 사전등록이 필요하다
현재 보고서가 잘못됐다        이 문서는 그 판단을 하지 않는다
Phase C를 열어도 된다        아니다 — B-C5 FAIL이므로 HOLD다
```

## 7. 산출물

```
runs/stt_sanitation_v1/phase_b_canary/{manifest,lineage,joined,crosstab}.json
runs/stt_sanitation_v1/phase_b_canary_rep2/…            동일 환경 2회차
work_sttv1/canary_600_780{,_rep2}/raw_segments.json     temperature·words 포함 원본
scripts/stt_metadata_canary.py · tests/test_stt_metadata_canary.py (14건)
```

```
제출본        FROZEN · 무변경
Phase C       CANCELLED under current design   (2026-09-07 결정)
Phase D       기존 설계 폐기 — 전제(재전사 parity)가 반증됐다
후속          (i) 선택 · `docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`
             (ii) N-run stability = DEFER · research-only (`WhisperDecodeStability_v1`)
             (iii) transcript 교체 = HOLD
M9            HOLD · official test UNOPENED
```
