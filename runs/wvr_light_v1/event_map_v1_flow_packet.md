# EVENT_MAP_COVERAGE_SHADOW_V1 whole-video flow packet

사전등록: `docs/preregistration/WVR_EVENT_MAP_COVERAGE_SHADOW_V1_2026-09-10.md`

```
기존 SHADOW_V1의 23 VALID 창(W01–W23) event만으로 만든 후보다.
W00 [0,48)은 INVALID source이므로 채우지 않고 남겨 뒀다.
이것은 CANDIDATE_EVENT_MAP이고 verified factual Event Map이 아니다.
relation·transition 라벨은 후보이며 판정 authority가 아니다.
coverage percentage ≠ semantic correctness.
reviewer 질문 Q1 FLOW_RECOVERABLE · Q2 GAP_MATERIALITY · Q3 EVENT_MAP_USABLE
판정 어휘 EVENT_MAP_SHADOW_PASS / HOLD / INCONCLUSIVE — executor는 판정하지 않았다.
```

## coverage 요약

```
window coverage      576.0초  96.00%
event coverage       576.0초  96.00%
redundant (window)   528.0초  88.00%
redundant (event)    518.0초  86.33%
unresolved            24.0초   4.00%
```

unresolved 구간:

```
   0.0 –   24.0초
```

## chapter candidate별 흐름

### CH01  24.0 – 104.0초  (30 group · 창 W01, W02, W03, W04)

```
  24.0–  28.0 | person                 | selecting    | bottle of soy sauce                | W01 | SINGLE_WINDOW_OBSERVED | frames 2
  28.0–  31.0 | person                 | selecting    | packet of curry                    | W01 | SINGLE_WINDOW_OBSERVED | frames 2
  31.0–  34.0 | person                 | selecting    | bag of potatoes                    | W01 | SINGLE_WINDOW_OBSERVED | frames 1
  34.0–  37.0 | person                 | placing      | potatoes in steamer                | W01 | SINGLE_WINDOW_OBSERVED | frames 2
  37.0–  40.0 | person                 | covering     | steamer                            | W01 | SINGLE_WINDOW_OBSERVED | frames 1
  40.0–  43.0 | person                 | pouring      | curry powder into bowl             | W01 | SINGLE_WINDOW_OBSERVED | frames 2
  43.0–  46.0 | person                 | placing      | potato slices in blender           | W01 | SINGLE_WINDOW_OBSERVED | frames 1
  46.0–  49.0 | person                 | blending     | potato slices                      | W01 | SINGLE_WINDOW_OBSERVED/MULTI_WINDOW_OBSERVED | frames 2
  48.0–  52.0 | person                 | placing      | bread pieces into blender          | W02 | MULTI_WINDOW_OBSERVED | frames 2
  49.0–  52.0 | person                 | pouring      | oil into bowl with curry powder    | W01 | MULTI_WINDOW_OBSERVED | frames 1
  52.0–  55.0 | person                 | mixing       | curry powder and oil               | W01 | MULTI_WINDOW_OBSERVED | frames 2
  52.0–  55.0 | person                 | placing      | lid on blender                     | W02 | MULTI_WINDOW_OBSERVED | frames 2
  55.0–  72.0 | person                 | chopping     | onion                              | W01 | MULTI_WINDOW_OBSERVED | frames 8
  55.0–  58.0 | person                 | pouring      | oil into bowl of breadcrumbs       | W02 | MULTI_WINDOW_OBSERVED | frames 1
  58.0–  62.0 | person                 | stirring     | breadcrumbs with oil               | W02 | MULTI_WINDOW_OBSERVED | frames 2
  62.0–  66.0 | person                 | chopping     | onion on cutting board             | W02 | MULTI_WINDOW_OBSERVED | frames 2
  66.0–  70.0 | person                 | chopping     | carrot on cutting board            | W02 | MULTI_WINDOW_OBSERVED | frames 2
  70.0–  74.0 | person                 | placing      | ground beef into bowl              | W02 | MULTI_WINDOW_OBSERVED | frames 2
  72.0–  76.0 | person                 | peeling      | carrot                             | W03 | MULTI_WINDOW_OBSERVED | frames 2
  74.0–  78.0 | person                 | placing      | onion and carrot into bowl with be | W02 | MULTI_WINDOW_OBSERVED | frames 2
  76.0–  80.0 | person                 | placing      | lid on pot                         | W03 | MULTI_WINDOW_OBSERVED | frames 2
  78.0–  82.0 | person                 | transferring | toasted breadcrumbs into bowl      | W02 | MULTI_WINDOW_OBSERVED | frames 2
  80.0–  84.0 | person                 | pouring      | breadcrumbs into bowl              | W03 | MULTI_WINDOW_OBSERVED | frames 2
  82.0–  88.0 | person                 | stirring     | breadcrumbs in bowl                | W02,W03 | MULTI_WINDOW_OBSERVED/SINGLE_WINDOW_OBSERVED | frames 3
       members: W02_E010(82–86), W03_E004(84–88)
  88.0–  92.0 | person                 | transferring | ground beef into bowl              | W03 | SINGLE_WINDOW_OBSERVED | frames 2
  92.0–  96.0 | person                 | adding       | onion and crab stick to bowl       | W03 | SINGLE_WINDOW_OBSERVED | frames 2
  96.0– 100.0 | person                 | mixing       | ingredients in bowl                | W03 | MULTI_WINDOW_OBSERVED | frames 2
  96.0– 100.0 | person                 | stirring     | mixture in a bowl with chopsticks  | W04 | MULTI_WINDOW_OBSERVED | frames 2
 100.0– 104.0 | person                 | cooking      | mixture in pan                     | W03 | MULTI_WINDOW_OBSERVED | frames 2
 100.0– 103.0 | person                 | cooking      | mixture in a pan over direct heat  | W04 | MULTI_WINDOW_OBSERVED | frames 2
```

