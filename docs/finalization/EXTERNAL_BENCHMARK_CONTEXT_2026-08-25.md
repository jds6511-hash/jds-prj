# 외부 벤치마크 문헌 — contextual evidence (2026-08-25)

**adoption gate가 아니다.** 관련 연구 맥락으로만 정리한다. 이 절은 현재 3B/4B 결론을
바꾸지 않는다.

## 확인한 1차 근거 (2026-08-25 열람)

| 출처 | 확인 내용 |
|---|---|
| [Qwen2.5-VL-3B-Instruct 모델 카드](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) | 비디오 MVBench 67.0 · Video-MME 67.6/61.5 · MLVU 68.2 · LVBench 43.3 · TempCompass 64.4 · LongVideoBench 54.2 · Charades-STA mIoU 38.8 / 문서 DocVQA 93.9 · InfoVQA 77.1 · TextVQA 79.3 / 일반 MMBench-V1.1 77.6 · AI2D 81.5. 한국어 언급 없음 |
| [Qwen3-VL Technical Report (arXiv 2511.21631)](https://arxiv.org/abs/2511.21631) | T-RoPE → **명시적 텍스트 타임스탬프 정합**으로 교체(temporal grounding 개선 주장) · interleaved-MRoPE 강화 · DeepStack 통합 |
| [Qwen3-VL-4B-Instruct 모델 카드](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | OCR 지원 언어 **19 → 32개**. 벤치마크 표는 **이미지로만 제공돼 텍스트 추출 불가** |
| [QwenLM/Qwen3-VL README](https://github.com/qwenlm/qwen3-vl) | 벤치마크 표가 이미지뿐 (확인함) |
| [lmms-eval issue #857](https://github.com/EvolvingLMMs-Lab/lmms-eval/issues/857) | Qwen2.5-VL-7B Charades-STA 공식 보고값 43.6 mIoU에 대해 **공개 재현 시도에서 29.46**이 보고됨 |

## 상태

```
동급 3B ↔ 4B 공식 head-to-head 표      없음 (확인함)
Qwen3-VL-4B 개별 수치의 1차 출처       표가 이미지여서 미확보. 2차(블로그) 수치는 근거로 쓰지 않는다
세대 개선 주장의 근거 규모             비디오는 8B가 Qwen2.5-VL-72B와 경쟁 수준이라는 서술 — 4B가 아니다
```

## 본 프로젝트 endpoint를 대리하지 못하는 이유 5가지

```
1  head-to-head 아님   3B(2.5세대) ↔ 4B(3세대) 동급 대조표가 없다.
                     세대 개선 주장은 8B·72B 비교에서 나온 것이다
2  언어 불일치         Video-MME·MLVU·LVBench·Charades-STA는 한국어 벤치마크가 아니다.
                     Qwen3의 다국어 개선은 OCR 언어 수 확대이고 한국어 캡션 품질 측정이 아니다
3  과제 불일치         본 프로젝트는 캡션 생성 → 텍스트 임베딩 → 랭킹이다.
                     VQA·grounding 점수는 이 파이프라인을 통과한 성능이 아니다
4  정밀도 불일치       공개 수치는 bf16이고 배포는 양 arm 4bit다
5  길이 효과 미측정     실측한 캡션 길이 차이(131.4자 ↔ 82.0자)가 임베딩 검색에 주는
                     영향은 어느 공개 벤치마크에도 없다
```

3번이 특히 중요하다. dev 실측에서 4B는 **장면형(+0.0132)에서 근소 우세이고 복합형
(−0.2407)에서 크게 열세**였다. 외부 VQA·grounding 점수가 높다는 것과 이 층별 패턴은
서로 다른 얘기다.

## 재현 discrepancy 사례의 취급

`lmms-eval` 이슈는 **"공식 보고값과 공개 재현 시도 사이에 큰 차이가 보고된 사례"** 정도로만
쓴다. peer-reviewed independent failure로 과장하지 않는다. 시사점은 하나다 — 공개 수치를
근거로 배포 채택을 밀지 않는다.

## 결론

> 외부 근거는 **"4B 세대가 일반 시각·OCR·temporal grounding에서 개선됐다는 개발사 주장이
> 있다"**까지다. 본 프로젝트의 부호 역전(AI Hub +0.0310 ↔ dev −0.0903)을 해소하지 않고,
> **adoption gate로 쓰지 않는다.**
