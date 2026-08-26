# AAR 서버 실행 runbook (2026-08-26) — F3

**목표.** *"AAR 연구를 더 한다"가 아니라* **이미 있는 M8 기능을 서버에서 한 번 완주해
재사용 가능한 `report.json`을 확보한다.**

```
AAR demo generation using existing M8 pipeline   =  finalization functional run  ← 이 문서
M8 research evaluation / taxonomy / human review =  HOLD  (별도 사건, 여기서 하지 않는다)
```

이 문서의 목적은 **서버에 접속했을 때 고민할 일을 남기지 않는 것**이다.
GPU를 잡는 순간 위에서 아래로 그대로 실행한다.

> **실행 완료 (2026-08-26).** 이 runbook대로 1회 완주했다 — 149구간 · 문장 83 ·
> 인용 121구간 · 소요 3분 30초 · report sha256 `1a9e1429…`. 실행에서 드러난 결함
> 3건을 아래에 반영했다(자리표시자·인터프리터·§6 검증 스니펫). 결과 수치와 provenance는
> `docs/finalization/final_report_facts_2026-08-26.json`의 `aar` 블록이 source다.
>
> **접속 정보는 자리표시자로 쓴다** — `<SERVER_USER>` · `<SERVER_HOST>` · `<LAB_MACHINE>`.
> 실제 값은 추적하지 않는 `SERVER_LOCAL.md`에만 둔다(공개 저장소 정책).
> 초판이 실제 계정명과 머신 라벨을 그대로 적었고, **머신 라벨은 호스트명으로 해석되지
> 않아 접속이 실패했다.**

---

## 0. 왜 서버인가 (되돌릴 수 없는 제약)

`report_model`이 `Qwen/Qwen2.5-7B-Instruct`이고 **로컬 6GB에서 4bit로도 실행 불가**가
실측이다(embed·lm_head 비양자화분이 초과). 3B 하향은 프롬프트 예시 문장 복사 오염으로
기각됐다(2026-07-11). 따라서 **서버 GPU 전용**이다.

서버: `<LAB_MACHINE>` · 계정 `<SERVER_USER>` · **RTX 4090 24GB** · 저장 `/ssd`.
접속은 `ssh <SERVER_USER>@<SERVER_HOST>` — 실제 값은 `SERVER_LOCAL.md`(추적 안 함).
**머신 라벨(`<LAB_MACHINE>`)은 호스트명이 아니다.**
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

### 셸 변수 (아래 블록 전부가 쓴다)

```bash
U=<SERVER_USER>                          # SERVER_LOCAL.md
S=$U@<SERVER_HOST>                       # SERVER_LOCAL.md. <LAB_MACHINE>은 호스트명이 아니다
PY=/ssd/$U/envs/prj/bin/python           # 서버 system python3에는 torch가 없다
V=gwaktube_soviet_apartment
```

**작업 디렉터리는 `/ssd/$U/prj`를 새로 만든다.** 기존 `/ssd/$U/jds-prj`에는 과거 M8
파일럿 산출물과 열람 금지 마커가 있고 **거기 `segments.json`이 현재 로컬 인덱스와
다르다.** 연구 산출물과 섞지 않으려고 별도 디렉터리를 쓴다.

```bash
# 로컬에서 — 보낼 파일과 해시를 먼저 찍는다
cd /c/Users/UserK/Desktop/prj
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
ssh $S 'mkdir -p /ssd/$U/prj/work/gwaktube_soviet_apartment'
scp work/$V/segments.json $S:/ssd/$U/prj/work/$V/segments.json
scp -r src scripts config.yaml $S:/ssd/$U/prj/           # 코드 동기화
```

> 코드는 git clone/pull이 더 낫지만, **실행 commit SHA를 결과에 기록하는 것이 조건**이다.
> `scp`로 보내면 서버 쪽에 git이 없으므로 **로컬 HEAD를 기록하고, 보낸 바이트가 그
> HEAD의 것과 같은지 코드 manifest 해시로 대조한다**(양쪽에서 같은 값이어야 한다).

```bash
# 로컬·서버 양쪽에서 같은 값이 나와야 한다
python - <<'EOF'
import hashlib, pathlib
h = hashlib.sha256()
for f in sorted(list(pathlib.Path(".").glob("src/**/*.py"))
                + list(pathlib.Path(".").glob("scripts/**/*.py"))):
    h.update(f.as_posix().encode())
    h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
print("code manifest:", h.hexdigest())
EOF
git rev-parse HEAD; git status --short        # 로컬에서만. dirty 여부를 숨기지 않는다
```

---

## 3. 서버 config 생성 (수동 편집 금지)

```bash
ssh $S
cd /ssd/$U/prj
$PY scripts/make_server_config.py --base /ssd/$U/prj --out config_server.yaml
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
nvidia-smi --query-compute-apps=pid,process_name --format=csv   # 남의 프로세스 0건이어야 한다
who                                           # 다른 사용자 로그인 확인
df -h /ssd                                    # 모델 캐시 여유(7B bf16 ≈ 15GB 다운로드)
sha256sum work/gwaktube_soviet_apartment/segments.json   # 로컬 값과 일치 확인
$PY - <<'EOF'
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
cd /ssd/$U/prj
export HF_HOME=/ssd/$USER/cache
V=gwaktube_soviet_apartment

date -Iseconds > m8_${V}.started
nohup $PY src/m8_report.py --config config_server.yaml --video-id $V \
  > /ssd/$U/prj/m8_${V}.log 2>&1 &
```

