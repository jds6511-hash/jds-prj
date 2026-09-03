# B1 canary — 신규 YouTube 영상 3분 구간 M1~M3 실행 특성 (2026-09-03)

```
승인 범위   3분 고정 구간 canary만. 40.4분 전체 실행은 **미승인**
목적        execution characterization — 시간·산출물 상태 분포 측정
아님        성능 실험 · 프롬프트/threshold/모델 튜닝 · 재실행 루프
```

```
영상        https://www.youtube.com/watch?v=xekZO4n4QuE  (전체 2,424초 · 1920x1080)
구간        600 ~ 780초 고정 · clip 100,895,213 B
video_id    canary_xekZO4n4QuE_600_780
provenance  recorded · source_id "xekZO4n4QuE#600-780" · sha256 검증 통과
격리        config_canary.yaml(재생성) · work_canary/ · results_canary/
            본 인덱스·본 config 무변경
실행        scripts/canary_ingest_probe.py (git 등록) · 로컬 RTX 3060 Laptop 6GB
```

## 1. 시간

```
M1  전처리        0.5초
M2  키프레임      23.3초
M3  STT + 캡션   459.6초
합계             483.4초  (8분 3초)

40.4분 환산      1.81시간   (선형 외삽 · M3가 96%)
```

## 2. 산출물

```
segments        36 (5초 · duration 180.0)
subtitle 비어있지 않음   22 / 36
caption  비어있지 않음   36 / 36
caption 평균 길이        149.7자
오염 캡션(is_corrupted_caption)   0건
자막 크레딧 환각(is_subtitle_credit)  0건
실패·재시도                        0
```

## 3. 발견 — 튜닝하지 않고 기록만 한다

```
① STT 내용 불일치 의심
   영상은 자수 공장(EMBROIDERY FACTORY) 장면인데
   자막이 "오븐에 2분간 구워주세요" · "크림치즈를 넣어주세요"로 나온다.
   seg 0·1이 같은 문장으로 연속되는 것도 환각 패턴과 일치한다.
   현재 필터는 `한글자막 by …` 형태만 잡으므로 여기서는 0건이다.
   → 무발화·배경음 구간 환각 가능성. **이번 canary에서 조치하지 않는다.**

② 캡션이 화면 문자를 옮겨 적는다
   caption_prompt는 "화면 글자를 그대로 옮기지 말라"고 지시하는데
   실제 캡션은 'EMBROIDERY FACTORY' · 'ISTJ' 같은 화면 문자열을 인용한다.
   → 프롬프트 준수 실패. **프롬프트를 고치지 않는다**(고치면 튜닝 루프가 된다).

③ VRAM 미측정
   nvidia-smi를 각 단계 **종료 후**에 읽어 0 MiB만 남았다.
   peak VRAM은 측정하지 못했다 — 측정했다고 적지 않는다.
   전체 실행을 열 때 폴링 방식으로 다시 설계해야 한다.
```

## 4. 전체 실행(B1 full) 판단 근거

```
시간        1.81시간 예상 (M3 단일 지배)
OOM         canary 구간에서 발생 없음 · 다만 peak 미측정이라 여유폭은 미확인
캡션 실패율  0/36
차단 요인    없음 — 단, 위 ①②는 결과 해석에 영향을 준다
```

권고: 전체 실행 전에 **VRAM 폴링을 붙이고**, ①의 STT 환각이 전체 구간에서 어느
비율인지 먼저 세는 것이 낫다. 그 둘 다 튜닝이 아니라 측정이다.

## 5. 이 canary가 주장하지 않는 것

```
검색 성능        측정하지 않았다 (M4 이후를 돌리지 않았다)
캡션 품질 평가    상태 분포만 셌다
STT 정확도       ①은 관찰이지 정량 측정이 아니다
전체 실행 승인    별건이다
```
