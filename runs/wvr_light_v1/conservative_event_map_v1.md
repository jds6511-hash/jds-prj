# CONSERVATIVE_EVENT_MAP (WVR_CONSERVATIVE_EVENT_MAP_SHADOW_V1)

리뷰어 판정을 그대로 쓰고 conflict는 해결하지 않는다. 상위 narrative 문구는 생성하지 않았다.

```
region 11 · 0–600초 연속 · source event 160건 · 유실 0건
conflict 240초 · stitchable 288초 · single-source 48초 · unresolved 24초
```

## R01  0–24  UNRESOLVED

```
창        없음 (valid 관측 없음)
overlap   -
판정      -
상태      UNRESOLVED (valid 관측 없음)
frame     12개 (0.5fps · traceability 전용)
```

### UG01 UNRESOLVED_GAP  0–24

```
이 구간을 덮는 창은 W00뿐이고 W00은 WINDOW_INVALID다 — 대체 생성 금지
event 0건 · filled=False · resolution=NONE
```

## R02  24–48  SINGLE_SOURCE

```
창        W01
overlap   -
판정      -
상태      SINGLE_SOURCE (교차 검증 없음)
frame     12개 (0.5fps · traceability 전용)
```

### SS01 SINGLE_SOURCE_EVENT  24–48  (W01 · 8건)

```
    24.0–  28.0 | W01  | person | selecting | bottle of soy sauce
    28.0–  31.0 | W01  | person | selecting | packet of curry
    31.0–  34.0 | W01  | person | selecting | bag of potatoes
    34.0–  37.0 | W01  | person | placing | potatoes in steamer
    37.0–  40.0 | W01  | person | covering | steamer
    40.0–  43.0 | W01  | person | pouring | curry powder into bowl
    43.0–  46.0 | W01  | person | placing | potato slices in blender
    46.0–  48.0 | W01  | person | blending | potato slices  (원본 46.0–49.0)
```

## R03  48–96  CONFLICT

```
창        W01, W02, W03
overlap   O02, O03
판정      CONFLICT, CONFLICT
상태      MATERIAL_CONFLICT / RESOLUTION NONE
frame     24개 (0.5fps · traceability 전용)
conflict region CR01 (block CB001, CB002)
```

### CB001 CONFLICT_BLOCK  48–72  (resolution NONE)

```
observation_set_1  source W01 (4건)
    48.0–  49.0 | W01  | person | blending | potato slices  (원본 46.0–49.0)
    49.0–  52.0 | W01  | person | pouring | oil into bowl with curry powder
    52.0–  55.0 | W01  | person | mixing | curry powder and oil
    55.0–  72.0 | W01  | person | chopping | onion
observation_set_2  source W02 (7건)
    48.0–  52.0 | W02  | person | placing | bread pieces into blender
    52.0–  55.0 | W02  | person | placing | lid on blender
    55.0–  58.0 | W02  | person | pouring | oil into bowl of breadcrumbs
    58.0–  62.0 | W02  | person | stirring | breadcrumbs with oil
    62.0–  66.0 | W02  | person | chopping | onion on cutting board
    66.0–  70.0 | W02  | person | chopping | carrot on cutting board
    70.0–  72.0 | W02  | person | placing | ground beef into bowl  (원본 70.0–74.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB002 CONFLICT_BLOCK  72–96  (resolution NONE)

```
observation_set_1  source W02 (4건)
    72.0–  74.0 | W02  | person | placing | ground beef into bowl  (원본 70.0–74.0)
    74.0–  78.0 | W02  | person | placing | onion and carrot into bowl with beef
    78.0–  82.0 | W02  | person | transferring | toasted breadcrumbs into bowl
    82.0–  86.0 | W02  | person | stirring | breadcrumbs in bowl
observation_set_2  source W03 (6건)
    72.0–  76.0 | W03  | person | peeling | carrot
    76.0–  80.0 | W03  | person | placing | lid on pot
    80.0–  84.0 | W03  | person | pouring | breadcrumbs into bowl
    84.0–  88.0 | W03  | person | stirring | breadcrumbs in bowl
    88.0–  92.0 | W03  | person | transferring | ground beef into bowl
    92.0–  96.0 | W03  | person | adding | onion and crab stick to bowl
