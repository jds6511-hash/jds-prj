# SHADOW_V1 blinded overlap packet

사전등록: `docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md`

```
23개 인접 overlap. 각 overlap의 두 출력은 Arm A · Arm B로 가려져 있다.
어느 쪽이 앞선 창인지는 reviewer 판정 전까지 공개되지 않는다.
event는 overlap 범위로 clip해 보여주며 원본 구간은 산출물에 보존돼 있다.
판정값 STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED
자동 매처는 AUDIT_DIAGNOSTIC_ONLY다 — 판정 authority가 아니다.
```

## O01  24–48초  (frame-audit overlap)

### Arm A

```
  24.0–  28.0 | person | selecting | bottle of soy sauce
  28.0–  31.0 | person | selecting | packet of curry
  31.0–  34.0 | person | selecting | bag of potatoes
  34.0–  37.0 | person | placing | potatoes in steamer
  37.0–  40.0 | person | covering | steamer
  40.0–  43.0 | person | pouring | curry powder into bowl
  43.0–  46.0 | person | placing | potato slices in blender
  46.0–  48.0 | person | blending | potato slices  (clipped)
```

### Arm B

```
(겹치는 event 없음)
```

## O02  48–72초

### Arm A

```
  48.0–  49.0 | person | blending | potato slices  (clipped)
  49.0–  52.0 | person | pouring | oil into bowl with curry powder
  52.0–  55.0 | person | mixing | curry powder and oil
  55.0–  72.0 | person | chopping | onion
```

### Arm B

```
  48.0–  52.0 | person | placing | bread pieces into blender
  52.0–  55.0 | person | placing | lid on blender
  55.0–  58.0 | person | pouring | oil into bowl of breadcrumbs
  58.0–  62.0 | person | stirring | breadcrumbs with oil
  62.0–  66.0 | person | chopping | onion on cutting board
  66.0–  70.0 | person | chopping | carrot on cutting board
  70.0–  72.0 | person | placing | ground beef into bowl  (clipped)
```

## O03  72–96초

### Arm A

```
  72.0–  76.0 | person | peeling | carrot
  76.0–  80.0 | person | placing | lid on pot
  80.0–  84.0 | person | pouring | breadcrumbs into bowl
  84.0–  88.0 | person | stirring | breadcrumbs in bowl
  88.0–  92.0 | person | transferring | ground beef into bowl
  92.0–  96.0 | person | adding | onion and crab stick to bowl
```

### Arm B

```
  72.0–  74.0 | person | placing | ground beef into bowl  (clipped)
  74.0–  78.0 | person | placing | onion and carrot into bowl with beef
  78.0–  82.0 | person | transferring | toasted breadcrumbs into bowl
  82.0–  86.0 | person | stirring | breadcrumbs in bowl
```

## O04  96–120초  (frame-audit overlap)

### Arm A

```
  96.0– 100.0 | person | mixing | ingredients in bowl
 100.0– 104.0 | person | cooking | mixture in pan
 104.0– 120.0 | person | peeling | potatoes with peeler
```

### Arm B

```
  96.0– 100.0 | person | stirring | mixture in a bowl with chopsticks
 100.0– 103.0 | person | cooking | mixture in a pan over direct heat
 103.0– 120.0 | person | peeling | potato with a peeler  (clipped)
```

## O05  120–144초  (frame-audit overlap)

### Arm A

```
 120.0– 125.0 | person | grating | potato
 125.0– 130.0 | person | mixing | potato mixture
 130.0– 135.0 | person | forming | potato balls
 135.0– 140.0 | person | coating | potato balls
 140.0– 144.0 | person | placing | potato balls  (clipped)
```

### Arm B

```
 120.0– 123.0 | person | peeling | potato with a peeler  (clipped)
 123.0– 127.0 | person | mixing | mixture in a bowl with chopsticks
 127.0– 131.0 | person | forming | mixture into balls
 131.0– 144.0 | person | placing | balls on a plate
```

## O06  144–168초

### Arm A

```
 144.0– 145.0 | person | placing | potato balls  (clipped)
 145.0– 168.0 | person | coating | potato balls
```

### Arm B

```
 144.0– 149.0 | person | pouring | liquid into a bowl
 149.0– 153.0 | person | mixing | ingredients in a bowl
 153.0– 157.0 | person | dipping | potato dough in egg mixture
 157.0– 161.0 | person | coating | potato dough in breadcrumbs
 161.0– 165.0 | person | placing | coated potato dough on a plate
 165.0– 168.0 | person | coating | potato dough in breadcrumbs  (clipped)
```

## O07  168–192초

### Arm A