transition 후보:

```
  28.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  31.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  34.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  37.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  40.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  43.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  46.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  48.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  49.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  52.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  52.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  55.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  55.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  58.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  62.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  66.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  70.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  72.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  74.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  76.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  78.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  80.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  82.0초  UNRESOLVED              gap 0.0초  actor_changed=False
  88.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  92.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  96.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
  96.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 100.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 100.0초  UNRESOLVED              gap 0.0초  actor_changed=False
```

### CH02  103.0 – 185.0초  (22 group · 창 W03, W04, W05, W06, W07)

```
boundary 신호  actor_changed=False · sustained_content_change=True
```

```
 103.0– 123.0 | person                 | peeling      | potato with a peeler               | W04 | MULTI_WINDOW_OBSERVED | frames 10
 104.0– 120.0 | person                 | peeling      | potatoes with peeler               | W03 | MULTI_WINDOW_OBSERVED | frames 8
 120.0– 125.0 | person                 | grating      | potato                             | W05 | MULTI_WINDOW_OBSERVED | frames 3
 123.0– 127.0 | person                 | mixing       | mixture in a bowl with chopsticks  | W04 | MULTI_WINDOW_OBSERVED | frames 2
 125.0– 130.0 | person                 | mixing       | potato mixture                     | W05 | MULTI_WINDOW_OBSERVED | frames 2
 127.0– 131.0 | person                 | forming      | mixture into balls                 | W04 | MULTI_WINDOW_OBSERVED | frames 2
 130.0– 135.0 | person                 | forming      | potato balls                       | W05 | MULTI_WINDOW_OBSERVED | frames 3
 131.0– 144.0 | person                 | placing      | balls on a plate                   | W04 | MULTI_WINDOW_OBSERVED | frames 6
 135.0– 140.0 | person                 | coating      | potato balls                       | W05 | MULTI_WINDOW_OBSERVED | frames 2
 140.0– 145.0 | person                 | placing      | potato balls                       | W05 | MULTI_WINDOW_OBSERVED | frames 3
 144.0– 149.0 | person                 | pouring      | liquid into a bowl                 | W06 | MULTI_WINDOW_OBSERVED | frames 3
 145.0– 168.0 | person                 | coating      | potato balls                       | W05 | MULTI_WINDOW_OBSERVED | frames 11
 149.0– 153.0 | person                 | mixing       | ingredients in a bowl              | W06 | MULTI_WINDOW_OBSERVED | frames 2
 153.0– 157.0 | person                 | dipping      | potato dough in egg mixture        | W06 | MULTI_WINDOW_OBSERVED | frames 2
 157.0– 161.0 | person                 | coating      | potato dough in breadcrumbs        | W06 | MULTI_WINDOW_OBSERVED | frames 2
 161.0– 165.0 | person                 | placing      | coated potato dough on a plate     | W06 | MULTI_WINDOW_OBSERVED | frames 2
 165.0– 170.0 | person                 | coating      | potato dough in breadcrumbs        | W06 | MULTI_WINDOW_OBSERVED | frames 2
 168.0– 175.0 | person                 | coating      | ball in breadcrumbs                | W07 | MULTI_WINDOW_OBSERVED | frames 4
 170.0– 175.0 | person                 | placing      | coated potato dough on a plate     | W06 | MULTI_WINDOW_OBSERVED | frames 3
 175.0– 180.0 | person                 | coating      | potato dough in breadcrumbs        | W06 | MULTI_WINDOW_OBSERVED | frames 2
 175.0– 184.0 | person                 | placing      | coated balls on plate              | W07 | MULTI_WINDOW_OBSERVED | frames 4
 180.0– 185.0 | person                 | placing      | coated potato dough on a plate     | W06 | MULTI_WINDOW_OBSERVED | frames 3
```

