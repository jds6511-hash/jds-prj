# SEMANTIC_CHAPTER_SHADOW_V1 reviewer packet

Conservative Event Map(PASS) 하나만 입력으로 써서 만든 chapter 후보다. 새 VLM 추론 0회 · Track A 입력 없음 · 생성 1회(재생성 금지). **executor는 판정을 쓰지 않는다.**

```
source map      0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c
chapter prompt  481a5f60630231ecee6935204326b1375b38eab5005d4fbde76a4a44601c7d9e (CHAPTER_PROMPT_V1)
generator       Qwen/Qwen2.5-7B-Instruct · bfloat16 · 4bit=False · greedy · max_new_tokens=4096
chapter 수       8 (허용 3–10)
```

## timeline

```
id    time          sec       confidence         title
CH01       0-48     48        MIXED_EVIDENCE     Food preparation - initial steps
      region R01,R02 · unresolved [[0.0, 24.0]]
CH02      48-96     48        MIXED_EVIDENCE     Food preparation - chopping and mixing
      region R03 · conflict CB001,CB002
CH03      96-192    96        LIMITED_EVIDENCE   Food preparation - cooking and shaping
      region R04
CH04     192-264    72        MIXED_EVIDENCE     Food preparation - finalizing and serving
      region R05 · conflict CB003,CB004,CB005
CH05     264-384    120       MIXED_EVIDENCE     Eating and food preparation continuation
      region R06,R07 · conflict CB006,CB007,CB008
CH06     384-480    96        LIMITED_EVIDENCE   Clothing and household tasks
      region R08
CH07     480-576    96        LIMITED_EVIDENCE   Gift wrapping and personal care
      region R09,R10 · conflict CB009,CB010
CH08     576-600    24        STABLE_DOMINANT    Exiting and final actions
      region R11
```

## 경계 격자 정렬 (판정 아님)

```
내부 경계 7개 중 24초 격자 위 7개 · 격자 밖 0개
```

## CH01  0–48  Food preparation - initial steps

```
confidence_class  MIXED_EVIDENCE
dominant          selecting ingredients, preparing ingredients
boundary 0      ACTIVITY_CHANGE · 24초 격자 위
region            R01, R02
conflict          없음
conflict source   -
unresolved        [[0.0, 24.0]]
source event      8건 (stable 8 · conflict 0)
창                W01
```

summary: Person selects and prepares various ingredients like soy sauce, curry, and potatoes. Conflicting observations exist for subsequent steps.

```
boundary 앞 근거 (최대 12초):
  (영상 시작)
boundary 뒤 근거 (최대 12초):
  (없음)
```

## CH02  48–96  Food preparation - chopping and mixing

```
confidence_class  MIXED_EVIDENCE
dominant          chopping vegetables, mixing ingredients
boundary 48      SCENE_OR_TASK_CHANGE · 24초 격자 위
region            R03
conflict          CB001, CB002
conflict source   W01, W02, W03
unresolved        없음
source event      20건 (stable 1 · conflict 19)
창                W01, W02, W03
```

summary: Person chops onions and carrots, mixes ingredients, and prepares ground beef. Conflicting observations exist for some steps.

```
boundary 앞 근거 (최대 12초):
  34.0-37.0 person | placing | potatoes in steamer
  37.0-40.0 person | covering | steamer
  40.0-43.0 person | pouring | curry powder into bowl
  43.0-46.0 person | placing | potato slices in blender
  46.0-49.0 person | blending | potato slices
boundary 뒤 근거 (최대 12초):
  46.0-49.0 person | blending | potato slices
  48.0-52.0 person | placing | bread pieces into blender
  49.0-52.0 person | pouring | oil into bowl with curry powder
  52.0-55.0 person | mixing | curry powder and oil
  52.0-55.0 person | placing | lid on blender
  55.0-72.0 person | chopping | onion
  55.0-58.0 person | pouring | oil into bowl of breadcrumbs
  58.0-62.0 person | stirring | breadcrumbs with oil
```

## CH03  96–192  Food preparation - cooking and shaping

```
confidence_class  LIMITED_EVIDENCE
dominant          cooking mixture, forming potato balls, coating in breadcrumbs
boundary 96      SUSTAINED_TRANSITION · 24초 격자 위
region            R04
conflict          없음
conflict source   -
unresolved        없음
source event      30건 (stable 30 · conflict 0)
창                W03, W04, W05, W06, W07
```

