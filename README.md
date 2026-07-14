# 영상 장면 검색 및 AAR 보고서 자동 생성 시스템

한국어 vlog 한 편을 업로드하고 자연어로 질의하면, 학습 없이(frozen 임베딩) **자막(말한 것)
+ 장면 캡션(보이는 것)**을 결합해 원하는 순간을 찾아주는 검색 시스템. 확장으로 질의 없이
영상 전체를 훑어 근거 인용([seg#N])이 달린 사후검토(AAR) 리포트를 자동 생성한다.

정대석 · KAIST 김주호 교수님 연구실

## 핵심 결과 (공식 test, n=39)

자막만 쓰는 baseline과, 자막+장면 캡션을 결합한 proposed를 동일 질의셋으로 비교했다.

| 지표 | baseline (자막만) | proposed (자막+캡션) | 비고 |
|---|---|---|---|
| MRR | 0.649 | **0.829** | 95% CI로 유의 |
| Hit@1 | 0.564 | **0.769** | 95% CI로 유의 |
| 장면형 질의 MRR | 0.174 | **0.718** | 무발화 장면 사각지대 최대 개선 |
| 자막형 질의 MRR | 0.958 | 0.880 | 소폭 하락(트레이드오프 명시) |

원본 확정 결과: [`results/eval_test.json`](results/eval_test.json)(test 평가),
[`results/alpha_search_dev.json`](results/alpha_search_dev.json)(dev α 탐색). 확정치 전체
요약표는 [`docs/DESIGN_SPEC.md`](docs/DESIGN_SPEC.md) §8-0 참조.

## 문서 읽는 순서 (진입점)

- **[docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md)** — 모듈별 API·데이터 스키마 계약(코드 수준
  명세). §8-0에 확정 상태 스냅샷 표, §8-1~8-7에 각 결정의 실측 근거.
- **[docs/DESIGN_SPEC_CHANGELOG.md](docs/DESIGN_SPEC_CHANGELOG.md)** — 확정치에 도달한
  날짜별 변천(문제 발견→처방→재개정).
- **[docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** — 선행연구 기반 설계
  근거(구현 착수 전 문헌 조사). 개정 배너로 최신 확정치와 정합.
- **[docs/presentation/](docs/presentation/)** — 중간발표 슬라이드(평이화 버전)와 예상질문
  방어 스크립트(Q1~Q15), 시연 런북.
- **[docs/오류분석_test_2026-07-13.md](docs/오류분석_test_2026-07-13.md)** — 확정 결과의
  사례 기반 정성 분석(왜 이겼는지/왜 졌는지).
- **[docs/probes/](docs/probes/)** — 모든 대안·ablation 탐색의 재현 가능한 스크립트
  (dev-only, 공식 결과 미접촉). 스크립트 상단 docstring에 목적·규율 준수 여부 명시.
- 최신 진행 상황: `docs/작업현황_*.md` 중 가장 최근 날짜 파일.

## 파이프라인 개요

```
M1 5초 분할+오디오 → M2 대표 프레임 선택 → M3 자막(Whisper)+캡션(Qwen2.5-VL) 생성
  → M4 임베딩(KURE-v1) → M5 정규화(z-score)+α 가중합 검색 → M6 평가(dev grid search→test)
  → M7 웹 UI 데모
(+ M8 AAR 리포트 생성 → M9 이중 평가(Coverage·Groundedness), 서버 GPU 대기)
```

## 실행

```bash
pip install -r requirements.txt
```

`data/videos/`(원본 mp4)와 `work/`(중간 산출물: 프레임·임베딩)는 대용량이라 저장소에서
제외했다(`.gitignore`). 직접 재현하려면 `data/videos/{video_id}.mp4`를 두고 순서대로:

```bash
python src/m1_preprocess.py --config config.yaml --video-id {video_id}
python src/m2_keyframe.py   --config config.yaml --video-id {video_id}
python src/m3_generate.py   --config config.yaml --video-id {video_id}
python src/m4_index.py      --config config.yaml --video-id {video_id}
python src/m5_search.py     --config config.yaml --video-id {video_id} --query "..."
```

평가(`results/eval_test.json` 재현, 확정 config는 이미 `config.yaml`에 고정):

```bash
python src/m6_evaluate.py --config config.yaml
```

웹 UI 데모:

```bash
python src/m7_webui.py --alpha 0.5 --port 7860
```

## 테스트

```bash
python -m pytest tests/ -q
```

## 방법론 규율 (요약)

- **test(n=39) 재평가 금지** — 확정 config로 공식 평가 완료(튜닝 접촉 0회, 확정 절차
  재평가 5회). 모든 튜닝·ablation은 dev(n=96)에서만.
- **캡션 수동 편집 금지** — 재생성은 자동 오염 판정분만.
- **라벨은 프레임 실물 검증** — 캡션·자막 텍스트를 보고 정답을 정하지 않는다.
- 상세: [CLAUDE.md](CLAUDE.md).

## 한계 (정직하게 명시)

n=39 소표본이라 hit@5/10은 95% CI가 0을 포함해 유의를 주장하지 않는다. 실사용 테스트에서
발견된 두 실패 모드(동의어 갭, 언급≠행위)와 처방은 방어 문서 Q13·
[오류분석 문서](docs/오류분석_test_2026-07-13.md)에 있다. M8/M9(AAR 리포트 생성·평가)는
설계·구현·단위테스트 완료 상태이며, 실전 구동은 서버 GPU 확보 대기 중이다(로컬 7B는
6GB 초과, 3B 하향은 예시 문장 복사 오염으로 기각 — 실측 확정).
