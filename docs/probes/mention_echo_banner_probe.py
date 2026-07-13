# 부정 결과 기록: 언급-반향 배너의 채널-격차 휴리스틱은 성립하지 않음 (2026-07-13)
#
# 가설: "~하는 장면" 질의에서 top1이 자막 채널만으로 올라온 경우(sub_cos 높고 cap_cos
# 낮음) "언급된 내용이며 해당 장면이 아닐 수 있음" 배너를 띄운다.
#
# 실측 기각: sub-cap 격차가 잡아야 할 것과 정반대. 언급-반향 오답(마늘 +0.15, 양파
# +0.06)이 정상 자막형 질의(삼각김밥 +0.27, 손님초대 +0.24)보다 격차가 작다. 마늘을
# 잡는 임계는 정상 자막형 전부를 오경고한다.
#
# 원인: 언급-반향 오답은 음식 장면이라 캡션도 부분 매칭(cap 0.616)되는 반면, 진짜 대화
# 질의는 캡션이 설명 불가(cap 0.437)라 격차가 오히려 크다. 유사도 공간에는 "존재하지
# 않는 장면"을 구분할 신호가 없다(한계2의 재확인).
#
# 결론: 채널-격차 배너 미채택. 신뢰 가능한 경로는 VLM 프레임 verifier뿐이며(크기 종속,
# vlm_verifier_probe.py 참조) 서버 GPU 과제로 유지.
#
# 재현: docs/probes/ 아래에서 실행 시 아래 격차 표가 재생성된다.
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import numpy as np
import common
from m4_index import embed_texts
from m5_search import VideoIndex, combine_scores

cfg = common.load_config("config.yaml")
vi = VideoIndex.load(cfg, "pland_costco_hosting")
cases = [
    ("A장면(정상)", "새우전을 부치는 장면"), ("A장면(정상)", "가방을 만드는 장면"),
    ("B자막(정상)", "삼각김밥 이야기하는 부분"), ("B자막(정상)", "손님 초대 이야기를 하는 부분"),
    ("C언급반향(오답)", "마늘 다지는 장면"), ("C언급반향(오답)", "양파를 볶는 장면"),
]
print(f'{"유형":14s} {"질의":22s} sub_cos cap_cos  gap')
for tag, q in cases:
    qv = embed_texts([q], cfg["embed_model"])[0]
    s_sub, s_cap = vi.emb_sub @ qv, vi.emb_cap @ qv
    t = np.argsort(-combine_scores(s_sub, s_cap, vi.static_mask, 0.5), kind="stable")[0]
    print(f"{tag:14s} {q:22s} {s_sub[t]:.3f}  {s_cap[t]:.3f}  {s_sub[t]-s_cap[t]:+.3f}")
print("\n=> 오답 격차 < 정상 자막형 격차 → 채널-격차 배너 기각")
