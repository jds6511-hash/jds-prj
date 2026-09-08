"""V2 claim → 한국어 evidence 표면형 사전 (2026-09-09 · freeze).

```
이 사전은 **frozen V2 영어 claim 문자열만 보고** 작성했다.
evidence(캡션·자막) 본문을 읽고 항을 추가·수정하지 않는다.
사전이 못 덮는 claim은 EVIDENCE_UNRESOLVED로 남는 것이 정상이고,
사후에 항을 추가해 UNRESOLVED를 줄이는 것은 계약 위반이다.
```

evidence 채널이 한국어이고 V2 진단 출력은 English-only이므로 토큰 겹침으로는
대조가 불가능하다. 그래서 claim 어휘를 한국어 어간 substring 집합으로 사전등록한다.

`COLLISION_DROPPED`: 서로 다른 object 집합에 동시에 들어가 지시 대상이 갈리는
표면형은 **양쪽에서 제거**한다(예: "볼"은 bowl·balls 둘 다에 걸린다).
"""
import hashlib

LEXICON_NAME = "WVR_EVIDENCE_LEXICON_V1"
SOURCE = "frozen V2 collapsed claims (density_v2_D{1,2,3}_S{0,1}.json)"

# 표면형이 두 object 어휘에 동시에 걸려 제거한 항 (감사 기록)
COLLISION_DROPPED = {
    "볼": ("bowl", "balls"),
}

ACTION_TERMS = {
    "eating": ("먹", "시식", "식사", "맛보"),
    "drinking": ("마시", "마신", "음료"),
    "cooking": ("요리", "조리", "익히", "굽", "구워", "볶", "튀기", "끓"),
    "sewing": ("재봉", "바느질", "미싱"),
    "chopping": ("썰", "자르", "다지", "칼질", "절단"),
    "mixing": ("섞", "혼합", "버무리", "반죽"),
    "stirring": ("젓", "저어", "섞"),
    "washing": ("씻", "세척"),
    "placing": ("놓", "담", "올리"),
    "steaming": ("찌", "찜", "증기"),
    "pouring": ("붓", "부어", "따르"),
    "adding": ("넣", "추가"),
    "peeling": ("깎", "벗기", "껍질"),
    "mashing": ("으깨", "으깬", "매시", "짓이기"),
    "forming": ("빚", "모양", "성형", "둥글", "만들"),
    "shaping": ("빚", "모양", "성형", "둥글", "만들"),
    "coating": ("묻히", "입히", "바르", "코팅", "튀김옷"),
    "handling": ("다루", "들고", "손에"),
    "holding": ("들고", "쥐", "잡"),
    "using": ("사용", "쓰"),
    "grating": ("갈", "채썰", "그레이터"),
    "pressing": ("누르", "짜", "압착", "프레스"),
    "dipping": ("담그", "적시", "묻히"),
    "preparing": ("준비", "손질", "만들"),
    "food": (),          # "preparing food"의 뒤 토큰 — action 쪽에서는 비어 있다
}

OBJECT_TERMS = {
    "breaded": ("튀김", "빵가루", "튀긴"),
    "fried": ("튀김", "튀긴"),
    "food": ("음식", "요리"),
    "item": (),
    "chopsticks": ("젓가락",),
    "drink": ("음료", "마실"),
    "glass": ("컵", "유리컵", "잔"),
    "straw": ("빨대",),
    "water": ("물",),
    "rice": ("밥", "쌀"),
    "noodle": ("국수", "면", "우동", "라면"),
    "soup": ("국물", "국", "탕", "스프"),
    "spoon": ("숟가락", "스푼"),
    "gimbap": ("김밥", "김"),
    "gloves": ("장갑",),
    "chicken": ("치킨", "닭"),
    "leg": ("다리",),
    "torch": ("토치", "화염", "불꽃"),
    "pajama": ("잠옷", "파자마"),
    "pants": ("바지",),
    "sewing": ("재봉틀", "미싱", "재봉"),
    "machine": ("기계", "틀"),
    "tomato": ("토마토",),
    "knife": ("칼",),
    "egg": ("달걀", "계란", "에그"),
    "pan": ("팬", "프라이팬", "후라이팬"),
    "potato": ("감자",),
    "potatoes": ("감자",),
    "steamer": ("찜기", "찜통", "스티머"),
    "breadcrumbs": ("빵가루", "브레드크럼"),
    "bowl": ("그릇", "대접"),
    "onion": ("양파",),
    "carrot": ("당근",),
    "crab": ("크래미", "게맛살", "크랩"),
    "stick": (),
    "oil": ("기름", "오일"),
    "ground": (),
    "beef": ("소고기", "고기", "민스"),
    "mixture": ("반죽", "혼합물", "재료"),
    "mash": ("으깬", "매시"),
    "mashed": ("으깬", "매시"),
    "stove": ("가스레인지", "레인지", "인덕션", "불"),
    "peeler": ("감자칼", "필러"),
    "balls": ("동그랑", "완자", "경단", "공"),
    "ball": ("동그랑", "완자", "경단", "공"),
    "plate": ("접시",),
    "oven": ("오븐", "에어프라이어"),
    "strainer": ("체", "소쿠리", "채반", "스트레이너"),
    "cutting": ("도마",),
    "board": ("도마",),
    "ricer": ("라이서", "매셔", "으깨"),
    "press": ("프레스", "압착", "누르"),
    "steamer_basket": ("찜기",),
}


def lexicon_hash() -> str:
    payload = repr(sorted(ACTION_TERMS.items())) + repr(sorted(
        OBJECT_TERMS.items())) + repr(sorted(COLLISION_DROPPED.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def action_terms(token: str) -> tuple:
    return ACTION_TERMS.get(token, ())


def object_terms(token: str) -> tuple:
    return OBJECT_TERMS.get(token, ())
