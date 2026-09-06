# Phase A — VAD sidecar 계측 결과 (2026-09-06)

트랙: `STT_EVIDENCE_SANITATION_V1` · 사전등록
`docs/preregistration/STT_EVIDENCE_SANITATION_V1_2026-09-06.md`

```
실행 범위   제출 영상 40.4분 전체 + 대조군 3편
재전사      없음        판정 변경 없음        텍스트 수정 없음
θ 선정      하지 않았다  claim eligibility 변경 없음
제출 산출물  무변경 (HWPX sha256 f874f643… · tag submission-ready-2026-09-03)
```

## 1. 재현 정보 (freeze 대상)

```
code_revision            621a252d3cbc7f1f0834e2191cb30c394fdfcf7d
faster_whisper_version   1.2.1
vad_model                silero_vad_v6.onnx
vad_model_sha256         4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2
sampling_rate            16000

threshold                0.5
neg_threshold            0.35        ← 기본 None의 resolved value: max(0.5-0.15, 0.01)
min_speech_duration_ms   0
max_speech_duration_s    inf
min_silence_duration_ms  2000
speech_pad_ms            400

audio_sha256             38ec13cfc31eee22eb217136caa2abdf7c597d6380c6f447a2c05c5476867647
segments_sha256          aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
stt_cache_sha256         59c98df1e0ea18e93623074a538b63b91794a8fca686e68a345c85dfc1c1a90d
```

**이 값을 characterization 이후에 바꾸면 그것도 threshold tuning이다.** 바꾸려면 사유를
freeze 문서에 적고 전 구간을 다시 잰다.

지표 정의는 코드와 테스트로 고정했다(`scripts/stt_vad_sidecar.py` ·
`tests/test_stt_vad_sidecar.py` 23건).

```
speech_overlap_ratio    |ASR구간 ∩ ∪(VAD speech)| / |ASR구간|
nearest_speech_gap_sec  overlap > 0 → 0 · 아니면 가장 가까운 speech까지 거리
                        speech가 하나도 없으면 None (거리를 지어내지 않는다)
```

VAD 구간은 **padding(400 ms)까지 적용된 최종 구간**이다. 합집합으로 세므로 맞닿은
구간을 이중으로 세지 않는다.

## 2. 제출 영상 — 현행 usable STT 294구간 분포

```
speech_overlap_ratio          gap (겹치지 않을 때 가장 가까운 speech까지)
0            210  (71.4%)     0            84
(0, .25]      13              (0, .25]      1
(.25, .50]    14              (.25, .50]    2
(.50, .75]    14              (.50, 1.0]    2
(.75, 1.0]    43              > 1.0        205
                              speech 없음    0
```

발화(utterance) 층도 같은 방향이다.

```
발화 437 중 overlap 0        336 (76.9%)
그 발화들의 총 길이            480.5초 / 전체 발화 736.4초
VAD가 speech로 본 총 길이     289.2초 = 오디오 2,424초의 11.9% · chunk 39개
```

## 3. 대조군 — VAD false negative인지 가른다

같은 코드·같은 파라미터로 발화가 분명한 영상 3편을 함께 쟀다. **이 대조군은 사전등록
§5의 층 구분을 영상 단위로 대신한 것이며, 판정 입력이 아니라 해석용이다.**

```
영상                      길이     VAD speech 비율   chunk   발화 overlap 0    구간 overlap 0
full_xekZO4n4QuE (제출)   40.4분   11.9%             39      76.9%            71.4%
wonyi_geoje              27.2분   83.2%             71       5.4%             3.2%
kbs_banff                26.3분   53.8%             81       6.2%             6.7%
itsub_viral_gadgets      15.9분   97.6%             10       0.0%             0.0%
```

대조군에서 overlap 0은 0~6.7%다. 같은 설정에서 제출 영상만 71.4%다. 따라서 이 tail을
**VAD 설정이 전반적으로 speech를 못 잡아서 생긴 것으로 설명하기 어렵다.**

그래도 `overlap == 0`을 환각이라고 부르지 않는다. 정확한 이름은 이것이다.

```
low/no-VAD-speech STT
```

VAD false negative·시간 정렬 오차가 이 안에 얼마나 섞여 있는지는 Phase A만으로
가릴 수 없다.

## 4. diagnostic cross-tab — 규칙 입력이 아니다

```
overlap bucket   라틴 포함   반복 2회 이상
0                    14           39
(0, .25]              1            2
(.25, .50]            0            0
(.50, .75]            1            2
(.75, 1.0]            0            0
```

```
라틴 포함 usable 구간 16 → 그중 14가 overlap 0
반복 3회 이상 usable 구간 25 → 25 전부 overlap 0
```

텍스트 이상 신호와 음향 신호가 같은 구간을 가리킨다. **그래도 규칙에 라틴·반복 조건을
넣지 않는다** — 실제 반복 발화를 지운 2026-08-29 사고가 그 경로에서 났다. 두 신호가
겹친다는 것은 음향 신호만으로도 충분할 수 있다는 근거로만 쓴다.

## 5. Phase B를 열 근거가 생겼는가

사전등록 §10의 판단 기준은 "현재 usable STT 중 VAD가 speech를 거의/전혀 찾지 못한
비율이 실제로 큰가"였다.

```
210 / 294 = 71.4%   (구간)
336 / 437 = 76.9%   (발화)
```

tail이 작지 않다. `VAD AND no_speech_prob` 형태의 후보를 계속 검토할 근거가 된다.
다만 **Phase A만으로는 임계값을 정할 수 없다** — 두 번째 축(no_speech_prob ·
avg_logprob · compression_ratio)이 아직 없다. 그 값들은 `stt_cache.json`에 저장돼
있지 않으므로 격리 namespace에서 같은 파라미터로 다시 돌려야 얻는다.

## 6. 이 결과가 주장하지 않는 것

```
환각이 210구간이다              아니다 — low/no-VAD-speech STT가 210구간이다
VAD가 정답이다                  아니다 — false negative를 Phase A로 가릴 수 없다
θ 후보를 골랐다                 고르지 않았다
현재 보고서가 잘못됐다           이 문서는 그 판단을 하지 않는다
```

## 7. 산출물

```
runs/stt_sanitation_v1/full_xekZO4n4QuE/{manifest,measurements,distribution}.json
runs/stt_sanitation_v1/control_{wonyi_geoje,kbs_banff,itsub_viral_gadgets}/…
scripts/stt_vad_sidecar.py            읽기 전용 계측기
tests/test_stt_vad_sidecar.py         23건 (지표 정의·경계·측정 표·분포·비변경 보증)
```

다음 관문은 사전등록 §9의 4단계 — Phase B 3분 canary이며, **별도 승인 사건**이다.
