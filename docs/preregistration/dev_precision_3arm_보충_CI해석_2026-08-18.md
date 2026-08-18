# dev 정밀도 3-arm — 보충: CI 해석 한계와 quadrant 라벨 (2026-08-18)

본 사전등록 `dev_precision_3arm_사전등록_2026-08-18.md`에 대한 보충이다.
**본문을 고치지 않고 여기에 추가한다.** 이 문서도 결과를 본 뒤 고치지 않는다.

## 1. cluster = 3 — CI는 진단용이다

dev는 **영상 3편**뿐이다. `paired video-cluster bootstrap CI`의 클러스터 수가 3이라
**추론적으로 매우 거친 구간**이 나온다. 계산은 하되 해석을 제한한다.

> `paired video-cluster bootstrap CI`를 보고하되, **cluster=3이므로 불확실성
> 진단용으로만 해석한다.** CI의 0 포함·배제 여부를 **formal adoption gate로
> 사용하지 않는다.**

이는 본문 §3의 "임의의 `δ`를 formal gate로 쓰지 않는다"와 같은 취지다 —
**dev 96·영상 3편에서 얻는 것은 방향과 크기의 감각이고, 확증은 장벽 1번(새 표본)이
따로 담당한다.**

## 2. quadrant는 **기술적 라벨**이다 — 의미를 자동 부여하지 않는다

```
Δ_quant  < 0  /  ≥ 0
Δ_deploy > 0  /  ≤ 0
```

출력 라벨은 부호 조합을 **기술**하는 문자열만 쓴다.

```
quant_loss_and_deploy_gain
quant_loss_and_no_deploy_gain
no_quant_loss_and_deploy_gain
no_quant_loss_and_no_deploy_gain
```

**`good`·`bad`·`equivalent`·`significant` 같은 평가어를 코드가 붙이지 않는다.**
CI가 0을 가로지르면 그대로 보여준다. **판단은 코드가 대신하지 않는다.**

## 3. VRAM 키 이름 — 6GB 적합성으로 오독되지 않게

peak VRAM은 **서버 4090에서 측정한 값**이다. 산출 키를 `server_peak_vram_*`로 둔다.
`peak_vram_gb` 같은 중립적 이름은 나중에 6GB 노트북 적합성 수치로 오독될 수 있다.
본문 §5의 "서버 4bit 성공은 6GB 적합성 증명이 아니다"를 키 이름으로도 강제한다.

## 4. fail-closed 검증 — 결과 산출 전에 막는다

paired 분석은 세 arm의 질의 집합이 **완전히 같아야** 성립한다. 다음은 결과를 내지
않고 거부한다.

```
세 arm 중 하나라도 질의 누락
질의 중복
질의 순서·집합 mismatch
arm별 aggregate MRR ≠ 저장된 per-query RR 평균
```

bootstrap `seed`·resample 수·CI method를 산출물에 기록한다.