summary: Person cooks the mixture, peels and grates potatoes, forms potato balls, and coats them in breadcrumbs. Some steps are consistent across observations.

```
boundary 앞 근거 (최대 12초):
  82.0-86.0 person | stirring | breadcrumbs in bowl
  84.0-88.0 person | stirring | breadcrumbs in bowl
  88.0-92.0 person | transferring | ground beef into bowl
  92.0-96.0 person | adding | onion and crab stick to bowl
boundary 뒤 근거 (최대 12초):
  96.0-100.0 person | mixing | ingredients in bowl
  96.0-100.0 person | stirring | mixture in a bowl with chopsticks
  100.0-104.0 person | cooking | mixture in pan
  100.0-103.0 person | cooking | mixture in a pan over direct heat
  103.0-123.0 person | peeling | potato with a peeler
  104.0-120.0 person | peeling | potatoes with peeler
```

## CH04  192–264  Food preparation - finalizing and serving

```
confidence_class  MIXED_EVIDENCE
dominant          pouring liquid, mixing ingredients, serving food
boundary 192      SCENE_OR_TASK_CHANGE · 24초 격자 위
region            R05
conflict          CB003, CB004, CB005
conflict source   W07, W08, W09, W10
unresolved        없음
source event      16건 (stable 2 · conflict 14)
창                W07, W08, W09, W10
```

summary: Person pours liquid into a pan, mixes cream, and serves the prepared food. Conflicting observations exist for some steps.

```
boundary 앞 근거 (최대 12초):
  175.0-184.0 person | placing | coated balls on plate
  180.0-185.0 person | placing | coated potato dough on a plate
  184.0-187.0 person | pouring | cream into pan
  185.0-192.0 person | pouring | liquid into a pan
  187.0-190.0 person | stirring | onions in pan
  190.0-193.0 person | pouring | sauce into pan
boundary 뒤 근거 (최대 12초):
  190.0-193.0 person | pouring | sauce into pan
  192.0-195.0 person | pouring | powder from a bottle into a pan
  193.0-202.0 person | pouring | liquid into pan
  195.0-240.0 person | pouring | liquid from a bottle into a pan
  202.0-205.0 person | pouring | cream into bowl
```

## CH05  264–384  Eating and food preparation continuation

```
confidence_class  MIXED_EVIDENCE
dominant          eating food, preparing additional food
boundary 264      SCENE_OR_TASK_CHANGE · 24초 격자 위
region            R06, R07
conflict          CB006, CB007, CB008
conflict source   W12, W13, W14, W15
unresolved        없음
source event      24건 (stable 12 · conflict 12)
창                W10, W11, W12, W13, W14, W15
```

summary: Person eats noodles and breaded food items, and prepares additional food like curry udon and chicken with sauce. Conflicting observations exist for some steps.

```
boundary 앞 근거 (최대 12초):
  236.0-264.0 person | pouring | butter into a bowl
  245.0-255.0 person | serving | potato cream
  255.0-260.0 person | serving | herbs
  260.0-288.0 person | eating | noodles
boundary 뒤 근거 (최대 12초):
  260.0-288.0 person | eating | noodles
  264.0-272.0 person | using chopsticks | lifting noodles from a bowl
  272.0-280.0 person | eating | noodles with a spoon
```

## CH06  384–480  Clothing and household tasks

```
confidence_class  LIMITED_EVIDENCE
dominant          placing food in bowl, wrapping fabric, adjusting clothing
boundary 384      SCENE_OR_TASK_CHANGE · 24초 격자 위
region            R08
conflict          없음
conflict source   -
unresolved        없음
source event      29건 (stable 28 · conflict 1)
창                W15, W16, W17, W18, W19
```

summary: Person places chicken legs in a bowl, wraps fabric, and adjusts clothing. Some steps are consistent across observations.

```
boundary 앞 근거 (최대 12초):
  348.0-376.0 person | preparing food | gimbal with gloves
  370.0-375.0 person | arranging | sushi rolls on plate
  375.0-380.0 person | placing | bowl of soup on table
  376.0-380.0 person | eating | food with spoon
  380.0-384.0 person | preparing food | chicken with sauce
  380.0-385.0 person | placing | chicken legs in steamer
boundary 뒤 근거 (최대 12초):
  380.0-385.0 person | placing | chicken legs in steamer
  384.0-389.0 person | placing | noodles in a bowl
  385.0-390.0 person | placing | noodles in bowl
  389.0-400.0 person | placing | chicken legs in a bowl
  390.0-400.0 person | placing | chicken legs in bowl
```