두 관측은 alternative source observations다 — 선호·승자 없음
```

## R04  96–192  STITCHABLE

```
창        W03, W04, W05, W06, W07
overlap   O04, O05, O06, O07
판정      SAME_EVENT, CONTINUATION, CONTINUATION, CONTINUATION
상태      STITCHABLE (리뷰어 판정)
frame     48개 (0.5fps · traceability 전용)
```

### SG001 CONSENSUS_EVENT  96–120  (W03 + W04 · SAME_EVENT · 6건)

```
    96.0– 100.0 | W03  | person | mixing | ingredients in bowl
    96.0– 100.0 | W04  | person | stirring | mixture in a bowl with chopsticks
   100.0– 104.0 | W03  | person | cooking | mixture in pan
   100.0– 103.0 | W04  | person | cooking | mixture in a pan over direct heat
   103.0– 120.0 | W04  | person | peeling | potato with a peeler  (원본 103.0–123.0)
   104.0– 120.0 | W03  | person | peeling | potatoes with peeler
```

### SG002 CONTINUATION_GROUP  120–144  (W04 + W05 · CONTINUATION · 9건)

```
   120.0– 123.0 | W04  | person | peeling | potato with a peeler  (원본 103.0–123.0)
   120.0– 125.0 | W05  | person | grating | potato
   123.0– 127.0 | W04  | person | mixing | mixture in a bowl with chopsticks
   125.0– 130.0 | W05  | person | mixing | potato mixture
   127.0– 131.0 | W04  | person | forming | mixture into balls
   130.0– 135.0 | W05  | person | forming | potato balls
   131.0– 144.0 | W04  | person | placing | balls on a plate
   135.0– 140.0 | W05  | person | coating | potato balls
   140.0– 144.0 | W05  | person | placing | potato balls  (원본 140.0–145.0)
```

### SG003 CONTINUATION_GROUP  144–168  (W05 + W06 · CONTINUATION · 8건)

```
   144.0– 145.0 | W05  | person | placing | potato balls  (원본 140.0–145.0)
   144.0– 149.0 | W06  | person | pouring | liquid into a bowl
   145.0– 168.0 | W05  | person | coating | potato balls
   149.0– 153.0 | W06  | person | mixing | ingredients in a bowl
   153.0– 157.0 | W06  | person | dipping | potato dough in egg mixture
   157.0– 161.0 | W06  | person | coating | potato dough in breadcrumbs
   161.0– 165.0 | W06  | person | placing | coated potato dough on a plate
   165.0– 168.0 | W06  | person | coating | potato dough in breadcrumbs  (원본 165.0–170.0)
```

### SG004 CONTINUATION_GROUP  168–192  (W06 + W07 · CONTINUATION · 10건)

```
   168.0– 170.0 | W06  | person | coating | potato dough in breadcrumbs  (원본 165.0–170.0)
   168.0– 175.0 | W07  | person | coating | ball in breadcrumbs
   170.0– 175.0 | W06  | person | placing | coated potato dough on a plate
   175.0– 180.0 | W06  | person | coating | potato dough in breadcrumbs
   175.0– 184.0 | W07  | person | placing | coated balls on plate
   180.0– 185.0 | W06  | person | placing | coated potato dough on a plate
   184.0– 187.0 | W07  | person | pouring | cream into pan
   185.0– 192.0 | W06  | person | pouring | liquid into a pan
   187.0– 190.0 | W07  | person | stirring | onions in pan
   190.0– 192.0 | W07  | person | pouring | sauce into pan  (원본 190.0–193.0)
```

## R05  192–264  CONFLICT

```
창        W07, W08, W09, W10
overlap   O08, O09, O10
판정      CONFLICT, CONFLICT, CONFLICT
상태      MATERIAL_CONFLICT / RESOLUTION NONE
frame     36개 (0.5fps · traceability 전용)
conflict region CR02 (block CB003, CB004, CB005)
```

### CB003 CONFLICT_BLOCK  192–216  (resolution NONE)

```
observation_set_1  source W07 (4건)
   192.0– 193.0 | W07  | person | pouring | sauce into pan  (원본 190.0–193.0)
   193.0– 202.0 | W07  | person | pouring | liquid into pan
   202.0– 205.0 | W07  | person | pouring | cream into bowl
   205.0– 216.0 | W07  | person | mixing | cream in bowl
