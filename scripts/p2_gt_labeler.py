"""P2 GT 라벨링 도구 — **손동작만 줄인다. 기준은 그대로다.**

315건을 쓰려면 지금은 시트 열기 → 영상 열기 → 위치 찾기 → CSV로 돌아가기를 315번
반복해야 한다. 이 도구는 그 왕복을 한 화면으로 접는다. **연구 계약은 하나도 바꾸지
않는다** — 질의 수·유형 배정·GT 정의·판정식·제외 규칙 전부 그대로다.

```
읽는 것    label_kit/p2/p2_label_intake.csv         (동결 배정 + 작성 중인 값)
          docs/P2_선정표본_2026-08-20.json          (영상 목록·구간 수·길이)
          label_kit/p2/contact_sheets/*.jpg         (프레임 + 시각 타일)
          data/videos/*.mp4                         (원본 영상)
안 읽는 것  파이프라인 텍스트 산출물 · 모델 구분 · 검색 결과 · 점수·순위 · 색인.
          숨기는 게 아니라 **그 경로를 여는 코드가 없다**
```

사람이 바꿀 수 있는 것은 `text` · `gt_start` · `gt_end` · `note`뿐이다. `query_id` ·
`video_id` · `query_type`을 바꾸려 하면 거절한다.

**타일 클릭은 seek 도움일 뿐이다.** 타일이 가리키는 구간을 GT 경계로 자동 입력하지
않는다 — 대표 프레임은 5초 구간의 한 시점이라 경계가 아니다. 경계는 사람이 원본 영상을
보고 지정한다.

**이 도구가 하지 않는 것**: 질의문 자동 생성·추천, 최종 산출물 자동 생성, 검색·평가
실행, 최종 동결. 전부 별도 단계다. 최종 권위 검증기는 그대로
`python scripts/p2_label_intake.py build`다.

실행:
  python scripts/p2_gt_labeler.py                 # http://127.0.0.1:8788
  python scripts/p2_gt_labeler.py --port 9000
"""
import argparse
import csv
import http.server
import json
import math
import os
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

CSV_PATH = ROOT / "label_kit" / "p2" / "p2_label_intake.csv"
SHEETS = ROOT / "label_kit" / "p2" / "contact_sheets"
VIDEOS = ROOT / "data" / "videos"
READS = ("intake_csv", "selection_manifest", "contact_sheets", "source_video",
         "ai_proposals")
WRITES = ("intake_csv", "adjudication_audit")
COLUMNS = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
           "note")
FROZEN = ("query_id", "video_id", "query_type")
HUMAN = ("text", "gt_start", "gt_end", "note")
# 시트 생성기와 같은 격자여야 타일 → 시각 매핑이 맞다 (테스트가 상수를 대조한다)
COLS, PER_SHEET, SEG_LEN = 6, 60, 5


class LabelerError(RuntimeError):
    pass


def _ai():
    import p2_ai_draft
    return p2_ai_draft


def _adj():
    import p2_adjudication
    return p2_adjudication


def n_pages(n_segments: int) -> int:
    return max(1, math.ceil(n_segments / PER_SHEET))


def tile_at(page: int, x_frac: float, y_frac: float, n_segments: int) -> dict:
    """타일 클릭 → 그 구간의 시작 시각. **GT 경계가 아니라 seek 목표다.**"""
    if page < 1 or (page - 1) * PER_SHEET >= n_segments:
        raise LabelerError(f"페이지 {page}에 세그먼트가 없다")
    on_page = min(PER_SHEET, n_segments - (page - 1) * PER_SHEET)
    rows_on_page = math.ceil(on_page / COLS)
    col = min(COLS - 1, max(0, int(x_frac * COLS)))
    row = min(rows_on_page - 1, max(0, int(y_frac * rows_on_page)))
    k = row * COLS + col
    if k >= on_page:
        raise LabelerError(f"빈 칸이다 — 이 페이지의 세그먼트는 {on_page}개다")
    idx = (page - 1) * PER_SHEET + k
    return {"seg_idx": idx, "seek_sec": float(idx * SEG_LEN)}


def parse_range(header, size: int):
    """부분 요청을 해석한다 — 없으면 None(전체 전송). 영상 seek가 이걸로 빨라진다."""
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes="):].split(",")[0].strip()
    try:
        if spec.startswith("-"):
            length = int(spec[1:])
            return max(0, size - length), size - 1
        first, _, last = spec.partition("-")
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start >= size or start > end:
        return None
    return start, min(end, size - 1)