## CH07  480–576  Gift wrapping and personal care

```
confidence_class  LIMITED_EVIDENCE
dominant          wrapping gift, putting on handbag, taking selfie
boundary 480      SCENE_OR_TASK_CHANGE · 24초 격자 위
region            R09, R10
conflict          CB009, CB010
conflict source   W19, W20, W21
unresolved        없음
source event      32건 (stable 18 · conflict 14)
창                W19, W20, W21, W22, W23
```

summary: Person wraps a gift, puts on a handbag, and takes a selfie. Some steps are consistent across observations.

```
boundary 앞 근거 (최대 12초):
  460.0-470.0 person | chopping | tomato
  468.0-472.0 hand | stirring | egg mixture in measuring cup
  470.0-475.0 person | pouring | egg yolk into measuring cup
  472.0-476.0 hand | pouring | egg mixture into pan
  475.0-480.0 person | stirring | egg yolk in measuring cup
  476.0-480.0 hand | stirring | egg mixture in pan
boundary 뒤 근거 (최대 12초):
  480.0-484.0 hand | transferring | egg mixture onto plate
  480.0-483.0 woman | pouring | sauce onto food
  483.0-486.0 woman | pouring | olive oil onto tofu
  484.0-488.0 hand | pouring | olive oil onto tofu
  486.0-528.0 woman | sprinkling | black pepper on food
  488.0-492.0 hand | placing | tofu on plate
```

## CH08  576–600  Exiting and final actions

```
confidence_class  STABLE_DOMINANT
dominant          adjusting clothing, looking at phone, entering shop
boundary 576      ACTIVITY_CHANGE · 24초 격자 위
region            R11
conflict          없음
conflict source   -
unresolved        없음
source event      6건 (stable 6 · conflict 0)
창                W23
```

summary: Person adjusts clothing, looks at a phone, and enters a shop.

```
boundary 앞 근거 (최대 12초):
  560.0-565.0 person | putting on | handbag
  561.0-565.0 person | picking up handbag | brown handbag
  565.0-570.0 person | taking photo | mirror
  565.0-573.0 person | taking mirror selfie | camera
  570.0-576.0 person | adjusting | clothing
  573.0-580.0 person | adjusting clothing | white shirt and shorts
boundary 뒤 근거 (최대 12초):
  573.0-580.0 person | adjusting clothing | white shirt and shorts
  580.0-585.0 person | looking at phone | phone displaying weather
  585.0-590.0 person | walking through train window | train window showing cityscape
```

## 구조 이상 (자동 수정·재생성하지 않았다)

```
ALL_BOUNDARIES_ON_24S_GRID 내부 경계 7개가 전부 24초 격자에 있다
```

## 판정 질문 (리뷰어 전용)

```
Q1 WHOLE_VIDEO_STRUCTURE
chapter sequence를 읽으면 영상의 주요 활동 흐름이 이해되는가
판정: NOT_ADJUDICATED
```

```
Q2 BOUNDARY_QUALITY
경계가 window/region 격자가 아니라 의미 변화에 대응하는가
판정: NOT_ADJUDICATED
```

```
Q3 CONFLICT_SAFETY
material conflict가 확정 사실로 잘못 해결되지 않았는가
판정: NOT_ADJUDICATED
```

```
Q4 OVERVIEW_INPUT_USABILITY
이 sequence를 다음 Overview 생성 입력으로 쓸 수 있는가
판정: NOT_ADJUDICATED
```

## 최종 어휘 (리뷰어 전용)

```
SEMANTIC_CHAPTER_SHADOW_PASS / HOLD / INCONCLUSIVE
executor 상태: EXECUTED / REVIEW_PENDING · verdict NOT_ADJUDICATED
```

말할 수 있는 최대 결론: 리뷰어가 PASS로 판정하면, Conservative Event Map은 conflict를 확정 사실로 바꾸지 않고도 whole-video Semantic Chapter 후보를 만들 수 있는 입력이다.