observation_set_2  source W08 (2건)
   192.0– 195.0 | W08  | person | pouring | powder from a bottle into a pan
   195.0– 216.0 | W08  | person | pouring | liquid from a bottle into a pan  (원본 195.0–240.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB004 CONFLICT_BLOCK  216–240  (resolution NONE)

```
observation_set_1  source W08 (1건)
   216.0– 240.0 | W08  | person | pouring | liquid from a bottle into a pan  (원본 195.0–240.0)
observation_set_2  source W09 (6건)
   216.0– 220.0 | W09  | person | pouring | mashed potatoes into a bowl with a hand mixer
   220.0– 224.0 | W09  | person | mixing | mashed potatoes with a hand mixer
   224.0– 228.0 | W09  | person | transferring | mashed potatoes into a piping bag
   228.0– 232.0 | W09  | person | placing | potato croquettes on a wire rack
   232.0– 236.0 | W09  | person | pouring | oil into a baking tray
   236.0– 240.0 | W09  | person | pouring | butter into a bowl  (원본 236.0–264.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB005 CONFLICT_BLOCK  240–264  (resolution NONE)

```
observation_set_1  source W09 (1건)
   240.0– 264.0 | W09  | person | pouring | butter into a bowl  (원본 236.0–264.0)
observation_set_2  source W10 (4건)
   240.0– 245.0 | W10  | person | serving | noodles
   245.0– 255.0 | W10  | person | serving | potato cream
   255.0– 260.0 | W10  | person | serving | herbs
   260.0– 264.0 | W10  | person | eating | noodles  (원본 260.0–288.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

## R06  264–312  STITCHABLE

```
창        W10, W11, W12
overlap   O11, O12
판정      CONTINUATION, CONTINUATION
상태      STITCHABLE (리뷰어 판정)
frame     24개 (0.5fps · traceability 전용)
```

### SG005 CONTINUATION_GROUP  264–288  (W10 + W11 · CONTINUATION · 4건)

```
   264.0– 288.0 | W10  | person | eating | noodles  (원본 260.0–288.0)
   264.0– 272.0 | W11  | person | using chopsticks | lifting noodles from a bowl
   272.0– 280.0 | W11  | person | eating | noodles with a spoon
   280.0– 288.0 | W11  | person | using chopsticks | picking up a breaded food item
```

### SG006 CONTINUATION_GROUP  288–312  (W11 + W12 · CONTINUATION · 9건)

```
   288.0– 296.0 | W11  | person | eating | breaded food item
   288.0– 293.0 | W12  | person | breaking apart | breaded potato ball
   293.0– 297.0 | W12  | person | eating | breaded potato ball
   296.0– 304.0 | W11  | person | using chopsticks | picking up a breaded food item
   297.0– 301.0 | W12  | person | eating | curry udon
   301.0– 305.0 | W12  | person | eating | breaded potato ball
   304.0– 312.0 | W11  | person | eating | breaded food item
   305.0– 310.0 | W12  | person | drinking | water
   310.0– 312.0 | W12  | person | eating | curry udon  (원본 310.0–336.0)
```

## R07  312–384  CONFLICT

```
창        W12, W13, W14, W15
overlap   O13, O14, O15
판정      CONFLICT, CONFLICT, CONFLICT
상태      MATERIAL_CONFLICT / RESOLUTION NONE
frame     36개 (0.5fps · traceability 전용)
conflict region CR03 (block CB006, CB007, CB008)
```

### CB006 CONFLICT_BLOCK  312–336  (resolution NONE)

```
observation_set_1  source W12 (1건)
   312.0– 336.0 | W12  | person | eating | curry udon  (원본 310.0–336.0)
observation_set_2  source W13 (2건)
   312.0– 317.0 | W13  | a person | eating | cream curry udon
   317.0– 336.0 | W13  | a person | eating | rice with kimchi  (원본 317.0–360.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB007 CONFLICT_BLOCK  336–360  (resolution NONE)

```
observation_set_1  source W13 (1건)
   336.0– 360.0 | W13  | a person | eating | rice with kimchi  (원본 317.0–360.0)
observation_set_2  source W14 (2건)
   336.0– 348.0 | W14  | person | eating | noodles with chopsticks and spoon
   348.0– 360.0 | W14  | person | preparing food | gimbal with gloves  (원본 348.0–376.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB008 CONFLICT_BLOCK  360–384  (resolution NONE)

```
observation_set_1  source W14 (3건)
   360.0– 376.0 | W14  | person | preparing food | gimbal with gloves  (원본 348.0–376.0)
   376.0– 380.0 | W14  | person | eating | food with spoon
   380.0– 384.0 | W14  | person | preparing food | chicken with sauce
observation_set_2  source W15 (5건)
   360.0– 365.0 | W15  | person | placing | sushi roll on cutting board
   365.0– 370.0 | W15  | person | placing | sushi rolls on plate
   370.0– 375.0 | W15  | person | arranging | sushi rolls on plate
   375.0– 380.0 | W15  | person | placing | bowl of soup on table
   380.0– 384.0 | W15  | person | placing | chicken legs in steamer  (원본 380.0–385.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

## R08  384–480  STITCHABLE

```
창        W15, W16, W17, W18, W19
overlap   O16, O17, O18, O19
판정      SAME_EVENT, SAME_EVENT, SAME_EVENT, TRANSITION
상태      STITCHABLE (리뷰어 판정)
frame     48개 (0.5fps · traceability 전용)
```

### SG007 CONSENSUS_EVENT  384–408  (W15 + W16 · SAME_EVENT · 8건)

```
   384.0– 385.0 | W15  | person | placing | chicken legs in steamer  (원본 380.0–385.0)
   384.0– 389.0 | W16  | person | placing | noodles in a bowl
   385.0– 390.0 | W15  | person | placing | noodles in bowl
   389.0– 400.0 | W16  | person | placing | chicken legs in a bowl
   390.0– 400.0 | W15  | person | placing | chicken legs in bowl
   400.0– 405.0 | W15  | person | holding | orange cloth
   400.0– 408.0 | W16  | person | holding | orange pajama pants
   405.0– 408.0 | W15  | person | holding | pink cloth
```

### SG008 CONSENSUS_EVENT  408–432  (W16 + W17 · SAME_EVENT · 8건)

```
   408.0– 412.0 | W16  | person | pulling | elastic band from pajama pants
   408.0– 413.0 | W17  | person | holding | elastic band and orange fabric
   412.0– 416.0 | W16  | person | holding | elastic band
   413.0– 420.0 | W17  | person | holding | orange fabric with pattern
   416.0– 420.0 | W16  | person | holding | orange pajama pants
   420.0– 432.0 | W16  | person | placing | orange pajama pants in a drawer
   420.0– 426.0 | W17  | person | placing | orange fabric on drawer
   426.0– 432.0 | W17  | person | placing | white elastic band on sewing machine  (원본 426.0–433.0)
```

### SG009 CONSENSUS_EVENT  432–456  (W17 + W18 · SAME_EVENT · 5건)

```
   432.0– 433.0 | W17  | person | placing | white elastic band on sewing machine  (원본 426.0–433.0)
   432.0– 440.0 | W18  | person | sewing | orange fabric with green dots
   433.0– 440.0 | W17  | person | sewing | orange fabric with pattern
   440.0– 456.0 | W17  | person | holding | orange fabric with pattern
   440.0– 456.0 | W18  | person | holding up | orange fabric with green dots  (원본 440.0–460.0)
```

### SG010 TRANSITION  456–480  (W18 + W19 · TRANSITION · 10건)

```
   456.0– 460.0 | W18  | person | holding up | orange fabric with green dots  (원본 440.0–460.0)
   456.0– 460.0 | W19  | hand | placing | crispy ball on plate
   460.0– 470.0 | W18  | person | chopping | tomato
   460.0– 464.0 | W19  | hand | chopping | tomato
   464.0– 468.0 | W19  | hand | cracking | egg into measuring cup
   468.0– 472.0 | W19  | hand | stirring | egg mixture in measuring cup
   470.0– 475.0 | W18  | person | pouring | egg yolk into measuring cup
   472.0– 476.0 | W19  | hand | pouring | egg mixture into pan
   475.0– 480.0 | W18  | person | stirring | egg yolk in measuring cup
   476.0– 480.0 | W19  | hand | stirring | egg mixture in pan
```

## R09  480–528  CONFLICT

```
창        W19, W20, W21
overlap   O20, O21
판정      CONFLICT, CONFLICT
상태      MATERIAL_CONFLICT / RESOLUTION NONE
frame     24개 (0.5fps · traceability 전용)
conflict region CR04 (block CB009, CB010)
```

### CB009 CONFLICT_BLOCK  480–504  (resolution NONE)

```
observation_set_1  source W19 (6건)
   480.0– 484.0 | W19  | hand | transferring | egg mixture onto plate
   484.0– 488.0 | W19  | hand | pouring | olive oil onto tofu
   488.0– 492.0 | W19  | hand | placing | tofu on plate
   492.0– 496.0 | W19  | hand | placing | shredded cabbage on plate
   496.0– 500.0 | W19  | person | tying | hair into bun
   500.0– 504.0 | W19  | person | adjusting | hair bun
observation_set_2  source W20 (3건)
   480.0– 483.0 | W20  | woman | pouring | sauce onto food
   483.0– 486.0 | W20  | woman | pouring | olive oil onto tofu
   486.0– 504.0 | W20  | woman | sprinkling | black pepper on food  (원본 486.0–528.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

### CB010 CONFLICT_BLOCK  504–528  (resolution NONE)

```
observation_set_1  source W20 (1건)
   504.0– 528.0 | W20  | woman | sprinkling | black pepper on food  (원본 486.0–528.0)
observation_set_2  source W21 (5건)
   504.0– 509.0 | W21  | a woman | walking | through a room
   509.0– 513.0 | W21  | a woman | placing | a small box on a table
   513.0– 520.0 | W21  | a woman | holding | two small boxes
   520.0– 524.0 | W21  | a woman | placing | a small pouch on a table
   524.0– 528.0 | W21  | a woman | wrapping | a small pouch in a brown paper bag  (원본 524.0–529.0)
두 관측은 alternative source observations다 — 선호·승자 없음
```

## R10  528–576  STITCHABLE

```
창        W21, W22, W23
overlap   O22, O23
판정      SAME_EVENT, SAME_EVENT
상태      STITCHABLE (리뷰어 판정)
frame     24개 (0.5fps · traceability 전용)
```

### SG011 CONSENSUS_EVENT  528–552  (W21 + W22 · SAME_EVENT · 10건)

```
   528.0– 529.0 | W21  | a woman | wrapping | a small pouch in a brown paper bag  (원본 524.0–529.0)
   528.0– 533.0 | W22  | person | wrapping | gift in kraft paper
   529.0– 533.0 | W21  | a woman | placing | a stamp on a table
   533.0– 541.0 | W21  | a woman | tying | a ribbon around a wrapped package
   533.0– 537.0 | W22  | person | placing | stamp on kraft paper bag
   537.0– 541.0 | W22  | person | tying | ribbon around kraft paper bag
   541.0– 552.0 | W21  | a woman | holding | a wrapped package
   541.0– 545.0 | W22  | person | adjusting | bow on kraft paper bag
   545.0– 550.0 | W22  | person | holding | wrapped gift
   550.0– 552.0 | W22  | person | unfolding | fabric  (원본 550.0–555.0)
```

### SG012 CONSENSUS_EVENT  552–576  (W22 + W23 · SAME_EVENT · 10건)

```
   552.0– 555.0 | W22  | person | unfolding | fabric  (원본 550.0–555.0)
   552.0– 557.0 | W23  | person | holding and displaying fabric | white fabric
   555.0– 560.0 | W22  | person | putting on | fabric
   557.0– 561.0 | W23  | person | placing fabric on table | white fabric
   560.0– 565.0 | W22  | person | putting on | handbag
   561.0– 565.0 | W23  | person | picking up handbag | brown handbag
   565.0– 570.0 | W22  | person | taking photo | mirror
   565.0– 573.0 | W23  | person | taking mirror selfie | camera
   570.0– 576.0 | W22  | person | adjusting | clothing
   573.0– 576.0 | W23  | person | adjusting clothing | white shirt and shorts  (원본 573.0–580.0)
```

## R11  576–600  SINGLE_SOURCE

```
창        W23
overlap   -
판정      -
상태      SINGLE_SOURCE (교차 검증 없음)
frame     12개 (0.5fps · traceability 전용)
```

### SS02 SINGLE_SOURCE_EVENT  576–600  (W23 · 6건)

```
   576.0– 580.0 | W23  | person | adjusting clothing | white shirt and shorts  (원본 573.0–580.0)
   580.0– 585.0 | W23  | person | looking at phone | phone displaying weather
   585.0– 590.0 | W23  | person | walking through train window | train window showing cityscape
   590.0– 593.0 | W23  | person | looking at train station sign | train station sign with text
   593.0– 597.0 | W23  | person | walking outside | building with signage
   597.0– 600.0 | W23  | person | entering shop | shop entrance with sign
```

