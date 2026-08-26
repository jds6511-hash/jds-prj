# AAR 서버 실행 runbook (2026-08-26) — F3

**목표.** *"AAR 연구를 더 한다"가 아니라* **이미 있는 M8 기능을 서버에서 한 번 완주해
재사용 가능한 `report.json`을 확보한다.**

```
AAR demo generation using existing M8 pipeline   =  finalization functional run  ← 이 문서
M8 research evaluation / taxonomy / human review =  HOLD  (별도 사건, 여기서 하지 않는다)
```

이 문서의 목적은 **서버에 접속했을 때 고민할 일을 남기지 않는 것**이다.
GPU를 잡는 순간 위에서 아래로 그대로 실행한다.

---

## 0. 왜 서버인가 (되돌릴 수 없는 제약)

`report_model`이 `Qwen/Qwen2.5-7B-Instruct`이고 **로컬 6GB에서 4bit로도 실행 불가**가
실측이다(embed·lm_head 비양자화분이 초과). 3B 하향은 프롬프트 예시 문장 복사 오염으로
기각됐다(2026-07-11). 따라서 **서버 GPU 전용**이다.

서버: `kixlab2` · 계정 `daeseok` · **RTX 4090 24GB** · 저장 `/ssd`.
24GB면 7B를 bf16으로 올릴 수 있으므로 **`llm_4bit`를 false로 되돌린다**(로컬 6GB 대응값).

---

## 1. 대상 영상 (하나만 고정한다)

```
video_id     gwaktube_soviet_apartment
이유         dev split · 데모에 쓰는 3편 중 구간 수가 가장 적다(149) → 서버 1회 완주가 짧다
구간          149 · seg_len 5s
금지          test 4편(gemini_promo · itsub_viral_gadgets · panibottle_vietnam1 ·
             yunnamnopo_tongyeong) — demo preflight가 거부한다. M9도 실행하지 않는다.
```

여유가 있으면 `kheritage_grave_excavation`(192)까지 확보한다. **test 영상은 어떤 경우에도
쓰지 않는다.**

---

## 2. 반입할 입력 artifact와 해시

M8은 `work/{video_id}/segments.json`만 읽는다(프레임·영상·임베딩 불필요).

```bash
# 로컬에서 — 보낼 파일과 해시를 먼저 찍는다
cd /c/Users/UserK/Desktop/prj
V=gwaktube_soviet_apartment
sha256sum work/$V/segments.json
python - <<'EOF'
import json, io
V = "gwaktube_soviet_apartment"
d = json.loads(io.open(f"work/{V}/segments.json", encoding="utf-8").read())
print("n_segments:", d["n_segments"], "· segments:", len(d["segments"]))
EOF
```

기록할 것: `segments.json`의 **sha256**과 **n_segments**. 이 둘이 반입 전후·서버 왕복
전후로 같아야 한다.

```bash
# 전송
ssh daeseok@kixlab2 'mkdir -p /ssd/daeseok/prj/work/gwaktube_soviet_apartment'
scp work/$V/segments.json daeseok@kixlab2:/ssd/daeseok/prj/work/$V/segments.json
scp -r src scripts config.yaml daeseok@kixlab2:/ssd/daeseok/prj/     # 코드 동기화
```

> 코드는 git clone/pull이 더 낫지만, **실행 commit SHA를 결과에 기록하는 것이 조건**이다.
> 어느 쪽이든 서버에서 `git rev-parse HEAD`를 찍어 남긴다.

---

## 3. 서버 config 생성 (수동 편집 금지)

```bash
ssh daeseok@kixlab2
cd /ssd/daeseok/prj
python scripts/make_server_config.py --base /ssd/daeseok/prj --out config_server.yaml
```

`config.yaml`에서 **`llm_4bit`를 false로, `paths`를 `/ssd`로** 바꾼 사본만 만든다.
`report_model`·프롬프트·chunk 설정 등은 생성 전후 동일함을 스크립트가 `assert`로 대조한다.
**본 `config.yaml`을 편집하지 않는다.** `config_*.yaml`은 `.gitignore` 대상이다.

---

## 4. 실행 전 preflight (전부 통과해야 진행)

```bash
# 비대화형 SSH는 .bashrc를 안 읽는다 — 명령마다 명시한다
export HF_HOME=/ssd/$USER/cache

nvidia-smi                                    # 남이 쓰는지 확인. 유휴 40MiB 근처여야 여유
df -h /ssd                                    # 모델 캐시 여유(7B bf16 ≈ 15GB 다운로드)
git rev-parse HEAD                            # 실행 commit 기록
sha256sum work/gwaktube_soviet_apartment/segments.json   # 로컬 값과 일치 확인
python - <<'EOF'
import yaml, io
c = yaml.safe_load(io.open("config_server.yaml", encoding="utf-8").read())
assert c["llm_4bit"] is False, "서버에서는 llm_4bit=false"
assert c["paths"]["work"].startswith("/ssd"), "/home 금지"
print("preflight OK ·", c["report_model"], "·", c["paths"]["work"])
EOF
```