transition 후보:

```
 104.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 120.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 123.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 125.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 127.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 130.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 131.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 135.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 140.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 144.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 145.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 149.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 153.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 157.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 161.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 165.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 168.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 170.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 175.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 175.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 180.0초  UNRESOLVED              gap 0.0초  actor_changed=False
```

### CH03  184.0 – 264.0초  (18 group · 창 W06, W07, W08, W09, W10)

```
boundary 신호  actor_changed=False · sustained_content_change=True
```

```
 184.0– 187.0 | person                 | pouring      | cream into pan                     | W07 | MULTI_WINDOW_OBSERVED | frames 2
 185.0– 192.0 | person                 | pouring      | liquid into a pan                  | W06 | MULTI_WINDOW_OBSERVED | frames 3
 187.0– 190.0 | person                 | stirring     | onions in pan                      | W07 | MULTI_WINDOW_OBSERVED | frames 1
 190.0– 193.0 | person                 | pouring      | sauce into pan                     | W07 | MULTI_WINDOW_OBSERVED | frames 2
 192.0– 195.0 | person                 | pouring      | powder from a bottle into a pan    | W08 | MULTI_WINDOW_OBSERVED | frames 2
 193.0– 202.0 | person                 | pouring      | liquid into pan                    | W07 | MULTI_WINDOW_OBSERVED | frames 4
 195.0– 240.0 | person                 | pouring      | liquid from a bottle into a pan    | W08 | MULTI_WINDOW_OBSERVED | frames 22
 202.0– 205.0 | person                 | pouring      | cream into bowl                    | W07 | MULTI_WINDOW_OBSERVED | frames 2
 205.0– 216.0 | person                 | mixing       | cream in bowl                      | W07 | MULTI_WINDOW_OBSERVED | frames 5
 216.0– 220.0 | person                 | pouring      | mashed potatoes into a bowl with a | W09 | MULTI_WINDOW_OBSERVED | frames 2
 220.0– 224.0 | person                 | mixing       | mashed potatoes with a hand mixer  | W09 | MULTI_WINDOW_OBSERVED | frames 2
 224.0– 228.0 | person                 | transferring | mashed potatoes into a piping bag  | W09 | MULTI_WINDOW_OBSERVED | frames 2
 228.0– 232.0 | person                 | placing      | potato croquettes on a wire rack   | W09 | MULTI_WINDOW_OBSERVED | frames 2
 232.0– 236.0 | person                 | pouring      | oil into a baking tray             | W09 | MULTI_WINDOW_OBSERVED | frames 2
 236.0– 264.0 | person                 | pouring      | butter into a bowl                 | W09 | MULTI_WINDOW_OBSERVED | frames 14
 240.0– 245.0 | person                 | serving      | noodles                            | W10 | MULTI_WINDOW_OBSERVED | frames 3
 245.0– 255.0 | person                 | serving      | potato cream                       | W10 | MULTI_WINDOW_OBSERVED | frames 5
 255.0– 260.0 | person                 | serving      | herbs                              | W10 | MULTI_WINDOW_OBSERVED | frames 2
```