def _num(v, name: str):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise LabelerError(f"{name}가 숫자가 아니다 — {v!r}")


def _fmt(v) -> str:
    if v in (None, ""):
        return ""
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)


class App:
    """CSV를 그대로 source of truth로 쓰는 편집기. 새 스키마를 만들지 않는다."""

    def __init__(self, csv_path=CSV_PATH, sheets=SHEETS, videos=VIDEOS,
                 bounds=None, proposals=None, audit_path=None):
        self.csv_path = Path(csv_path)
        self.sheets = Path(sheets)
        self.videos = Path(videos)
        self.bounds = dict(bounds or {})
        self.rows = self._read()
        self.proposals = self._load_proposals(proposals)
        self.audit_path = Path(audit_path) if audit_path is not None             else _adj().AUDIT
        if self.audit_path == _adj().AUDIT and self.csv_path != Path(CSV_PATH):
            # 실측 사고: 픽스처 CSV로 만든 App이 본 audit에 픽스처 query_id를 썼다.
            # 작업 CSV가 본 intake가 아니면 본 audit에 쓰지 못하게 막는다.
            raise LabelerError("작업 CSV가 본 intake가 아닌데 본 audit에 쓰려 한다 "
                               "— audit_path를 분리해라")

    def _load_proposals(self, given) -> dict:
        """AI 초안을 읽어 둔다. **행에 채워 넣지 않는다** — 별도로 보여 주기만 한다."""
        rows = given if given is not None else _ai().load_drafts()
        known = {r["query_id"] for r in self.rows}
        out = {}
        for r in rows:
            qid = r.get("query_id")
            if qid not in known:
                raise LabelerError(f"{qid}: 초안이 활성 설계에 없는 행을 가리킨다")
            out[qid] = {"draft_text": str(r.get("draft_text") or ""),
                        "draft_gt_start": _fmt(_num(r.get("draft_gt_start"),
                                                    "draft_gt_start")),
                        "draft_gt_end": _fmt(_num(r.get("draft_gt_end"),
                                                  "draft_gt_end")),
                        "ai_model": str(r.get("ai_model") or ""),
                        "rationale": str(r.get("rationale") or "")}
        return out

    def _allocation(self) -> list:
        return [{k: r[k] for k in FROZEN} for r in self.rows]

    def proposal_of(self, qid: str) -> dict:
        return self.proposals.get(qid)

    def _read(self) -> list:
        if not self.csv_path.is_file():
            raise LabelerError(f"intake CSV가 없다: {self.csv_path}")
        rows = list(csv.DictReader(
            self.csv_path.read_text(encoding="utf-8-sig").splitlines()))
        if not rows:
            raise LabelerError("intake CSV가 비었다")
        return [{c: (r.get(c) or "") for c in COLUMNS} for r in rows]

    def _write(self) -> None:
        tmp = self.csv_path.with_suffix(".csv.part")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(COLUMNS))
            w.writeheader()
            w.writerows(self.rows)
        tmp.replace(self.csv_path)

    def _row(self, qid: str) -> dict:
        for r in self.rows:
            if r["query_id"] == qid:
                return r
        raise LabelerError(f"{qid}: 배정에 없다 — query_id를 만들지 않는다")

    def _check_frozen(self, row: dict, edit: dict) -> None:
        for f in FROZEN:
            if f in edit and str(edit[f]) != row[f]:
                raise LabelerError(
                    f"{f}는 동결된 배정이다 — 이 도구로 바꿀 수 없다 "
                    f"({row[f]!r} → {edit[f]!r})")

    def _apply(self, edit: dict, complete: bool) -> dict:
        row = self._row(str(edit.get("query_id", "")))
        self._check_frozen(row, edit)
        text = str(edit.get("text", row["text"]) or "").strip()
        s = _num(edit.get("gt_start", row["gt_start"]), "gt_start")
        e = _num(edit.get("gt_end", row["gt_end"]), "gt_end")
        note = str(edit.get("note", row["note"]) or "").strip()
        bound = self.bounds.get(row["video_id"])
        if s is not None and e is not None:
            if not 0 <= s < e:
                raise LabelerError(f"gt_start < gt_end여야 한다 ({s}, {e})")
            if bound is not None and e > bound:
                raise LabelerError(f"영상 길이 {bound}s를 넘는다 (gt_end {e})")
        if complete:
            if not text:
                raise LabelerError("text가 비어 있다")
            if s is None or e is None:
                raise LabelerError("gt_start·gt_end가 필요하다")
        row.update({"text": text, "gt_start": _fmt(s), "gt_end": _fmt(e),
                    "note": note})
        self._write()
        return row

    def save(self, edit: dict) -> dict:
        """완성 저장. 세 칸이 다 있어야 하고, 초안이 있으면 행동을 명시해야 한다."""
        adj = _adj()
        qid = str(edit.get("query_id", ""))
        prop = self.proposals.get(qid)
        action = (edit.get("action") or "").strip() or None
        if prop is None:
            if action not in (None, "not_applicable"):
                raise LabelerError(f"{qid}: 초안이 없는 행에 draft_action "
                                   f"{action!r}을 붙일 수 없다")
            action = "not_applicable"
            origin = "human_only"
        else:
            if action not in ("accepted", "edited", "rejected_manual"):
                raise LabelerError(
                    "AI 초안이 있는 행은 accepted·edited·rejected_manual 중 하나를 "
                    "명시해야 저장된다 — 초안을 보여 준 것만으로 완료되지 않는다")
            origin = "ai_first_human_adjudicated"
            if action == "accepted":
                same = (str(edit.get("text", "")).strip() == prop["draft_text"]
                        and _fmt(_num(edit.get("gt_start"), "gt_start"))
                        == prop["draft_gt_start"]
                        and _fmt(_num(edit.get("gt_end"), "gt_end"))
                        == prop["draft_gt_end"])
                if not same:
                    raise LabelerError(
                        "accepted는 초안을 그대로 확정했다는 뜻이다 — 값이 다르면 "
                        "edited로 기록해라")
        row = self._apply(edit, complete=True)
        adj.record(qid, origin, action, self.audit_path,
                   allocation=self._allocation())
        return row

    def draft(self, edit: dict) -> dict:
        """작성 중 임시 저장. **완료로 세지 않는다.**"""
        return self._apply(edit, complete=False)

    def is_done(self, row: dict) -> bool:
        return all(str(row.get(c) or "").strip()
                   for c in ("text", "gt_start", "gt_end"))

    def progress(self) -> dict:
        by_video = {}
        for r in self.rows:
            if self.is_done(r):
                by_video[r["video_id"]] = by_video.get(r["video_id"], 0) + 1
        return {"done": sum(1 for r in self.rows if self.is_done(r)),
                "total": len(self.rows), "by_video": by_video}

    def resume_index(self) -> int:
        for i, r in enumerate(self.rows):
            if not self.is_done(r):
                return i
        return len(self.rows) - 1

    def state(self, n_segments: dict) -> dict:
        return {"rows": [{**r, "done": self.is_done(r)} for r in self.rows],
                "columns": list(COLUMNS), "frozen": list(FROZEN),
                "human": list(HUMAN),
                "progress": self.progress(), "resume": self.resume_index(),
                "n_segments": n_segments,
                "pages": {v: n_pages(n) for v, n in n_segments.items()},
                "bounds": self.bounds, "seg_len": SEG_LEN, "cols": COLS,
                "per_sheet": PER_SHEET,
                # 초안은 행 값에 섞지 않는다 — 사람이 행동을 고르기 전까지 별개다
                "proposals": self.proposals,
                "actions": list(_adj().DRAFT_ACTION)}