**중단 조건** — 남이 GPU를 많이 쓰고 있으면 실행하지 않는다. `/ssd` 여유가 30GB 미만이면
실행하지 않는다. 해시가 다르면 **전송된 바이트가 검증한 바이트가 아니므로** 실행하지 않는다.

---

## 5. 본 실행

```bash
cd /ssd/daeseok/prj
export HF_HOME=/ssd/$USER/cache
V=gwaktube_soviet_apartment

nohup python src/m8_report.py --config config_server.yaml --video-id $V \
  > /ssd/daeseok/prj/m8_${V}.log 2>&1 &
```

```
출력      /ssd/daeseok/prj/work/gwaktube_soviet_apartment/report.json
재실행    이미 있으면 건너뛴다. 다시 만들려면 --force
```

콘솔 한글은 깨질 수 있다 — **수치는 항상 UTF-8 JSON에서 읽는다.**

---

## 6. 서버 산출물 검증 (반출 전)

```bash
python - <<'EOF'
import json, io, hashlib
V = "gwaktube_soviet_apartment"
rp = f"/ssd/daeseok/prj/work/{V}/report.json"
sp = f"/ssd/daeseok/prj/work/{V}/segments.json"
r = json.loads(io.open(rp, encoding="utf-8").read())
s = json.loads(io.open(sp, encoding="utf-8").read())
print("video_id      :", r.get("video_id"))
print("model         :", r.get("model"))
print("n_segments    : report", r.get("n_segments"), "· segments", s["n_segments"])
assert r.get("n_segments") == s["n_segments"], "n_segments 불일치 — 다른 인덱스로 만든 리포트다"
print("report sha256 :", hashlib.sha256(io.open(rp,'rb').read()).hexdigest())
print("segs   sha256 :", hashlib.sha256(io.open(sp,'rb').read()).hexdigest())
EOF
git rev-parse HEAD    # 결과와 함께 기록
```

기록할 것: `report.json` sha256 · `segments.json` sha256 · 실행 commit · 모델 ID ·
`llm_4bit=false` · GPU · 소요.

---

## 7. 노트북 반입과 재확인

```bash
# 로컬에서
V=gwaktube_soviet_apartment
scp daeseok@kixlab2:/ssd/daeseok/prj/work/$V/report.json work/$V/report.json
sha256sum work/$V/report.json      # 서버에서 찍은 값과 같아야 한다
```

**반입 위치는 `work/{video_id}/report.json`이다** — `aar_view`의 기본 경로다.
`segments.json`은 **덮어쓰지 않는다**(로컬 인덱스가 원본이다).

---

## 8. 렌더와 추적 확인

```bash
python scripts/aar_view.py --config config.yaml --video-id gwaktube_soviet_apartment \
  --out-md docs/finalization/AAR_SAMPLE_gwaktube_soviet_apartment.md \
  --out-json docs/finalization/aar_sample_gwaktube_soviet_apartment.json
```

확인할 추적 경로 — **문장 → 인용 segment → timestamp → seek → 근거(자막·캡션)** 가
끊기지 않아야 한다. `aar_view`는 LLM을 쓰지 않는다(결정적 렌더).

```bash
python - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import aar_view
V = "gwaktube_soviet_apartment"
print(aar_view.check_precomputed(f"work/{V}/report.json", f"work/{V}/segments.json"))
EOF
```

---

## 9. 실패 조건 (그대로 두고 기록한다)

```
n_segments mismatch      report.json과 segments.json의 구간 수가 다르다
                         → 다른 인덱스로 만든 리포트다. 렌더하지 않는다(TraceError)
stale report             segments.json이 재생성됐는데 report.json이 옛것이다
                         → 같은 증상. 재생성 전까지 발표에 쓰지 않는다
out-of-range 인용        LLM이 없는 구간을 인용했다 → report.json은 저장되지만
                         검증에서 드러난다. 고치지 말고 관측으로 남긴다
해시 불일치              전송된 바이트가 검증한 바이트가 아니다 → 다시 전송
```

**어떤 경우에도 검출기·프롬프트·인덱스를 결과를 보고 바꾸지 않는다.**

---

## 10. 서버를 못 잡았을 때 (fallback)

**AAR가 없어도 데모의 검색·재생·근거 표시는 그대로 동작한다.** AAR는 부가 화면이다.

```
scripts/demo.py       AAR 유무와 무관하게 검색·seek·근거 표시 수행
aar_view              사전계산 report.json이 없으면 check_precomputed()가 없음을 보고한다
                      → 발표에서는 그 화면을 건너뛴다
```

따라서 **GPU 예약이 늦어지면 이 runbook만 커밋하고 F4·F5로 넘어간다.**
AAR 생성 때문에 프로젝트 전체가 대기하지 않는다.

---

## 11. 완료 후 기록할 항목

```
video_id · n_segments · report.json sha256 · segments.json sha256
실행 commit SHA · report_model · llm_4bit(false) · GPU · 소요
check_precomputed 결과 · 추적 경로 확인 여부 · 관측된 결함
```

이 결과는 **기능 확인 기록**이다. M8 research evaluation(6분류 taxonomy·human review)은
여전히 HOLD이고, 이 실행으로 그 권한이 생기지 않는다.