transition 후보:

```
 185.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 187.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 190.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 192.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 193.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 195.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 202.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 205.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 216.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 220.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 224.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 228.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 232.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 236.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 240.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 245.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 255.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
```

### CH04  260.0 – 360.0초  (15 group · 창 W10, W11, W12, W13)

```
boundary 신호  actor_changed=False · sustained_content_change=True
```

```
 260.0– 288.0 | person                 | eating       | noodles                            | W10 | MULTI_WINDOW_OBSERVED | frames 14
 264.0– 272.0 | person                 | using chopst | lifting noodles from a bowl        | W11 | MULTI_WINDOW_OBSERVED | frames 4
 272.0– 280.0 | person                 | eating       | noodles with a spoon               | W11 | MULTI_WINDOW_OBSERVED | frames 4
 280.0– 288.0 | person                 | using chopst | picking up a breaded food item     | W11 | MULTI_WINDOW_OBSERVED | frames 4
 288.0– 296.0 | person                 | eating       | breaded food item                  | W11 | MULTI_WINDOW_OBSERVED | frames 4
 288.0– 293.0 | person                 | breaking apa | breaded potato ball                | W12 | MULTI_WINDOW_OBSERVED | frames 3
 293.0– 297.0 | person                 | eating       | breaded potato ball                | W12 | MULTI_WINDOW_OBSERVED | frames 2
 296.0– 304.0 | person                 | using chopst | picking up a breaded food item     | W11 | MULTI_WINDOW_OBSERVED | frames 4
 297.0– 301.0 | person                 | eating       | curry udon                         | W12 | MULTI_WINDOW_OBSERVED | frames 2
 301.0– 305.0 | person                 | eating       | breaded potato ball                | W12 | MULTI_WINDOW_OBSERVED | frames 2
 304.0– 312.0 | person                 | eating       | breaded food item                  | W11 | MULTI_WINDOW_OBSERVED | frames 4
 305.0– 310.0 | person                 | drinking     | water                              | W12 | MULTI_WINDOW_OBSERVED | frames 2
 310.0– 336.0 | person                 | eating       | curry udon                         | W12 | MULTI_WINDOW_OBSERVED | frames 13
 312.0– 317.0 | a person               | eating       | cream curry udon                   | W13 | MULTI_WINDOW_OBSERVED | frames 3
 317.0– 360.0 | a person               | eating       | rice with kimchi                   | W13 | MULTI_WINDOW_OBSERVED | frames 21
```

transition 후보:

```
 264.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 272.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 280.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 288.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 288.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 293.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 296.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 297.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 301.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 304.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 305.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 310.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 312.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 317.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
```

### CH05  336.0 – 400.0초  (13 group · 창 W14, W15, W16)

```
boundary 신호  actor_changed=True · sustained_content_change=False
```

```
 336.0– 348.0 | person                 | eating       | noodles with chopsticks and spoon  | W14 | MULTI_WINDOW_OBSERVED | frames 6
 348.0– 376.0 | person                 | preparing fo | gimbal with gloves                 | W14 | MULTI_WINDOW_OBSERVED | frames 14
 360.0– 365.0 | person                 | placing      | sushi roll on cutting board        | W15 | MULTI_WINDOW_OBSERVED | frames 3
 365.0– 370.0 | person                 | placing      | sushi rolls on plate               | W15 | MULTI_WINDOW_OBSERVED | frames 2
 370.0– 375.0 | person                 | arranging    | sushi rolls on plate               | W15 | MULTI_WINDOW_OBSERVED | frames 3
 375.0– 380.0 | person                 | placing      | bowl of soup on table              | W15 | MULTI_WINDOW_OBSERVED | frames 2
 376.0– 380.0 | person                 | eating       | food with spoon                    | W14 | MULTI_WINDOW_OBSERVED | frames 2
 380.0– 384.0 | person                 | preparing fo | chicken with sauce                 | W14 | MULTI_WINDOW_OBSERVED | frames 2
 380.0– 385.0 | person                 | placing      | chicken legs in steamer            | W15 | MULTI_WINDOW_OBSERVED | frames 3
 384.0– 389.0 | person                 | placing      | noodles in a bowl                  | W16 | MULTI_WINDOW_OBSERVED | frames 3
 385.0– 390.0 | person                 | placing      | noodles in bowl                    | W15 | MULTI_WINDOW_OBSERVED | frames 2
 389.0– 400.0 | person                 | placing      | chicken legs in a bowl             | W16 | MULTI_WINDOW_OBSERVED | frames 5
 390.0– 400.0 | person                 | placing      | chicken legs in bowl               | W15 | MULTI_WINDOW_OBSERVED | frames 5
```

