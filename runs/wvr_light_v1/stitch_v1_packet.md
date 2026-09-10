# STITCHING_SHADOW_V1 blinded overlap packet

사전등록: `docs/preregistration/WVR_OVERLAP_EVENT_STITCHING_SHADOW_V1_2026-09-10.md`

```
인접 창의 공유 24초 overlap 22개다. 각 overlap의 두 창 출력은
Arm A · Arm B로 가려져 있고 어느 쪽이 앞선 창인지는 판정 기록 전까지
공개되지 않는다. event는 공유 구간으로 clip해 보여주며 원본 구간도 함께 적었다.

비교 단위는 event 한 줄이 아니라 **overlap 안의 event sequence 전체**다.
판정 기준은 문자열 일치가 아니라 report-material contradiction이다.
  예) 자른다 vs 섞는다 → 연속 행동일 수 있다
      요리한다 vs 옷을 재봉한다 (같은 시각) → material conflict

relation 어휘   SAME_EVENT · CONTINUATION · TRANSITION · CONFLICT ·
               UNRESOLVED
상위 판정        STITCHABLE · MATERIAL_CONFLICT · UNRESOLVED
executor는 어느 판정도 채우지 않았다.
```

## O02  48–72초  (공유 프레임 12개: 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70)

### Arm A  (event 7개)

```
  48.0–  52.0 | person               | placing        | bread pieces into blender
  52.0–  55.0 | person               | placing        | lid on blender
  55.0–  58.0 | person               | pouring        | oil into bowl of breadcrumbs
  58.0–  62.0 | person               | stirring       | breadcrumbs with oil
  62.0–  66.0 | person               | chopping       | onion on cutting board
  66.0–  70.0 | person               | chopping       | carrot on cutting board
  70.0–  72.0 | person               | placing        | ground beef into bowl   (원본 70.0–74.0)
```

### Arm B  (event 4개)

```
  48.0–  49.0 | person               | blending       | potato slices   (원본 46.0–49.0)
  49.0–  52.0 | person               | pouring        | oil into bowl with curry powder
  52.0–  55.0 | person               | mixing         | curry powder and oil
  55.0–  72.0 | person               | chopping       | onion
```

## O03  72–96초  (공유 프레임 12개: 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94)

### Arm A  (event 4개)

```
  72.0–  74.0 | person               | placing        | ground beef into bowl   (원본 70.0–74.0)
  74.0–  78.0 | person               | placing        | onion and carrot into bowl with beef
  78.0–  82.0 | person               | transferring   | toasted breadcrumbs into bowl
  82.0–  86.0 | person               | stirring       | breadcrumbs in bowl
```

### Arm B  (event 6개)

```
  72.0–  76.0 | person               | peeling        | carrot
  76.0–  80.0 | person               | placing        | lid on pot
  80.0–  84.0 | person               | pouring        | breadcrumbs into bowl
  84.0–  88.0 | person               | stirring       | breadcrumbs in bowl
  88.0–  92.0 | person               | transferring   | ground beef into bowl
  92.0–  96.0 | person               | adding         | onion and crab stick to bowl
```

## O04  96–120초  (공유 프레임 12개: 96, 98, 100, 102, 104, 106, 108, 110, 112, 114, 116, 118)

### Arm A  (event 3개)

```
  96.0– 100.0 | person               | stirring       | mixture in a bowl with chopsticks
 100.0– 103.0 | person               | cooking        | mixture in a pan over direct heat
 103.0– 120.0 | person               | peeling        | potato with a peeler   (원본 103.0–123.0)
```

### Arm B  (event 3개)

```
  96.0– 100.0 | person               | mixing         | ingredients in bowl
 100.0– 104.0 | person               | cooking        | mixture in pan
 104.0– 120.0 | person               | peeling        | potatoes with peeler
```

## O05  120–144초  (공유 프레임 12개: 120, 122, 124, 126, 128, 130, 132, 134, 136, 138, 140, 142)

### Arm A  (event 4개)

```
 120.0– 123.0 | person               | peeling        | potato with a peeler   (원본 103.0–123.0)
 123.0– 127.0 | person               | mixing         | mixture in a bowl with chopsticks
 127.0– 131.0 | person               | forming        | mixture into balls
 131.0– 144.0 | person               | placing        | balls on a plate
```

### Arm B  (event 5개)

```
 120.0– 125.0 | person               | grating        | potato
 125.0– 130.0 | person               | mixing         | potato mixture
 130.0– 135.0 | person               | forming        | potato balls
 135.0– 140.0 | person               | coating        | potato balls
 140.0– 144.0 | person               | placing        | potato balls   (원본 140.0–145.0)
```

