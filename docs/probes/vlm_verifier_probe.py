# 한계2(언급≠행위) 처방 실증: VLM 프레임 재검증(verifier) 프로토타입
# top-k 결과의 대표 프레임을 캡셔너(Qwen2.5-VL-3B-4bit)에게 보여주고 질의 장면 여부를
# 예/아니오로 판정시킨다. 본 시스템 미반영(dev 프로브) — 정식 반영 시 표시 계층
# 전용(랭킹 불변, 8-2 abstention과 동일 계약)이면 test 재평가 불필요.
# 사례: '마늘 다지는 장면' top3(seg 7/4/8)는 자막의 '다진 마늘' 언급 반향 오답
# (프레임 실물: 오이·당근 손질, 2026-07-13 확인). 양성 대조군: seg165(새우 조리),
# seg82(초밥 매대).
#
# 실측 결론(2026-07-13, 5/7): 오답 기각 4/4 — 언급 반향 3건 전부 + 사람 기대 라벨이
# 틀렸던 손질 장면(seg165)까지 정확히 기각(정밀도 우수). 양성 승인 2/4 — 초밥 매대는
# 승인하나 '기름 속 반죽 입힌 새우 부치기'(seg191)는 어휘를 풀어써도 기각 = 3B의
# 시각 인식 한계(재현 부족). 시사점: 재검증 단계 구조는 유효하나 verifier 품질이
# VLM 크기에 종속 — 3B는 과잉 경고 위험이 있어 정식 반영은 서버급 VLM에서 재실측 후.
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import common
from m3_generate import load_vlm, caption_frame

cfg = common.load_config("config.yaml")
wdir = common.work_dir(cfg, "pland_costco_hosting")
doc = json.load(open(wdir / "segments.json", encoding="utf-8"))
model, processor = load_vlm(cfg)

CASES = [
    # (질의, seg_idx, 기대판정, 비고)
    ("마늘을 다지는 장면", 7, "아니오", "언급 반향 오답 top1"),
    ("마늘을 다지는 장면", 4, "아니오", "언급 반향 오답 top2"),
    ("마늘을 다지는 장면", 8, "아니오", "언급 반향 오답 top3"),
    # seg165는 새우 '손질' 장면(프레임 확인) — 부치는 장면 아님. 1차 실행에서 verifier가
    # '아니오'로 판정했고 그게 옳았다(사람 기대 라벨이 오류). 음성 케이스로 재분류.
    ("새우전을 부치는 장면", 165, "아니오", "새우 손질(부치기 아님) — 검색 top1보다 정밀"),
    # seg191은 팬에 기름을 두르고 새우를 부치는 장면(프레임 확인) — 진짜 양성.
    ("새우전을 부치는 장면", 191, "예", "양성 대조군(팬에 부치는 중, 15:55)"),
    # 동일 프레임 + 풀어쓴 질의: '아니오'가 '새우전' 어휘 문제인지 분리
    ("새우를 기름에 굽는 장면", 191, "예", "양성 대조군(어휘 풀어쓰기)"),
    ("초밥이 있는 장면", 82, "예", "양성 대조군(초밥 매대)"),
]

PROMPT = ("이 이미지가 '{q}'에 해당하는가? 화면에 실제로 보이는 것만 근거로 "
          "'예' 또는 '아니오' 한 단어로만 답하라.")

correct = 0
for q, idx, expect, note in CASES:
    frame = wdir / doc["segments"][idx]["rep_frame"]
    ans = caption_frame(str(frame), PROMPT.format(q=q), model, processor, cfg).strip()
    verdict = "예" if ans.startswith("예") else ("아니오" if ans.startswith("아니") else f"불명({ans[:20]})")
    ok = verdict == expect
    correct += ok
    print(f"{'PASS' if ok else 'FAIL'} | {q} × seg{idx} ({note}): 판정={verdict} 기대={expect}")
print(f"\n{correct}/{len(CASES)} 일치")