transition 후보:

```
 348.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 360.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 365.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 370.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 375.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 376.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 380.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 380.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 384.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 385.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 389.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 390.0초  UNRESOLVED              gap 0.0초  actor_changed=False
```

### CH06  400.0 – 460.0초  (16 group · 창 W15, W16, W17, W18, W19)

```
boundary 신호  actor_changed=False · sustained_content_change=True
```

```
 400.0– 405.0 | person                 | holding      | orange cloth                       | W15 | MULTI_WINDOW_OBSERVED | frames 3
 400.0– 408.0 | person                 | holding      | orange pajama pants                | W16 | MULTI_WINDOW_OBSERVED | frames 4
 405.0– 408.0 | person                 | holding      | pink cloth                         | W15 | MULTI_WINDOW_OBSERVED | frames 1
 408.0– 412.0 | person                 | pulling      | elastic band from pajama pants     | W16 | MULTI_WINDOW_OBSERVED | frames 2
 408.0– 413.0 | person                 | holding      | elastic band and orange fabric     | W17 | MULTI_WINDOW_OBSERVED | frames 3
 412.0– 416.0 | person                 | holding      | elastic band                       | W16 | MULTI_WINDOW_OBSERVED | frames 2
 413.0– 420.0 | person                 | holding      | orange fabric with pattern         | W17 | MULTI_WINDOW_OBSERVED | frames 3
 416.0– 420.0 | person                 | holding      | orange pajama pants                | W16 | MULTI_WINDOW_OBSERVED | frames 2
 420.0– 432.0 | person                 | placing      | orange pajama pants in a drawer    | W16 | MULTI_WINDOW_OBSERVED | frames 6
 420.0– 426.0 | person                 | placing      | orange fabric on drawer            | W17 | MULTI_WINDOW_OBSERVED | frames 3
 426.0– 433.0 | person                 | placing      | white elastic band on sewing machi | W17 | MULTI_WINDOW_OBSERVED | frames 4
 432.0– 440.0 | person                 | sewing       | orange fabric with green dots      | W18 | MULTI_WINDOW_OBSERVED | frames 4
 433.0– 440.0 | person                 | sewing       | orange fabric with pattern         | W17 | MULTI_WINDOW_OBSERVED | frames 3
 440.0– 456.0 | person                 | holding      | orange fabric with pattern         | W17 | MULTI_WINDOW_OBSERVED | frames 8
 440.0– 460.0 | person                 | holding up   | orange fabric with green dots      | W18 | MULTI_WINDOW_OBSERVED | frames 10
 456.0– 460.0 | hand                   | placing      | crispy ball on plate               | W19 | MULTI_WINDOW_OBSERVED | frames 2
```

transition 후보:

```
 400.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 405.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 408.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 408.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 412.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 413.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 416.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 420.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 420.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 426.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 432.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 433.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 440.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 440.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 456.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
```

### CH07  460.0 – 529.0초  (22 group · 창 W18, W19, W20, W21)

```
boundary 신호  actor_changed=True · sustained_content_change=True
```