## O06  144–168초  (공유 프레임 12개: 144, 146, 148, 150, 152, 154, 156, 158, 160, 162, 164, 166)

### Arm A  (event 2개)

```
 144.0– 145.0 | person               | placing        | potato balls   (원본 140.0–145.0)
 145.0– 168.0 | person               | coating        | potato balls
```

### Arm B  (event 6개)

```
 144.0– 149.0 | person               | pouring        | liquid into a bowl
 149.0– 153.0 | person               | mixing         | ingredients in a bowl
 153.0– 157.0 | person               | dipping        | potato dough in egg mixture
 157.0– 161.0 | person               | coating        | potato dough in breadcrumbs
 161.0– 165.0 | person               | placing        | coated potato dough on a plate
 165.0– 168.0 | person               | coating        | potato dough in breadcrumbs   (원본 165.0–170.0)
```

## O07  168–192초  (공유 프레임 12개: 168, 170, 172, 174, 176, 178, 180, 182, 184, 186, 188, 190)

### Arm A  (event 5개)

```
 168.0– 175.0 | person               | coating        | ball in breadcrumbs
 175.0– 184.0 | person               | placing        | coated balls on plate
 184.0– 187.0 | person               | pouring        | cream into pan
 187.0– 190.0 | person               | stirring       | onions in pan
 190.0– 192.0 | person               | pouring        | sauce into pan   (원본 190.0–193.0)
```

### Arm B  (event 5개)

```
 168.0– 170.0 | person               | coating        | potato dough in breadcrumbs   (원본 165.0–170.0)
 170.0– 175.0 | person               | placing        | coated potato dough on a plate
 175.0– 180.0 | person               | coating        | potato dough in breadcrumbs
 180.0– 185.0 | person               | placing        | coated potato dough on a plate
 185.0– 192.0 | person               | pouring        | liquid into a pan
```

## O08  192–216초  (공유 프레임 12개: 192, 194, 196, 198, 200, 202, 204, 206, 208, 210, 212, 214)

### Arm A  (event 4개)

```
 192.0– 193.0 | person               | pouring        | sauce into pan   (원본 190.0–193.0)
 193.0– 202.0 | person               | pouring        | liquid into pan
 202.0– 205.0 | person               | pouring        | cream into bowl
 205.0– 216.0 | person               | mixing         | cream in bowl
```

### Arm B  (event 2개)

```
 192.0– 195.0 | person               | pouring        | powder from a bottle into a pan
 195.0– 216.0 | person               | pouring        | liquid from a bottle into a pan   (원본 195.0–240.0)
```

## O09  216–240초  (공유 프레임 12개: 216, 218, 220, 222, 224, 226, 228, 230, 232, 234, 236, 238)

### Arm A  (event 1개)

```
 216.0– 240.0 | person               | pouring        | liquid from a bottle into a pan   (원본 195.0–240.0)
```

### Arm B  (event 6개)

```
 216.0– 220.0 | person               | pouring        | mashed potatoes into a bowl with a hand mixer
 220.0– 224.0 | person               | mixing         | mashed potatoes with a hand mixer
 224.0– 228.0 | person               | transferring   | mashed potatoes into a piping bag
 228.0– 232.0 | person               | placing        | potato croquettes on a wire rack
 232.0– 236.0 | person               | pouring        | oil into a baking tray
 236.0– 240.0 | person               | pouring        | butter into a bowl   (원본 236.0–264.0)
```

## O10  240–264초  (공유 프레임 12개: 240, 242, 244, 246, 248, 250, 252, 254, 256, 258, 260, 262)

### Arm A  (event 4개)

```
 240.0– 245.0 | person               | serving        | noodles
 245.0– 255.0 | person               | serving        | potato cream
 255.0– 260.0 | person               | serving        | herbs
 260.0– 264.0 | person               | eating         | noodles   (원본 260.0–288.0)
```

### Arm B  (event 1개)

```
 240.0– 264.0 | person               | pouring        | butter into a bowl   (원본 236.0–264.0)
```

## O11  264–288초  (공유 프레임 12개: 264, 266, 268, 270, 272, 274, 276, 278, 280, 282, 284, 286)

### Arm A  (event 3개)

```
 264.0– 272.0 | person               | using chopsticks | lifting noodles from a bowl
 272.0– 280.0 | person               | eating         | noodles with a spoon
 280.0– 288.0 | person               | using chopsticks | picking up a breaded food item
```

### Arm B  (event 1개)

```
 264.0– 288.0 | person               | eating         | noodles   (원본 260.0–288.0)
```

## O12  288–312초  (공유 프레임 12개: 288, 290, 292, 294, 296, 298, 300, 302, 304, 306, 308, 310)

### Arm A  (event 6개)

