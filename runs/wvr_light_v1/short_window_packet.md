# SHORT_WINDOW_V1 blinded adjudication packet

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`

```
각 창의 두 출력은 Arm A · Arm B로 가려져 있다.
어느 쪽이 0.5fps(higher-density reference)인지는 판정 전까지 공개되지 않는다.
0.5fps는 truth가 아니다 — 어느 쪽이 더 촘촘한지가 정답을 뜻하지 않는다.
판정값은 STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED 넷뿐이다.
```

```
기술 게이트   6/6 통과 (파싱 · 절단 없음 · English-only · 표현 비축퇴)
```

## P1  360–408초 (48초)

### Arm A

```
  start–  end  | actor | action | object_or_state
    360.0–  368.0 | person | handling | sushi rolls wrapped in plastic
    368.0–  376.0 | person | placing | sushi rolls on a plate
    376.0–  392.0 | person | serving | food on a plate
    392.0–  400.0 | person | handling | chicken legs
    400.0–  408.0 | person | holding | underwear
```

### Arm B

```
  start–  end  | actor | action | object_or_state
    360.0–  365.0 | person | placing | sushi roll on cutting board
    365.0–  370.0 | person | placing | sushi rolls on plate
    370.0–  375.0 | person | arranging | sushi rolls on plate
    375.0–  380.0 | person | placing | bowl of soup on table
    380.0–  385.0 | person | placing | chicken legs in steamer
    385.0–  390.0 | person | placing | noodles in bowl
    390.0–  400.0 | person | placing | chicken legs in bowl
    400.0–  405.0 | person | holding | orange cloth
    405.0–  408.0 | person | holding | pink cloth
```

## P2  416–464초 (48초)

### Arm A

```
  start–  end  | actor | action | object_or_state
    416.0–  424.0 | person | holding | orange pajama pants with carrot patterns
    424.0–  432.0 | person | placing | orange pajama pants into a drawer
    432.0–  440.0 | person | sewing | orange pajama pants using a sewing machine
    440.0–  448.0 | person | holding | orange pajama pants with carrot patterns
    448.0–  456.0 | person | hanging | orange pajama pants on a hanger
    456.0–  464.0 | person | holding | orange pajama pants with carrot patterns
```

### Arm B

```
  start–  end  | actor | action | object_or_state
    416.0–  421.0 | a person | holding | a piece of fabric
    421.0–  425.0 | a person | holding | a piece of fabric with carrot patterns
    425.0–  429.0 | a person | placing | a piece of fabric on a drawer
    429.0–  433.0 | a person | placing | a piece of fabric on a sewing machine
    433.0–  437.0 | a person | sewing | a piece of fabric with carrot patterns
    437.0–  453.0 | a person | holding | a piece of fabric with carrot patterns
    453.0–  464.0 | a person | placing | a piece of food on a plate
```

## P3  104–152초 (48초)

### Arm A

```
  start–  end  | actor | action | object_or_state
    104.0–  128.0 | person | peeling | potato
    128.0–  136.0 | person | mixing | potato mixture
    136.0–  144.0 | person | forming | potato balls
    144.0–  152.0 | person | arranging | potato balls on plate
```

### Arm B

```
  start–  end  | actor | action | object_or_state
    104.0–  112.0 | person | using | potato ricer
    112.0–  120.0 | person | pressing | potato ricer
    120.0–  128.0 | person | mixing | potato mixture
    128.0–  136.0 | person | wearing | gloves
    136.0–  144.0 | person | mixing | potato mixture
    144.0–  152.0 | person | placing | potato dough balls
```