```
 168.0– 175.0 | person | coating | ball in breadcrumbs
 175.0– 184.0 | person | placing | coated balls on plate
 184.0– 187.0 | person | pouring | cream into pan
 187.0– 190.0 | person | stirring | onions in pan
 190.0– 192.0 | person | pouring | sauce into pan  (clipped)
```

### Arm B

```
 168.0– 170.0 | person | coating | potato dough in breadcrumbs  (clipped)
 170.0– 175.0 | person | placing | coated potato dough on a plate
 175.0– 180.0 | person | coating | potato dough in breadcrumbs
 180.0– 185.0 | person | placing | coated potato dough on a plate
 185.0– 192.0 | person | pouring | liquid into a pan
```

## O08  192–216초

### Arm A

```
 192.0– 195.0 | person | pouring | powder from a bottle into a pan
 195.0– 216.0 | person | pouring | liquid from a bottle into a pan  (clipped)
```

### Arm B

```
 192.0– 193.0 | person | pouring | sauce into pan  (clipped)
 193.0– 202.0 | person | pouring | liquid into pan
 202.0– 205.0 | person | pouring | cream into bowl
 205.0– 216.0 | person | mixing | cream in bowl
```

## O09  216–240초

### Arm A

```
 216.0– 220.0 | person | pouring | mashed potatoes into a bowl with a hand mixer
 220.0– 224.0 | person | mixing | mashed potatoes with a hand mixer
 224.0– 228.0 | person | transferring | mashed potatoes into a piping bag
 228.0– 232.0 | person | placing | potato croquettes on a wire rack
 232.0– 236.0 | person | pouring | oil into a baking tray
 236.0– 240.0 | person | pouring | butter into a bowl  (clipped)
```

### Arm B

```
 216.0– 240.0 | person | pouring | liquid from a bottle into a pan  (clipped)
```

## O10  240–264초

### Arm A

```
 240.0– 264.0 | person | pouring | butter into a bowl  (clipped)
```

### Arm B

```
 240.0– 245.0 | person | serving | noodles
 245.0– 255.0 | person | serving | potato cream
 255.0– 260.0 | person | serving | herbs
 260.0– 264.0 | person | eating | noodles  (clipped)
```

## O11  264–288초

### Arm A

```
 264.0– 288.0 | person | eating | noodles  (clipped)
```

### Arm B

```
 264.0– 272.0 | person | using chopsticks | lifting noodles from a bowl
 272.0– 280.0 | person | eating | noodles with a spoon
 280.0– 288.0 | person | using chopsticks | picking up a breaded food item
```

## O12  288–312초  (frame-audit overlap)

### Arm A

```
 288.0– 296.0 | person | eating | breaded food item
 296.0– 304.0 | person | using chopsticks | picking up a breaded food item
 304.0– 312.0 | person | eating | breaded food item
```

### Arm B

```
 288.0– 293.0 | person | breaking apart | breaded potato ball
 293.0– 297.0 | person | eating | breaded potato ball
 297.0– 301.0 | person | eating | curry udon
 301.0– 305.0 | person | eating | breaded potato ball
 305.0– 310.0 | person | drinking | water
 310.0– 312.0 | person | eating | curry udon  (clipped)
```

## O13  312–336초

### Arm A

```
 312.0– 317.0 | a person | eating | cream curry udon
 317.0– 336.0 | a person | eating | rice with kimchi  (clipped)
```

### Arm B

```
 312.0– 336.0 | person | eating | curry udon  (clipped)
```

## O14  336–360초

### Arm A

```
 336.0– 348.0 | person | eating | noodles with chopsticks and spoon
 348.0– 360.0 | person | preparing food | gimbal with gloves  (clipped)
```

### Arm B

```
 336.0– 360.0 | a person | eating | rice with kimchi  (clipped)
```

## O15  360–384초

### Arm A

```
 360.0– 376.0 | person | preparing food | gimbal with gloves  (clipped)
 376.0– 380.0 | person | eating | food with spoon
 380.0– 384.0 | person | preparing food | chicken with sauce
```

### Arm B

```
 360.0– 365.0 | person | placing | sushi roll on cutting board
 365.0– 370.0 | person | placing | sushi rolls on plate
 370.0– 375.0 | person | arranging | sushi rolls on plate
 375.0– 380.0 | person | placing | bowl of soup on table
 380.0– 384.0 | person | placing | chicken legs in steamer  (clipped)
```

## O16  384–408초

### Arm A

```
 384.0– 385.0 | person | placing | chicken legs in steamer  (clipped)
 385.0– 390.0 | person | placing | noodles in bowl
 390.0– 400.0 | person | placing | chicken legs in bowl
 400.0– 405.0 | person | holding | orange cloth
 405.0– 408.0 | person | holding | pink cloth
```

### Arm B