```
 288.0– 293.0 | person               | breaking apart | breaded potato ball
 293.0– 297.0 | person               | eating         | breaded potato ball
 297.0– 301.0 | person               | eating         | curry udon
 301.0– 305.0 | person               | eating         | breaded potato ball
 305.0– 310.0 | person               | drinking       | water
 310.0– 312.0 | person               | eating         | curry udon   (원본 310.0–336.0)
```

### Arm B  (event 3개)

```
 288.0– 296.0 | person               | eating         | breaded food item
 296.0– 304.0 | person               | using chopsticks | picking up a breaded food item
 304.0– 312.0 | person               | eating         | breaded food item
```

## O13  312–336초  (공유 프레임 12개: 312, 314, 316, 318, 320, 322, 324, 326, 328, 330, 332, 334)

### Arm A  (event 2개)

```
 312.0– 317.0 | a person             | eating         | cream curry udon
 317.0– 336.0 | a person             | eating         | rice with kimchi   (원본 317.0–360.0)
```

### Arm B  (event 1개)

```
 312.0– 336.0 | person               | eating         | curry udon   (원본 310.0–336.0)
```

## O14  336–360초  (공유 프레임 12개: 336, 338, 340, 342, 344, 346, 348, 350, 352, 354, 356, 358)

### Arm A  (event 1개)

```
 336.0– 360.0 | a person             | eating         | rice with kimchi   (원본 317.0–360.0)
```

### Arm B  (event 2개)

```
 336.0– 348.0 | person               | eating         | noodles with chopsticks and spoon
 348.0– 360.0 | person               | preparing food | gimbal with gloves   (원본 348.0–376.0)
```

## O15  360–384초  (공유 프레임 12개: 360, 362, 364, 366, 368, 370, 372, 374, 376, 378, 380, 382)

### Arm A  (event 5개)

```
 360.0– 365.0 | person               | placing        | sushi roll on cutting board
 365.0– 370.0 | person               | placing        | sushi rolls on plate
 370.0– 375.0 | person               | arranging      | sushi rolls on plate
 375.0– 380.0 | person               | placing        | bowl of soup on table
 380.0– 384.0 | person               | placing        | chicken legs in steamer   (원본 380.0–385.0)
```

### Arm B  (event 3개)

```
 360.0– 376.0 | person               | preparing food | gimbal with gloves   (원본 348.0–376.0)
 376.0– 380.0 | person               | eating         | food with spoon
 380.0– 384.0 | person               | preparing food | chicken with sauce
```

## O16  384–408초  (공유 프레임 12개: 384, 386, 388, 390, 392, 394, 396, 398, 400, 402, 404, 406)

### Arm A  (event 5개)

```
 384.0– 385.0 | person               | placing        | chicken legs in steamer   (원본 380.0–385.0)
 385.0– 390.0 | person               | placing        | noodles in bowl
 390.0– 400.0 | person               | placing        | chicken legs in bowl
 400.0– 405.0 | person               | holding        | orange cloth
 405.0– 408.0 | person               | holding        | pink cloth
```

### Arm B  (event 3개)

```
 384.0– 389.0 | person               | placing        | noodles in a bowl
 389.0– 400.0 | person               | placing        | chicken legs in a bowl
 400.0– 408.0 | person               | holding        | orange pajama pants
```

## O17  408–432초  (공유 프레임 12개: 408, 410, 412, 414, 416, 418, 420, 422, 424, 426, 428, 430)

### Arm A  (event 4개)

```
 408.0– 413.0 | person               | holding        | elastic band and orange fabric
 413.0– 420.0 | person               | holding        | orange fabric with pattern
 420.0– 426.0 | person               | placing        | orange fabric on drawer
 426.0– 432.0 | person               | placing        | white elastic band on sewing machine   (원본 426.0–433.0)
```

### Arm B  (event 4개)

```
 408.0– 412.0 | person               | pulling        | elastic band from pajama pants
 412.0– 416.0 | person               | holding        | elastic band
 416.0– 420.0 | person               | holding        | orange pajama pants
 420.0– 432.0 | person               | placing        | orange pajama pants in a drawer
```

## O18  432–456초  (공유 프레임 12개: 432, 434, 436, 438, 440, 442, 444, 446, 448, 450, 452, 454)

### Arm A  (event 2개)

```
 432.0– 440.0 | person               | sewing         | orange fabric with green dots
 440.0– 456.0 | person               | holding up     | orange fabric with green dots   (원본 440.0–460.0)
```

### Arm B  (event 3개)

```
 432.0– 433.0 | person               | placing        | white elastic band on sewing machine   (원본 426.0–433.0)
 433.0– 440.0 | person               | sewing         | orange fabric with pattern
 440.0– 456.0 | person               | holding        | orange fabric with pattern
```