```
 460.0– 470.0 | person                 | chopping     | tomato                             | W18 | MULTI_WINDOW_OBSERVED | frames 5
 460.0– 464.0 | hand                   | chopping     | tomato                             | W19 | MULTI_WINDOW_OBSERVED | frames 2
 464.0– 468.0 | hand                   | cracking     | egg into measuring cup             | W19 | MULTI_WINDOW_OBSERVED | frames 2
 468.0– 472.0 | hand                   | stirring     | egg mixture in measuring cup       | W19 | MULTI_WINDOW_OBSERVED | frames 2
 470.0– 475.0 | person                 | pouring      | egg yolk into measuring cup        | W18 | MULTI_WINDOW_OBSERVED | frames 3
 472.0– 476.0 | hand                   | pouring      | egg mixture into pan               | W19 | MULTI_WINDOW_OBSERVED | frames 2
 475.0– 480.0 | person                 | stirring     | egg yolk in measuring cup          | W18 | MULTI_WINDOW_OBSERVED | frames 2
 476.0– 480.0 | hand                   | stirring     | egg mixture in pan                 | W19 | MULTI_WINDOW_OBSERVED | frames 2
 480.0– 484.0 | hand                   | transferring | egg mixture onto plate             | W19 | MULTI_WINDOW_OBSERVED | frames 2
 480.0– 483.0 | woman                  | pouring      | sauce onto food                    | W20 | MULTI_WINDOW_OBSERVED | frames 2
 483.0– 486.0 | woman                  | pouring      | olive oil onto tofu                | W20 | MULTI_WINDOW_OBSERVED | frames 1
 484.0– 488.0 | hand                   | pouring      | olive oil onto tofu                | W19 | MULTI_WINDOW_OBSERVED | frames 2
 486.0– 528.0 | woman                  | sprinkling   | black pepper on food               | W20 | MULTI_WINDOW_OBSERVED | frames 21
 488.0– 492.0 | hand                   | placing      | tofu on plate                      | W19 | MULTI_WINDOW_OBSERVED | frames 2
 492.0– 496.0 | hand                   | placing      | shredded cabbage on plate          | W19 | MULTI_WINDOW_OBSERVED | frames 2
 496.0– 500.0 | person                 | tying        | hair into bun                      | W19 | MULTI_WINDOW_OBSERVED | frames 2
 500.0– 504.0 | person                 | adjusting    | hair bun                           | W19 | MULTI_WINDOW_OBSERVED | frames 2
 504.0– 509.0 | a woman                | walking      | through a room                     | W21 | MULTI_WINDOW_OBSERVED | frames 3
 509.0– 513.0 | a woman                | placing      | a small box on a table             | W21 | MULTI_WINDOW_OBSERVED | frames 2
 513.0– 520.0 | a woman                | holding      | two small boxes                    | W21 | MULTI_WINDOW_OBSERVED | frames 3
 520.0– 524.0 | a woman                | placing      | a small pouch on a table           | W21 | MULTI_WINDOW_OBSERVED | frames 2
 524.0– 529.0 | a woman                | wrapping     | a small pouch in a brown paper bag | W21 | MULTI_WINDOW_OBSERVED | frames 3
```

transition 후보:

```
 460.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 464.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 468.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 470.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 472.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 475.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 476.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 480.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 480.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 483.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 484.0초  UNRESOLVED              gap 0.0초  actor_changed=True
 486.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
 488.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
 492.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 496.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=True
 500.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 504.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=True
 509.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 513.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 520.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 524.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
```

### CH08  528.0 – 600.0초  (23 group · 창 W21, W22, W23)

```
boundary 신호  actor_changed=True · sustained_content_change=False
```