def load_reference():
    """영상별 구간 수와 길이 상한. 최종 검증기와 **같은 규칙**을 쓴다."""
    import p2_label_intake as I
    return I.n_segments_of(), I.time_bound_of(SEG_LEN)


PAGE = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>P2 GT 라벨러</title><style>
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,sans-serif;
background:#101418;color:#e8eef5}
header{display:flex;gap:16px;align-items:baseline;padding:8px 14px;
background:#1c2530;position:sticky;top:0;z-index:5}
header b{font-size:16px}#prog{color:#7ee787;font-variant-numeric:tabular-nums}
#type{padding:2px 8px;border-radius:10px;background:#2a3a4a}
main{display:grid;grid-template-columns:minmax(420px,1fr) minmax(360px,480px);
gap:12px;padding:12px;align-items:start}
video{width:100%;background:#000;border-radius:6px}
.pane{background:#161d25;border-radius:8px;padding:10px}
.sheet img{width:100%;cursor:crosshair;border-radius:4px}
.row{display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap}
input,textarea,button,select{font:inherit;background:#0d1116;color:#e8eef5;
border:1px solid #2a3a4a;border-radius:5px;padding:6px}
textarea{width:100%;min-height:54px}input[type=number]{width:110px}
button{cursor:pointer}button.p{background:#7fb3ff;color:#0d1116;font-weight:600}
.hint{color:#93a7bc;font-size:12px}.warn{color:#ffd166;font-size:12px}
.prop{border:1px solid #3a4a5a;border-radius:6px;padding:8px;margin:6px 0}
kbd{background:#2a3a4a;border-radius:4px;padding:1px 5px;font-size:12px}
#list{max-height:190px;overflow:auto;display:flex;flex-wrap:wrap;gap:4px}
#list button{padding:3px 7px;font-size:12px}
#list button.d{border-color:#7ee787;color:#7ee787}
#list button.cur{background:#7fb3ff;color:#0d1116}
</style>
<header><b>P2 GT 라벨러</b><span id=prog></span><span id=qid></span>
<span id=type></span><span class=hint id=vid></span></header>
<main>
<div>
 <video id=v controls preload=metadata></video>
 <div class=pane>
  <div class=row>
   <button data-d=-5>−5s</button><button data-d=-1>−1s</button>
   <button data-d=-0.1>−0.1s</button><button data-d=0.1>+0.1s</button>
   <button data-d=1>+1s</button><button data-d=5>+5s</button>
   <span class=hint>현재 <b id=cur>0.00</b>s</span>
  </div>
  <div class=row>
   <button id=setI>시작 = 현재 <kbd>I</kbd></button>
   <input id=s type=number step=0.1 min=0>
   <button id=setO>끝 = 현재 <kbd>O</kbd></button>
   <input id=e type=number step=0.1 min=0>
   <button id=go>구간 재생 <kbd>P</kbd></button>
  </div>
  <div id=prop class=prop hidden>
   <div class=row><b>AI 초안</b><span class=hint id=pmodel></span></div>
   <div class=hint id=ptext></div>
   <div class=hint id=pspan></div>
   <div class=row>
    <button id=pacc>초안 그대로 확정</button>
    <button id=pedit>초안 불러와 수정</button>
    <button id=prej>초안 거부 · 직접 작성</button>
    <span class=warn id=pact></span>
   </div>
   <div class=warn>초안은 정답이 아니다. 원본 영상에서 확인한 뒤 행동을 고른다 —
    고르지 않으면 저장되지 않는다.</div>
  </div>
  <textarea id=t placeholder="사람이 실제로 검색할 한 문장 (자동 생성 없음)"></textarea>
  <div class=row><input id=n placeholder="메모(선택)" style="flex:1">
   <button id=save class=p>저장하고 다음 <kbd>Ctrl+S</kbd></button></div>
  <div class=warn>시트는 후보 위치 탐색용이다. GT 경계는 원본 영상으로 확인한다 —
   타일을 눌러도 경계가 자동 입력되지 않는다.</div>
  <div class=hint><kbd>J</kbd>/<kbd>L</kbd> ±1s ·
   <kbd>,</kbd>/<kbd>.</kbd> ±0.1s · <kbd>←</kbd>/<kbd>→</kbd> ±5s ·
   <kbd>Space</kbd> 재생 · <kbd>Alt+←/→</kbd> 이전·다음 질의</div>
 </div>
 <div class=pane><div class=row><b id=vcount>이 영상</b>
  <span class=hint>순서는 동결돼 있다</span></div><div id=list></div></div>
</div>
<div class="pane sheet">
 <div class=row><button id=pp>◀</button><span id=pg></span><button id=pn>▶</button>
  <span class=hint>타일 클릭 → 그 시각으로 이동</span></div>
 <img id=sh alt="프레임 시트">
</div>
</main>
<script>
let S=null,i=0,page=1,act=null;
const $=q=>document.querySelector(q),v=$('#v');
const row=()=>S.rows[i];
async function load(){S=await (await fetch('/api/state')).json();i=S.resume;go();}
function go(){const r=row();act=null;
 $('#qid').textContent=r.query_id;$('#type').textContent=r.query_type;
 $('#vid').textContent=r.video_id+' · '+S.n_segments[r.video_id]+'구간';
 $('#prog').textContent=S.progress.done+' / '+S.progress.total;
 $('#t').value=r.text||'';$('#s').value=r.gt_start||'';$('#e').value=r.gt_end||'';
 $('#n').value=r.note||'';
 if(!v.dataset.vid||v.dataset.vid!==r.video_id){
  v.src='/video/'+encodeURIComponent(r.video_id);v.dataset.vid=r.video_id;}
 proposal();page=1;sheet();list();}
function proposal(){const r=row(),p=S.proposals[r.query_id],el=$('#prop');
 if(!p){el.hidden=true;return;}
 el.hidden=false;$('#pmodel').textContent=p.ai_model;
 $('#ptext').textContent='질의 초안: '+p.draft_text;
 $('#pspan').textContent='구간 초안: '+p.draft_gt_start+'s ~ '+p.draft_gt_end+'s'
  +(p.rationale?' · '+p.rationale:'');
 $('#pact').textContent='행동 미선택';}
function setAct(a){act=a;$('#pact').textContent='행동: '+a;}
function fillFromProposal(){const p=S.proposals[row().query_id];
 $('#t').value=p.draft_text;$('#s').value=p.draft_gt_start;
 $('#e').value=p.draft_gt_end;}
function list(){const r=row(),el=$('#list');el.innerHTML='';
 $('#vcount').textContent='이 영상의 '+
  S.rows.filter(x=>x.video_id===r.video_id).length+'건';
 S.rows.forEach((x,k)=>{if(x.video_id!==r.video_id)return;
  const b=document.createElement('button');
  b.textContent=x.query_id.split('_').pop()+' '+x.query_type;
  if(x.done)b.className='d';if(k===i)b.className='cur';
  b.onclick=()=>{i=k;go();};el.appendChild(b);});}
function sheet(){const r=row(),n=S.pages[r.video_id];
 page=Math.min(Math.max(1,page),n);$('#pg').textContent=page+' / '+n;
 $('#sh').src='/sheet/'+encodeURIComponent(r.video_id)+'/'+page;}
$('#pp').onclick=()=>{page--;sheet();};$('#pn').onclick=()=>{page++;sheet();};
$('#sh').onclick=async ev=>{const b=ev.target.getBoundingClientRect();
 const q=new URLSearchParams({video:row().video_id,page,
  x:(ev.clientX-b.left)/b.width,y:(ev.clientY-b.top)/b.height});
 const r=await (await fetch('/api/tile?'+q)).json();
 if(r.error){alert(r.error);return;}
 v.currentTime=r.seek_sec;v.pause();};
const seek=d=>{v.currentTime=Math.max(0,v.currentTime+d);};
document.querySelectorAll('[data-d]').forEach(b=>
 b.onclick=()=>seek(parseFloat(b.dataset.d)));
v.ontimeupdate=()=>{$('#cur').textContent=v.currentTime.toFixed(2);};
$('#setI').onclick=()=>{$('#s').value=v.currentTime.toFixed(1);};
$('#setO').onclick=()=>{$('#e').value=v.currentTime.toFixed(1);};
$('#go').onclick=()=>{const a=parseFloat($('#s').value);
 if(!isNaN(a)){v.currentTime=a;v.play();}};
async function post(url,body){const r=await fetch(url,{method:'POST',
 headers:{'content-type':'application/json'},body:JSON.stringify(body)});
 return r.json();}
const payload=()=>({query_id:row().query_id,text:$('#t').value,
 gt_start:$('#s').value,gt_end:$('#e').value,note:$('#n').value,
 action:act||''});
async function draft(){const r=await post('/api/draft',payload());
 if(!r.error){S.rows[i]=r.row;S.progress=r.progress;}}
$('#pacc').onclick=()=>{fillFromProposal();setAct('accepted');$('#save').click();};
$('#pedit').onclick=()=>{fillFromProposal();setAct('edited');};
$('#prej').onclick=()=>{$('#t').value='';$('#s').value='';$('#e').value='';
 setAct('rejected_manual');};
$('#save').onclick=async()=>{const r=await post('/api/save',payload());
 if(r.error){alert(r.error);return;}
 S.rows[i]=r.row;S.progress=r.progress;
 const nxt=S.rows.findIndex((x,k)=>k>i&&!x.done);
 i=nxt<0?Math.min(i+1,S.rows.length-1):nxt;go();};
['#t','#s','#e','#n'].forEach(q=>$(q).addEventListener('change',draft));
addEventListener('keydown',ev=>{
 if(ev.ctrlKey&&ev.key==='s'){ev.preventDefault();$('#save').click();return;}
 if(ev.altKey&&ev.key==='ArrowLeft'){i=Math.max(0,i-1);go();return;}
 if(ev.altKey&&ev.key==='ArrowRight'){i=Math.min(S.rows.length-1,i+1);go();return;}
 if(ev.target.matches('input,textarea'))return;
 const k=ev.key.toLowerCase();
 if(k==='i'){$('#setI').click();}else if(k==='o'){$('#setO').click();}
 else if(k==='j'){seek(-1);}else if(k==='l'){seek(1);}
 else if(k===','){seek(-0.1);}else if(k==='.'){seek(0.1);}
 else if(ev.key==='ArrowLeft'){seek(-5);}else if(ev.key==='ArrowRight'){seek(5);}
 else if(k==='p'){$('#go').click();}
 else if(ev.key===' '){ev.preventDefault();v.paused?v.play():v.pause();}});
load();
</script></html>"""


def make_handler(app: App, n_segments: dict):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype: str, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _file(self, path: Path, ctype: str):
            if not path.is_file():
                self._json({"error": f"파일이 없다: {path.name}"}, 404)
                return
            size = path.stat().st_size
            rng = parse_range(self.headers.get("Range"), size)
            with open(path, "rb") as f:
                if rng is None:
                    self._send(200, f.read(), ctype,
                               {"Accept-Ranges": "bytes"})
                    return
                start, end = rng
                f.seek(start)
                chunk = f.read(end - start + 1)
            self._send(206, chunk, ctype,
                       {"Accept-Ranges": "bytes",
                        "Content-Range": f"bytes {start}-{end}/{size}"})

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            parts = [urllib.parse.unquote(p) for p in u.path.strip("/").split("/")]
            if u.path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif u.path == "/api/state":
                self._json(app.state(n_segments))
            elif u.path == "/api/tile":
                try:
                    self._json(tile_at(int(q["page"][0]), float(q["x"][0]),
                                       float(q["y"][0]),
                                       n_segments[q["video"][0]]))
                except (LabelerError, KeyError, ValueError) as exc:
                    self._json({"error": str(exc)}, 400)
            elif len(parts) == 2 and parts[0] == "video":
                self._file(app.videos / f"{parts[1]}.mp4", "video/mp4")
            elif len(parts) == 3 and parts[0] == "sheet":
                name = f"{parts[1]}_p{int(parts[2]):02d}.jpg"
                self._file(app.sheets / name, "image/jpeg")
            else:
                self._json({"error": "없는 경로"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                self._json({"error": "본문이 JSON이 아니다"}, 400)
                return
            fn = {"/api/save": app.save, "/api/draft": app.draft}.get(self.path)
            if fn is None:
                self._json({"error": "없는 경로"}, 404)
                return
            try:
                row = fn(body)
            except LabelerError as exc:
                self._json({"error": str(exc)}, 400)
                return
            self._json({"row": {**row, "done": app.is_done(row)},
                        "progress": app.progress()})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intake", default=str(CSV_PATH))
    ap.add_argument("--sheets", default=str(SHEETS))
    ap.add_argument("--videos", default=str(VIDEOS))
    ap.add_argument("--port", type=int, default=8788)
    a = ap.parse_args()
    n_segments, bounds = load_reference()
    app = App(csv_path=a.intake, sheets=a.sheets, videos=a.videos, bounds=bounds)
    pr = app.progress()
    print(f"P2 GT 라벨러  {pr['done']}/{pr['total']} 작성됨")
    print(f"  intake  {a.intake}")
    print(f"  열기    http://127.0.0.1:{a.port}/   (Ctrl+C로 종료)")
    print("  최종 검증은 이 도구가 아니라 "
          "`python scripts/p2_label_intake.py build`다")
    os.chdir(ROOT)
    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", a.port), make_handler(app, n_segments))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료. 작성분은 CSV에 저장돼 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