## O19  456–480초  (공유 프레임 12개: 456, 458, 460, 462, 464, 466, 468, 470, 472, 474, 476, 478)

### Arm A  (event 6개)

```
 456.0– 460.0 | hand                 | placing        | crispy ball on plate
 460.0– 464.0 | hand                 | chopping       | tomato
 464.0– 468.0 | hand                 | cracking       | egg into measuring cup
 468.0– 472.0 | hand                 | stirring       | egg mixture in measuring cup
 472.0– 476.0 | hand                 | pouring        | egg mixture into pan
 476.0– 480.0 | hand                 | stirring       | egg mixture in pan
```

### Arm B  (event 4개)

```
 456.0– 460.0 | person               | holding up     | orange fabric with green dots   (원본 440.0–460.0)
 460.0– 470.0 | person               | chopping       | tomato
 470.0– 475.0 | person               | pouring        | egg yolk into measuring cup
 475.0– 480.0 | person               | stirring       | egg yolk in measuring cup
```

## O20  480–504초  (공유 프레임 12개: 480, 482, 484, 486, 488, 490, 492, 494, 496, 498, 500, 502)

### Arm A  (event 6개)

```
 480.0– 484.0 | hand                 | transferring   | egg mixture onto plate
 484.0– 488.0 | hand                 | pouring        | olive oil onto tofu
 488.0– 492.0 | hand                 | placing        | tofu on plate
 492.0– 496.0 | hand                 | placing        | shredded cabbage on plate
 496.0– 500.0 | person               | tying          | hair into bun
 500.0– 504.0 | person               | adjusting      | hair bun
```

### Arm B  (event 3개)

```
 480.0– 483.0 | woman                | pouring        | sauce onto food
 483.0– 486.0 | woman                | pouring        | olive oil onto tofu
 486.0– 504.0 | woman                | sprinkling     | black pepper on food   (원본 486.0–528.0)
```

## O21  504–528초  (공유 프레임 12개: 504, 506, 508, 510, 512, 514, 516, 518, 520, 522, 524, 526)

### Arm A  (event 1개)

```
 504.0– 528.0 | woman                | sprinkling     | black pepper on food   (원본 486.0–528.0)
```

### Arm B  (event 5개)

```
 504.0– 509.0 | a woman              | walking        | through a room
 509.0– 513.0 | a woman              | placing        | a small box on a table
 513.0– 520.0 | a woman              | holding        | two small boxes
 520.0– 524.0 | a woman              | placing        | a small pouch on a table
 524.0– 528.0 | a woman              | wrapping       | a small pouch in a brown paper bag   (원본 524.0–529.0)
```

## O22  528–552초  (공유 프레임 12개: 528, 530, 532, 534, 536, 538, 540, 542, 544, 546, 548, 550)

### Arm A  (event 6개)

```
 528.0– 533.0 | person               | wrapping       | gift in kraft paper
 533.0– 537.0 | person               | placing        | stamp on kraft paper bag
 537.0– 541.0 | person               | tying          | ribbon around kraft paper bag
 541.0– 545.0 | person               | adjusting      | bow on kraft paper bag
 545.0– 550.0 | person               | holding        | wrapped gift
 550.0– 552.0 | person               | unfolding      | fabric   (원본 550.0–555.0)
```

### Arm B  (event 4개)

```
 528.0– 529.0 | a woman              | wrapping       | a small pouch in a brown paper bag   (원본 524.0–529.0)
 529.0– 533.0 | a woman              | placing        | a stamp on a table
 533.0– 541.0 | a woman              | tying          | a ribbon around a wrapped package
 541.0– 552.0 | a woman              | holding        | a wrapped package
```

## O23  552–576초  (공유 프레임 12개: 552, 554, 556, 558, 560, 562, 564, 566, 568, 570, 572, 574)

### Arm A  (event 5개)

```
 552.0– 557.0 | person               | holding and displaying fabric | white fabric
 557.0– 561.0 | person               | placing fabric on table | white fabric
 561.0– 565.0 | person               | picking up handbag | brown handbag
 565.0– 573.0 | person               | taking mirror selfie | camera
 573.0– 576.0 | person               | adjusting clothing | white shirt and shorts   (원본 573.0–580.0)
```

### Arm B  (event 5개)

```
 552.0– 555.0 | person               | unfolding      | fabric   (원본 550.0–555.0)
 555.0– 560.0 | person               | putting on     | fabric
 560.0– 565.0 | person               | putting on     | handbag
 565.0– 570.0 | person               | taking photo   | mirror
 570.0– 576.0 | person               | adjusting      | clothing
```