```
 384.0– 389.0 | person | placing | noodles in a bowl
 389.0– 400.0 | person | placing | chicken legs in a bowl
 400.0– 408.0 | person | holding | orange pajama pants
```

## O17  408–432초

### Arm A

```
 408.0– 413.0 | person | holding | elastic band and orange fabric
 413.0– 420.0 | person | holding | orange fabric with pattern
 420.0– 426.0 | person | placing | orange fabric on drawer
 426.0– 432.0 | person | placing | white elastic band on sewing machine  (clipped)
```

### Arm B

```
 408.0– 412.0 | person | pulling | elastic band from pajama pants
 412.0– 416.0 | person | holding | elastic band
 416.0– 420.0 | person | holding | orange pajama pants
 420.0– 432.0 | person | placing | orange pajama pants in a drawer
```

## O18  432–456초  (frame-audit overlap)

### Arm A

```
 432.0– 433.0 | person | placing | white elastic band on sewing machine  (clipped)
 433.0– 440.0 | person | sewing | orange fabric with pattern
 440.0– 456.0 | person | holding | orange fabric with pattern
```

### Arm B

```
 432.0– 440.0 | person | sewing | orange fabric with green dots
 440.0– 456.0 | person | holding up | orange fabric with green dots  (clipped)
```

## O19  456–480초  (frame-audit overlap)

### Arm A

```
 456.0– 460.0 | person | holding up | orange fabric with green dots  (clipped)
 460.0– 470.0 | person | chopping | tomato
 470.0– 475.0 | person | pouring | egg yolk into measuring cup
 475.0– 480.0 | person | stirring | egg yolk in measuring cup
```

### Arm B

```
 456.0– 460.0 | hand | placing | crispy ball on plate
 460.0– 464.0 | hand | chopping | tomato
 464.0– 468.0 | hand | cracking | egg into measuring cup
 468.0– 472.0 | hand | stirring | egg mixture in measuring cup
 472.0– 476.0 | hand | pouring | egg mixture into pan
 476.0– 480.0 | hand | stirring | egg mixture in pan
```

## O20  480–504초

### Arm A

```
 480.0– 483.0 | woman | pouring | sauce onto food
 483.0– 486.0 | woman | pouring | olive oil onto tofu
 486.0– 504.0 | woman | sprinkling | black pepper on food  (clipped)
```

### Arm B

```
 480.0– 484.0 | hand | transferring | egg mixture onto plate
 484.0– 488.0 | hand | pouring | olive oil onto tofu
 488.0– 492.0 | hand | placing | tofu on plate
 492.0– 496.0 | hand | placing | shredded cabbage on plate
 496.0– 500.0 | person | tying | hair into bun
 500.0– 504.0 | person | adjusting | hair bun
```

## O21  504–528초

### Arm A

```
 504.0– 528.0 | woman | sprinkling | black pepper on food  (clipped)
```

### Arm B

```
 504.0– 509.0 | a woman | walking | through a room
 509.0– 513.0 | a woman | placing | a small box on a table
 513.0– 520.0 | a woman | holding | two small boxes
 520.0– 524.0 | a woman | placing | a small pouch on a table
 524.0– 528.0 | a woman | wrapping | a small pouch in a brown paper bag  (clipped)
```

## O22  528–552초

### Arm A

```
 528.0– 533.0 | person | wrapping | gift in kraft paper
 533.0– 537.0 | person | placing | stamp on kraft paper bag
 537.0– 541.0 | person | tying | ribbon around kraft paper bag
 541.0– 545.0 | person | adjusting | bow on kraft paper bag
 545.0– 550.0 | person | holding | wrapped gift
 550.0– 552.0 | person | unfolding | fabric  (clipped)
```

### Arm B

```
 528.0– 529.0 | a woman | wrapping | a small pouch in a brown paper bag  (clipped)
 529.0– 533.0 | a woman | placing | a stamp on a table
 533.0– 541.0 | a woman | tying | a ribbon around a wrapped package
 541.0– 552.0 | a woman | holding | a wrapped package
```

## O23  552–576초  (frame-audit overlap)

### Arm A

```
 552.0– 557.0 | person | holding and displaying fabric | white fabric
 557.0– 561.0 | person | placing fabric on table | white fabric
 561.0– 565.0 | person | picking up handbag | brown handbag
 565.0– 573.0 | person | taking mirror selfie | camera
 573.0– 576.0 | person | adjusting clothing | white shirt and shorts  (clipped)
```

### Arm B

```
 552.0– 555.0 | person | unfolding | fabric  (clipped)
 555.0– 560.0 | person | putting on | fabric
 560.0– 565.0 | person | putting on | handbag
 565.0– 570.0 | person | taking photo | mirror
 570.0– 576.0 | person | adjusting | clothing
```
