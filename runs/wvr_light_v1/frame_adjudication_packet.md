# FRAME_ADJUDICATION_V1 packet — KEEP·DROP 프레임 실물

사전등록: `docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md`

```
프레임은 모델이 실제로 받은 것과 같은 512×288이다(원본 해상도가 아니다).
KEEP  = S0·S1 공통 프레임 (0.25fps에도 들어간 것)
DROP  = S0에만 있는 프레임 (0.25fps가 못 본 것)
판정값 DROP_FRAMES_CARRY_MATERIAL_INFORMATION · KEEP_FRAMES_SUFFICIENT ·
       GENERATION_ERROR_NOT_SAMPLING · FRAMES_INSUFFICIENT
```

## Q1  P2 448–464초

garment/pajama sequence가 계속되는가, 아니면 food-on-plate 장면으로 전환되는가?

```
KEEP  448.0, 452.0, 456.0, 460.0
DROP  450.0, 454.0, 458.0, 462.0
```

대지: `runs/wvr_light_v1/frames_adjudication/Q1_sheet.png`

**S0 (0.5fps) 주장**

```
437–453 | a person | holding | a piece of fabric with carrot patterns
453–464 | a person | placing | a piece of food on a plate
```

**S1 (0.25fps) 주장**

```
448–456 | person | hanging | orange pajama pants on a hanger
456–464 | person | holding | orange pajama pants with carrot patterns
```

## Q2  P3 104–128초

potato peeling인가, potato ricer/pressing/mixing인가?

```
KEEP  104.0, 108.0, 112.0, 116.0, 120.0, 124.0
DROP  106.0, 110.0, 114.0, 118.0, 122.0, 126.0
```

대지: `runs/wvr_light_v1/frames_adjudication/Q2_sheet.png`

**S0 (0.5fps) 주장**

```
104–128 | person | peeling | potato
```

**S1 (0.25fps) 주장**

```
104–112 | person | using | potato ricer
112–120 | person | pressing | potato ricer
120–128 | person | mixing | potato mixture
```

## Q3  P3 128–144초

forming potato balls인가, gloves/mixing sequence인가?

```
KEEP  128.0, 132.0, 136.0, 140.0
DROP  130.0, 134.0, 138.0, 142.0
```

대지: `runs/wvr_light_v1/frames_adjudication/Q3_sheet.png`

**S0 (0.5fps) 주장**

```
128–136 | person | mixing | potato mixture
136–144 | person | forming | potato balls
```

**S1 (0.25fps) 주장**

```
128–136 | person | wearing | gloves
136–144 | person | mixing | potato mixture
```