```
출력      /ssd/$U/prj/work/gwaktube_soviet_apartment/report.json
재실행    이미 있으면 건너뛴다. 다시 만들려면 --force
소요 실측  149구간 · 3분 30초 (모델 로드 19초 포함, RTX 4090 bf16, HF 캐시 이미 있음)
진행 판정  프로세스 생존이 아니라 **로그의 `M8 완료:` 줄 + report.json 존재**로 한다
```

`m8_report.py`는 완료 전까지 진행 출력이 없다(가중치 로드 progress bar만 보인다).
GPU 사용률·VRAM으로 살아 있는지만 확인하고, 완료 판정은 위 두 마커로 한다.
콘솔 한글은 깨질 수 있다 — **수치는 항상 UTF-8 JSON에서 읽는다.**

---

## 6. 서버 산출물 검증 (반출 전)

> **초판 오류 (2026-08-26 실행에서 드러남).** 이 자리에 `r["n_segments"]`를 대조하는
> `assert`가 있었는데, **`m8_report.save_report`는 `n_segments`를 쓰지 않는다** —
> `video_id` · `schema_version` · `model` · `map_chunk_size` · `provenance` + 생성 결과만
> 저장한다. 정상 리포트에서도 그 assert는 반드시 실패한다. 실제로 있는 것으로 바꿨다.
>
> **인덱스 대응은 해시로 판정한다.** 생성에 쓴 `segments.json`의 sha256이 로컬 원본과
> 같으면 인용 번호가 같은 구간을 가리킨다 — 구간 수만 세는 것보다 강한 검사다.

```bash
$PY - <<'EOF'
import json, io, hashlib
V = "gwaktube_soviet_apartment"
rp = f"/ssd/$U/prj/work/{V}/report.json"
sp = f"/ssd/$U/prj/work/{V}/segments.json"
r = json.loads(io.open(rp, encoding="utf-8").read())
s = json.loads(io.open(sp, encoding="utf-8").read())
segs = {x["idx"] for x in s["segments"]}
n = len(s["segments"])
print("video_id      :", r.get("video_id"))
print("model         :", r.get("model"), "| schema", r.get("schema_version"))
print("n_sentences   :", len(r["sentences"]), "| index n_segments:", n)
assert r.get("video_id") == V, "video_id 불일치"
assert r.get("schema_version") == 2, "aar_view가 지원하는 schema가 아니다"
nocite = [x.get("sent_id") for x in r["sentences"] if not (x.get("cites") or [])]
oor = sorted({c for x in r["sentences"] for c in (x.get("cites") or []) if c not in segs})
assert not nocite, f"인용 없는 문장 {nocite}"
assert not oor, f"인용 범위 위반 {oor}"
cited = {c for x in r["sentences"] for c in (x.get("cites") or [])}
print("cited segments:", len(cited), "/", n)
print("max cites/sent:", max(len(x["cites"]) for x in r["sentences"]), "(reduce 퇴화 상한 확인)")
print("report sha256 :", hashlib.sha256(io.open(rp,'rb').read()).hexdigest())
print("segs   sha256 :", hashlib.sha256(io.open(sp,'rb').read()).hexdigest(), "← 로컬 값과 같아야 한다")
print("SERVER VALIDATOR PASS")
EOF
```

`save_report`의 자체 검증 4개(반복 루프 · 인용 범위 · 서술 공백 · reduce 퇴화)는
**저장 직후 실행되므로 종료코드 0과 `M8 완료:` 출력 자체가 그 통과 증거**다.

기록할 것: `report.json` sha256 · `segments.json` sha256 · 로컬 실행 HEAD + 코드 manifest ·
모델 ID · `llm_4bit=false` · GPU · 소요.

---

## 7. 노트북 반입과 재확인

```bash
# 로컬에서
V=gwaktube_soviet_apartment
scp $S:/ssd/$U/prj/work/$V/report.json work/$V/report.json
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

> **렌더 산출물은 커밋하지 않는다.** `AAR_SAMPLE_*.md` · `aar_sample_*.json`에는
> 인용 구간의 **자막·캡션 원문이 그대로 실린다**(이번 실행에서 자막 99 · 캡션 121구간).
> `work/*/segments.json`을 공개하지 않는 것과 같은 이유로 `.gitignore` 대상이다.
> 저장소에는 해시·수치만 남기고 재생성은 이 명령으로 한다.

```bash
python - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import aar_view
V = "gwaktube_soviet_apartment"
print(aar_view.check_precomputed(f"work/{V}/report.json", f"work/{V}/segments.json",
                                 video_id=V))
EOF
python scripts/demo.py --video-id gwaktube_soviet_apartment --check-only
#  → "AAR 사전 생성물   사용 가능 (문장 N · 인용 구간 M)" 으로 바뀌어야 한다
```

**`index_consistency.n_segments_checked`는 `false`로 나온다** — `report.json`의
provenance에 `n_segments`가 없기 때문이고 결함이 아니다(`aar_view`가 그 경우를 보고만
하도록 만들어져 있다). 인덱스 대응은 §6의 **해시 일치**로 판정한다.

---

## 9. 실패 조건 (그대로 두고 기록한다)

```
n_segments mismatch      report provenance에 n_segments가 있고 현재 인덱스와 다르다
                         → 다른 인덱스로 만든 리포트다. 렌더하지 않는다(TraceError)
                         현재 코드는 그 필드를 쓰지 않아 이 경로가 발동하지 않는다 —
                         그래서 §6에서 segments.json 해시로 대신 판정한다
stale report             segments.json이 재생성됐는데 report.json이 옛것이다
                         → 해시가 달라진다. 재생성 전까지 발표에 쓰지 않는다
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