```
 528.0– 533.0 | person                 | wrapping     | gift in kraft paper                | W22 | MULTI_WINDOW_OBSERVED | frames 3
 529.0– 533.0 | a woman                | placing      | a stamp on a table                 | W21 | MULTI_WINDOW_OBSERVED | frames 2
 533.0– 541.0 | a woman                | tying        | a ribbon around a wrapped package  | W21 | MULTI_WINDOW_OBSERVED | frames 4
 533.0– 537.0 | person                 | placing      | stamp on kraft paper bag           | W22 | MULTI_WINDOW_OBSERVED | frames 2
 537.0– 541.0 | person                 | tying        | ribbon around kraft paper bag      | W22 | MULTI_WINDOW_OBSERVED | frames 2
 541.0– 552.0 | a woman                | holding      | a wrapped package                  | W21 | MULTI_WINDOW_OBSERVED | frames 5
 541.0– 545.0 | person                 | adjusting    | bow on kraft paper bag             | W22 | MULTI_WINDOW_OBSERVED | frames 2
 545.0– 550.0 | person                 | holding      | wrapped gift                       | W22 | MULTI_WINDOW_OBSERVED | frames 2
 550.0– 555.0 | person                 | unfolding    | fabric                             | W22 | MULTI_WINDOW_OBSERVED | frames 3
 552.0– 557.0 | person                 | holding and  | white fabric                       | W23 | MULTI_WINDOW_OBSERVED | frames 3
 555.0– 560.0 | person                 | putting on   | fabric                             | W22 | MULTI_WINDOW_OBSERVED | frames 2
 557.0– 561.0 | person                 | placing fabr | white fabric                       | W23 | MULTI_WINDOW_OBSERVED | frames 2
 560.0– 565.0 | person                 | putting on   | handbag                            | W22 | MULTI_WINDOW_OBSERVED | frames 3
 561.0– 565.0 | person                 | picking up h | brown handbag                      | W23 | MULTI_WINDOW_OBSERVED | frames 2
 565.0– 570.0 | person                 | taking photo | mirror                             | W22 | MULTI_WINDOW_OBSERVED | frames 2
 565.0– 573.0 | person                 | taking mirro | camera                             | W23 | MULTI_WINDOW_OBSERVED | frames 4
 570.0– 576.0 | person                 | adjusting    | clothing                           | W22 | MULTI_WINDOW_OBSERVED | frames 3
 573.0– 580.0 | person                 | adjusting cl | white shirt and shorts             | W23 | MULTI_WINDOW_OBSERVED/SINGLE_WINDOW_OBSERVED | frames 3
 580.0– 585.0 | person                 | looking at p | phone displaying weather           | W23 | SINGLE_WINDOW_OBSERVED | frames 3
 585.0– 590.0 | person                 | walking thro | train window showing cityscape     | W23 | SINGLE_WINDOW_OBSERVED | frames 2
 590.0– 593.0 | person                 | looking at t | train station sign with text       | W23 | SINGLE_WINDOW_OBSERVED | frames 2
 593.0– 597.0 | person                 | walking outs | building with signage              | W23 | SINGLE_WINDOW_OBSERVED | frames 2
 597.0– 600.0 | person                 | entering sho | shop entrance with sign            | W23 | SINGLE_WINDOW_OBSERVED | frames 1
```

transition 후보:

```
 529.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
 533.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 533.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
 537.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 541.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=True
 541.0초  POSSIBLE_CONFLICT       gap 0.0초  actor_changed=True
 545.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 550.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 552.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 555.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 557.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 560.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 561.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 565.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 565.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 570.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 573.0초  UNRESOLVED              gap 0.0초  actor_changed=False
 580.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 585.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 590.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 593.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
 597.0초  POSSIBLE_TRANSITION     gap 0.0초  actor_changed=False
```

## chapter 경계 후보 (억제된 것 포함)

```
  40.0초  G006  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  43.0초  G007  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  49.0초  G010  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  52.0초  G012  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  55.0초  G013  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  55.0초  G014  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  62.0초  G016  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
  70.0초  G018  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 103.0초  G031  actor_changed=False sustained=True
 123.0초  G034  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 144.0초  G041  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 184.0초  G053  actor_changed=False sustained=True
 228.0초  G065  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 232.0초  G066  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 240.0초  G068  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 260.0초  G071  actor_changed=False sustained=True
 305.0초  G082  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 312.0초  G084  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 336.0초  G086  actor_changed=True sustained=False
 348.0초  G087  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 360.0초  G088  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 376.0초  G092  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 400.0초  G099  actor_changed=False sustained=True
 456.0초  G114  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 460.0초  G115  actor_changed=True sustained=True
 460.0초  G116  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 464.0초  G117  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 470.0초  G119  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 472.0초  G120  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 475.0초  G121  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 476.0초  G122  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 480.0초  G124  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 484.0초  G126  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 486.0초  G127  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 488.0초  G128  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 496.0초  G130  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 504.0초  G132  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 509.0초  G133  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 528.0초  G137  actor_changed=True sustained=False
 529.0초  G138  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 533.0초  G139  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 533.0초  G140  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 541.0초  G142  actor_changed=True sustained=True  (MIN_CHAPTER_SEC로 억제)
 541.0초  G143  actor_changed=True sustained=False  (MIN_CHAPTER_SEC로 억제)
 550.0초  G145  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 565.0초  G151  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 570.0초  G153  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 580.0초  G155  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
 585.0초  G156  actor_changed=False sustained=True  (MIN_CHAPTER_SEC로 억제)
```

executor는 chapter 최종 경계·semantic 판정을 확정하지 않았다.
