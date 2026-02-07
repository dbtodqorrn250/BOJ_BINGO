import streamlit as st
import requests
import random
import time
import concurrent.futures
import pickle
import os
from bs4 import BeautifulSoup
import json
import gspread
from google.oauth2.service_account import Credentials

# =========================================================
# 0) 기본 설정
# =========================================================
st.set_page_config(
    layout="wide",
    page_title="BAEKJOON BINGO : FINAL",
    initial_sidebar_state="expanded"
)

GRID_SIZE = 5
MAX_LEVEL = 5
STATE_FILE = "bingo_state.pkl"  # 상태 저장 파일명
try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except FileNotFoundError:
    # 로컬 테스트용 (secrets.toml이 없을 경우)
    ADMIN_PASSWORD = "1234"

LEVEL_MAPPING = {
    1: "6..10",
    2: "11..15",
    3: "16..20",
    4: "21..25",
    5: "26..30",
}

SOLVED_SEARCH = "https://solved.ac/api/v3/search/problem"
SOLVED_USER_SHOW = "https://solved.ac/api/v3/user/show"

def get_headers():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# =========================================================
# solved.ac 티어 변환
# =========================================================
TIER_NAMES = [
    "Unrated",
    "Bronze V","Bronze IV","Bronze III","Bronze II","Bronze I",
    "Silver V","Silver IV","Silver III","Silver II","Silver I",
    "Gold V","Gold IV","Gold III","Gold II","Gold I",
    "Platinum V","Platinum IV","Platinum III","Platinum II","Platinum I",
    "Diamond V","Diamond IV","Diamond III","Diamond II","Diamond I",
    "Ruby V","Ruby IV","Ruby III","Ruby II","Ruby I"
]

def tier_to_name(tier: int):
    if tier is None:
        return "?"
    if 0 <= tier < len(TIER_NAMES):
        return TIER_NAMES[tier]
    return str(tier)


# =========================================================
# 1) UI (CSS 스타일)
# =========================================================
st.markdown("""
<style>
/* [핵심] Streamlit 시스템의 'Running' 상태 표시 숨기기 */
div[data-testid="stStatusWidget"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
}

/* 사이드바 여닫기 버튼 강제 표시 */
[data-testid="stSidebarCollapsedControl"] {
    display: block !important;
    color: white !important;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 5px;
    z-index: 999999 !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
    pointer-events: none;
}
header[data-testid="stHeader"] > div {
    pointer-events: auto;
}

.block-container {
    padding-top: 3rem !important;
    padding-bottom: 2rem !important;
}

:root{
  --bg:#0b1220;
  --panel:#101a2f;
  --card:#0f1a30;
  --border:rgba(255,255,255,.09);
  --text:#eaf1ff;
  --muted:#b9c5e6;
  --muted2:#8ea0c9;
  --red1:#ff4d6d;
  --red2:#c9184a;
  --blue1:#4dabf7;
  --blue2:#1864ab;
  --shadow: 0 14px 35px rgba(0,0,0,.35);
}

.stApp{
  background: radial-gradient(1200px 600px at 30% 10%, rgba(77,171,247,.15), transparent 55%),
              radial-gradient(900px 600px at 80% 30%, rgba(255,77,109,.12), transparent 55%),
              var(--bg);
  color: var(--text);
  font-family: 'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
}

h1,h2,h3,h4 { color: var(--text) !important; }

section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, rgba(16,26,47,.95), rgba(10,16,30,.95));
  border-right: 1px solid var(--border);
}

hr { border-color: rgba(255,255,255,.08) !important; }

a.problem-link{
  text-decoration:none;
  color: var(--muted);
  font-size: .78rem;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.03);
  display: inline-block;
}
a.problem-link:hover{
  color: var(--text);
  border-color: rgba(255,255,255,.2);
}

.bingo-card{
  position: relative;
  background: rgba(255,255,255,.03);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 14px 14px 12px 14px;
  min-height: 168px;
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: transform 0.2s ease;
}
.bingo-card:hover{
  border-color: rgba(255,255,255,.18);
  transform: translateY(-2px);
}

.badge{
  font-size: .72rem;
  padding: 6px 12px;
  border-radius: 999px;
  font-weight: 900;
  letter-spacing: .2px;
  border: 1px solid rgba(255,255,255,.10);
}
.lv-dots{
  font-size: .85rem;
  color: var(--muted2);
  letter-spacing: 1px;
}
.pid{
  font-size: 1.75rem;
  font-weight: 1000;
  letter-spacing: -0.8px;
  margin-top: 8px;
}
.ptitle{
  margin-top: 6px;
  font-size: .95rem;
  color: var(--muted);
  line-height: 1.25;
  min-height: 2.4em;
}
.card-bottom{
  margin-top: 12px;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.red-glow{
  box-shadow: 0 0 0 1px rgba(255,77,109,.25), 0 18px 40px rgba(255,77,109,.08);
}
.blue-glow{
  box-shadow: 0 0 0 1px rgba(77,171,247,.25), 0 18px 40px rgba(77,171,247,.08);
}

/* =======================
   팀 패널 UI
======================= */
.team-panel{
  background: rgba(255,255,255,.03);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 16px;
  box-shadow: var(--shadow);
}

.team-title{
  font-size: 1.1rem;
  font-weight: 1000;
  letter-spacing: -.4px;
  margin-bottom: 12px;
}

.player-card{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(255,255,255,.08);
  background: rgba(255,255,255,.02);
  margin-bottom: 10px;
}

.player-left{
  display:flex;
  flex-direction:column;
  gap: 3px;
}

.player-handle{
  font-weight: 1000;
  font-size: 1.05rem;
}

.player-tier{
  color: var(--muted2);
  font-size: .85rem;
  font-weight: 800;
}

.player-right{
  text-align:right;
  display:flex;
  flex-direction:column;
  gap: 3px;
}

.capture-num{
  font-size: 1.25rem;
  font-weight: 1000;
}

.capture-label{
  color: rgba(255,255,255,.55);
  font-size: .78rem;
  font-weight: 800;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 2) 데이터 저장/불러오기 (Google Sheets 버전)
# =========================================================
# 구글 시트 이름 (아까 만드신 시트 이름과 똑같아야 합니다)
SHEET_NAME = "BingoData"

def get_google_sheet_connection():
    """Streamlit Secrets를 이용해 구글 시트 연결"""
    # Streamlit Secrets에서 인증 정보 가져오기
    credentials_dict = st.secrets["gcp_service_account"]
    
    # 인증 범위 설정
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = Credentials.from_service_account_info(
        credentials_dict, scopes=scopes
    )
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"구글 시트 연결 실패: {e}")
        return None

def save_state():
    """현재 세션 상태를 JSON으로 변환해 구글 시트 A1 셀에 저장"""
    # 저장할 데이터 추출
    keys_to_save = ["game_started", "red_users", "blue_users", "logs", "board", "participants"]
    data = {}
    for k in keys_to_save:
        if k in st.session_state:
            data[k] = st.session_state[k]
            
    # [중요] set 자료형(used_problem_ids)은 JSON 저장이 안 되므로 list로 변환
    if "used_problem_ids" in st.session_state:
        data["used_problem_ids"] = list(st.session_state.used_problem_ids)
    
    try:
        sheet = get_google_sheet_connection()
        if sheet:
            # JSON 문자열로 변환하여 A1 셀에 저장
            json_str = json.dumps(data, ensure_ascii=False)
            # 셀 내용이 너무 길 수 있으므로 update_acell 대신 update 사용 권장될 수 있으나 
            # A1 셀 하나에 통째로 넣습니다.
            sheet.update(range_name='A1', values=[[json_str]])
            # (옵션) 백업용으로 타임스탬프도 B1에 찍어줄 수 있음
            # sheet.update(range_name='B1', values=[[str(time.time())]])
    except Exception as e:
        print(f"Cloud Save failed: {e}")

def load_state():
    """구글 시트 A1 셀에서 JSON 데이터를 가져와 복구"""
    try:
        sheet = get_google_sheet_connection()
        if not sheet:
            return False
            
        # A1 셀 값 읽기
        val = sheet.acell('A1').value
        if not val:
            return False
            
        data = json.loads(val)
        
        # 데이터 복구
        for k, v in data.items():
            st.session_state[k] = v
            
        # [중요] list로 저장된 used_problem_ids를 다시 set으로 변환
        if "used_problem_ids" in data:
            st.session_state.used_problem_ids = set(data["used_problem_ids"])
            
        # 구버전 호환성 체크 (capturer)
        if "board" in st.session_state:
            board = st.session_state.board
            for r in range(len(board)):
                for c in range(len(board[r])):
                    if "capturer" not in board[r][c]:
                        board[r][c]["capturer"] = None
        
        return True
    except Exception as e:
        print(f"Cloud Load failed: {e}")
        return False

def clear_state():
    """구글 시트 데이터 삭제 (A1 셀 비우기)"""
    try:
        sheet = get_google_sheet_connection()
        if sheet:
            sheet.update(range_name='A1', values=[['']])
    except Exception as e:
        print(f"Cloud Clear failed: {e}")
        
    for k in list(st.session_state.keys()):
        del st.session_state[k]

# =========================================================
# 3) solved.ac + 백준 크롤링 로직
# =========================================================
@st.cache_data(ttl=600)
def solved_user_exists(handle: str) -> bool:
    try:
        res = requests.get(f"{SOLVED_USER_SHOW}?handle={handle}", timeout=3)
        return res.status_code == 200
    except:
        return False

@st.cache_data(ttl=600)
def fetch_user_tier(handle: str):
    try:
        res = requests.get(f"{SOLVED_USER_SHOW}?handle={handle}", timeout=3)
        if res.status_code != 200:
            return None
        return res.json().get("tier", None)
    except:
        return None

@st.cache_data(ttl=600)
def fetch_problems_with_filter(level: int, user_filter_query: str):
    tier_range = LEVEL_MAPPING.get(level, "6..10")
    query = f"tier:{tier_range} solvable:true lang:ko {user_filter_query}".strip()

    params = {
        "query": query,
        "sort": "random", 
        "direction": "asc",
        "page": 1,
    }
    try:
        res = requests.get(SOLVED_SEARCH, params=params, timeout=3)
        if res.status_code == 200:
            return res.json().get("items", [])
    except:
        pass
    return []

def get_submission_id(user_id: str, problem_id: int):
    url = f"https://www.acmicpc.net/status?problem_id={problem_id}&user_id={user_id}&result_id=4"
    try:
        res = requests.get(url, headers=get_headers(), timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("tbody tr")

        best = float("inf")
        for row in rows:
            tds = row.find_all("td")
            if not tds:
                continue
            try:
                sid = int(tds[0].text.strip())
                best = min(best, sid)
            except:
                pass
        return best
    except:
        return float("inf")

def check_single_cell_logic(cell_info, participants):
    pid = cell_info["problemId"]

    # ---------------------------------------------------------
    # [변경점] Solved.ac API 확인 로직을 전부 삭제했습니다.
    # 이제 무조건 백준 사이트 채점 현황판을 직접 확인합니다.
    # ---------------------------------------------------------

    min_sub_id = float("inf")
    winner_team = None
    winner_id = None

    # 모든 참가자에 대해 백준 채점 현황(맞았습니다)을 조회
    for user_id, team in participants.items():
        # 이 함수가 백준 사이트(acmicpc.net/status)를 직접 긁어옵니다.
        sub_id = get_submission_id(user_id, pid)
        
        # 크롤링 성공 시 (제출 번호가 inf가 아님)
        if sub_id != float("inf"):
            # 가장 옛날에 푼 사람(제출 번호가 작은 사람)이 우선권을 가짐
            if sub_id < min_sub_id:
                min_sub_id = sub_id
                winner_team = team
                winner_id = user_id

    return winner_team, winner_id


# =========================================================
# 4) 게임 로직
# =========================================================
def init_state():
    if "game_started" not in st.session_state:
        loaded = load_state()
        if not loaded:
            st.session_state.game_started = False
            st.session_state.red_users = []
            st.session_state.blue_users = []
            st.session_state.logs = []
            st.session_state.used_problem_ids = set()

def add_log(msg: str):
    st.session_state.logs.insert(0, msg)
    st.session_state.logs = st.session_state.logs[:7]
    save_state()

def build_participants():
    p = {}
    for u in st.session_state.red_users:
        p[u] = "RED"
    for u in st.session_state.blue_users:
        p[u] = "BLUE"
    return p

def init_game():
    board = []
    participants = build_participants()
    st.session_state.participants = participants
    st.session_state.used_problem_ids = set() 

    filter_query = " ".join([f"-s@{u}" for u in participants.keys()]).strip()

    problem_pool = {}
    
    # [수정] 스피너 제거 (즉시 실행)
    for lv in range(1, MAX_LEVEL + 1):
        items = fetch_problems_with_filter(lv, filter_query)
        if not items:
            items = fetch_problems_with_filter(lv, "")
        problem_pool[lv] = items

    candidates = problem_pool.get(1, [])
    
    if len(candidates) >= GRID_SIZE * GRID_SIZE:
        selected_problems = random.sample(candidates, GRID_SIZE * GRID_SIZE)
    else:
        selected_problems = [random.choice(candidates) for _ in range(GRID_SIZE * GRID_SIZE)] if candidates else []

    if not selected_problems:
        fallback_p = {"problemId": 0, "titleKo": "문제 부족", "level": 0}
        selected_problems = [fallback_p] * 25

    idx = 0
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            p = selected_problems[idx]
            idx += 1
            st.session_state.used_problem_ids.add(p["problemId"])
            
            # capturer: 누가 점령했는지 저장
            row.append({"owner": None, "capturer": None, "level": 1, "info": p})
            
        board.append(row)

    st.session_state.board = board
    st.session_state.game_started = True
    st.session_state.logs = []
    add_log("게임 시작!")
    save_state()

def update_cell_after_win(cell, winner_team, winner_id):
    participants = st.session_state.participants
    old_pid = cell["info"]["problemId"]
    
    if old_pid in st.session_state.used_problem_ids:
        st.session_state.used_problem_ids.remove(old_pid)

    cell["owner"] = winner_team
    cell["capturer"] = winner_id  # NEW

    next_lv = cell["level"] + 1 if cell["level"] < MAX_LEVEL else MAX_LEVEL

    filter_q = " ".join([f"-s@{u}" for u in participants.keys()]).strip()
    new_items = fetch_problems_with_filter(next_lv, filter_q)
    if not new_items:
        new_items = fetch_problems_with_filter(next_lv, "")

    if new_items:
        candidates = [
            item for item in new_items 
            if item["problemId"] not in st.session_state.used_problem_ids
        ]
        
        if not candidates:
            candidates = new_items
            
        picked = random.choice(candidates)
        cell["info"] = picked
        cell["level"] = next_lv
        st.session_state.used_problem_ids.add(picked["problemId"])

    add_log(f"{winner_team} 점령! #{old_pid} (by {winner_id})")
    save_state()

def check_cell_worker(r, c, cell_info, participants):
    w_team, w_id = check_single_cell_logic(cell_info, participants)
    return (r, c, w_team, w_id)

def scan_all_cells_parallel():
    board = st.session_state.board
    participants = st.session_state.participants
    
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                cell = board[r][c]
                tasks.append(
                    executor.submit(check_cell_worker, r, c, cell['info'], participants)
                )
    
    results = [f.result() for f in concurrent.futures.as_completed(tasks)]
    
    changes = 0
    for r, c, w_team, w_id in results:
        if w_team:
            cell = board[r][c]
            if cell["owner"] != w_team:
                update_cell_after_win(cell, w_team, w_id)
                changes += 1
    
    if changes > 0:
        st.toast(f"{changes}개의 타일이 점령되었습니다!", icon="🎉")
        st.rerun()
    else:
        st.toast("변동 사항이 없습니다.", icon="💤")

def check_winner():
    board = st.session_state.board
    lines = []

    for i in range(GRID_SIZE):
        lines.append([(i, c) for c in range(GRID_SIZE)])
        lines.append([(r, i) for r in range(GRID_SIZE)])

    lines.append([(i, i) for i in range(GRID_SIZE)])
    lines.append([(i, GRID_SIZE - 1 - i) for i in range(GRID_SIZE)])

    r_cnt, b_cnt = 0, 0
    for line in lines:
        owners = [board[r][c]["owner"] for r, c in line]
        if all(o == "RED" for o in owners):
            r_cnt += 1
        if all(o == "BLUE" for o in owners):
            b_cnt += 1
    return r_cnt, b_cnt

def render_cell_html(cell):
    pid = cell["info"]["problemId"]
    title = cell["info"].get("titleKo", "")
    owner = cell.get("owner")
    lv = cell["level"]

    dots = "●" * lv + "○" * (5 - lv)

    if owner == "RED":
        badge = "<span class='badge' style='background:linear-gradient(90deg,var(--red1),var(--red2)); color:white;'>RED</span>"
        extra = "red-glow"
    elif owner == "BLUE":
        badge = "<span class='badge' style='background:linear-gradient(90deg,var(--blue1),var(--blue2)); color:white;'>BLUE</span>"
        extra = "blue-glow"
    else:
        badge = "<span class='badge' style='background:rgba(255,255,255,.06); color:var(--text);'>NEUTRAL</span>"
        extra = ""

    return f"""
    <div class="bingo-card {extra}">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
        <div class="lv-dots">{dots}</div>
        {badge}
      </div>

      <div>
        <div class="pid">#{pid}</div>
        <div class="ptitle">{title}</div>
      </div>

      <div class="card-bottom">
        <a class="problem-link" href="https://www.acmicpc.net/problem/{pid}" target="_blank">OPEN</a>
        <div style="color:var(--muted2); font-size:.8rem; font-weight:800;">Lv.{lv}</div>
      </div>
    </div>
    """

def count_captures_by_user(board):
    cnt = {}
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            cap = board[r][c].get("capturer")
            if cap:
                cnt[cap] = cnt.get(cap, 0) + 1
    return cnt

def render_team_panel_html(team_name: str, users: list, cap_cnt: dict):
    is_red = (team_name == "RED")
    grad = "linear-gradient(90deg,var(--red1),var(--red2))" if is_red else "linear-gradient(90deg,var(--blue1),var(--blue2))"
    icon = "🔴" if is_red else "🔵"
    
    enriched = []
    for u in users:
        tier = fetch_user_tier(u)
        tier_name = tier_to_name(tier)
        captured = cap_cnt.get(u, 0)
        enriched.append((u, tier, tier_name, captured))
    
    # 정렬: 점령수(내림) > 티어(내림) > 이름(오름)
    enriched.sort(key=lambda x: (-x[3], -(x[1] or 0), x[0].lower()))
    
    players_html = ""
    if not enriched:
        players_html = "<div style='color:rgba(255,255,255,.55); font-weight:800;'>(없음)</div>"
    else:
        for u, tier, tier_name, captured in enriched:
            # [수정] 들여쓰기 제거 (마크다운 코드 블록 인식 방지)
            players_html += f"""
<div class="player-card">
  <div class="player-left">
    <div class="player-handle">{u}</div>
    <div class="player-tier">{tier_name}</div>
  </div>
  <div class="player-right">
    <div class="capture-num">{captured}</div>
    <div class="capture-label">CAPTURED</div>
  </div>
</div>"""
    
    # [수정] 반환 문자열 들여쓰기 제거
    return f"""
<div class="team-panel">
  <div class="team-title" style="background:{grad}; -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
    {icon} {team_name} TEAM
  </div>
  {players_html}
</div>"""


# =========================================================
# 6) 메인 UI
# =========================================================
init_state()

st.markdown("""
<div style="margin-bottom: 20px;">
  <div style="font-size: .95rem; color: var(--muted2); font-weight: 800; letter-spacing: .5px;">
    ⚔️ BAEKJOON
  </div>
  <div style="font-size: 2.4rem; font-weight: 1000; letter-spacing: -1px;">
    BINGO ARENA
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바: 컨트롤
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎮 Game Control")
    st.markdown("---")

    if not st.session_state.game_started:
        st.markdown("### 🔴 RED TEAM")
        red_handle = st.text_input("RED 플레이어 추가", key="red_add_input", placeholder="예: baekjoon")

        if st.button("➕ RED 추가", use_container_width=True):
            h = red_handle.strip()
            if h:
                if h not in st.session_state.red_users and h not in st.session_state.blue_users:
                    if solved_user_exists(h):
                        st.session_state.red_users.append(h)
                        st.success(f"추가: {h}")
                        save_state()
                    else:
                        st.error("존재하지 않는 유저")
                else:
                    st.warning("중복된 유저")

        for u in st.session_state.red_users:
            colA, colB = st.columns([4, 1])
            with colA: st.write(f"• {u}")
            with colB:
                if st.button("✖", key=f"del_red_{u}"):
                    st.session_state.red_users.remove(u)
                    save_state()
                    st.rerun()

        st.markdown("---")

        st.markdown("### 🔵 BLUE TEAM")
        blue_handle = st.text_input("BLUE 플레이어 추가", key="blue_add_input", placeholder="예: startlink")

        if st.button("➕ BLUE 추가", use_container_width=True):
            h = blue_handle.strip()
            if h:
                if h not in st.session_state.red_users and h not in st.session_state.blue_users:
                    if solved_user_exists(h):
                        st.session_state.blue_users.append(h)
                        st.success(f"추가: {h}")
                        save_state()
                    else:
                        st.error("존재하지 않는 유저")
                else:
                    st.warning("중복된 유저")

        for u in st.session_state.blue_users:
            colA, colB = st.columns([4, 1])
            with colA: st.write(f"• {u}")
            with colB:
                if st.button("✖", key=f"del_blue_{u}"):
                    st.session_state.blue_users.remove(u)
                    save_state()
                    st.rerun()

        st.markdown("---")

        can_start = len(st.session_state.red_users) > 0 and len(st.session_state.blue_users) > 0
        if st.button("🚀 START GAME", type="primary", use_container_width=True, disabled=not can_start):
            init_game()
            st.rerun()

    else:
        st.success("🟢 게임 진행 중")
        
        st.markdown("### ⚡ Action")
        if st.button("🔄 업데이트", type="primary", use_container_width=True):
            scan_all_cells_parallel()

        st.markdown("---")

        st.markdown("### 📜 Recent Events")
        if st.session_state.logs:
            for x in st.session_state.logs:
                st.write("• " + x)
        else:
            st.write("• (아직 없음)")

        st.markdown("---")

        st.markdown("### ⛔ Reset Game")
        with st.expander("관리자 모드"):
            admin_pw = st.text_input("관리자 암호", type="password", key="admin_pw")
            if st.button("❌ 게임 종료", use_container_width=True):
                if admin_pw == ADMIN_PASSWORD:
                    clear_state()
                    st.rerun()
                else:
                    st.error("암호가 올바르지 않습니다.")

# ---------------------------------------------------------
# 게임 시작 전이면 종료 및 안내 메시지
# ---------------------------------------------------------
if not st.session_state.game_started:
    st.info("👈 왼쪽 사이드바를 열어 플레이어를 등록하고 게임을 시작하세요!")
    st.stop()

# ---------------------------------------------------------
# 상단 HUD 점수판
# ---------------------------------------------------------
r_score, b_score = check_winner()

hud1, hud2, hud3 = st.columns([1, 1, 1])
with hud1:
    st.markdown(f"""
    <div style="background:rgba(255,77,109,.10); border:1px solid rgba(255,77,109,.22);
                border-radius:18px; padding:14px; text-align:center;">
      <div style="font-weight:1000; color:#ffd6de;">🔴 RED</div>
      <div style="font-size:2.3rem; font-weight:1000; color:white; margin-top:2px;">{r_score}</div>
      <div style="color:rgba(255,255,255,.55); font-size:.85rem;">BINGO LINES</div>
    </div>
    """, unsafe_allow_html=True)

with hud2:
    st.markdown(f"""
    <div style="background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.10);
                border-radius:18px; padding:14px; text-align:center;">
      <div style="font-weight:1000; color:var(--muted);">⚔️ MATCH</div>
      <div style="font-size:1.05rem; font-weight:900; color:white; margin-top:6px;">
        Use Sidebar to Update
      </div>
      <div style="color:rgba(255,255,255,.55); font-size:.85rem; margin-top:4px;">
        Last UI render: {time.strftime('%H:%M:%S')}
      </div>
    </div>
    """, unsafe_allow_html=True)

with hud3:
    st.markdown(f"""
    <div style="background:rgba(77,171,247,.10); border:1px solid rgba(77,171,247,.22);
                border-radius:18px; padding:14px; text-align:center;">
      <div style="font-weight:1000; color:#d6ecff;">🔵 BLUE</div>
      <div style="font-size:2.3rem; font-weight:1000; color:white; margin-top:2px;">{b_score}</div>
      <div style="color:rgba(255,255,255,.55); font-size:.85rem;">BINGO LINES</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 승리 연출
# ---------------------------------------------------------
if r_score >= 3 or b_score >= 3:
    win_team = "RED" if r_score >= 3 else "BLUE"
    color = "linear-gradient(90deg,var(--red1),var(--red2))" if win_team == "RED" else "linear-gradient(90deg,var(--blue1),var(--blue2))"
    st.balloons()
    st.markdown(f"""
    <div style="background:{color}; padding:18px; border-radius:22px;
                text-align:center; color:white; box-shadow: 0 18px 45px rgba(0,0,0,.35);
                margin-bottom: 18px;">
      <div style="font-size:1.7rem; font-weight:1000;">🏆 {win_team} TEAM VICTORY! 🏆</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 팀별 플레이어 패널 (NEW)
# ---------------------------------------------------------
cap_cnt = count_captures_by_user(st.session_state.board)

teamR, teamB = st.columns(2, gap="medium")
with teamR:
    st.markdown(render_team_panel_html("RED", st.session_state.red_users, cap_cnt), unsafe_allow_html=True)
with teamB:
    st.markdown(render_team_panel_html("BLUE", st.session_state.blue_users, cap_cnt), unsafe_allow_html=True)

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 빙고판 렌더링
# ---------------------------------------------------------
board = st.session_state.board

for r in range(GRID_SIZE):
    cols = st.columns(GRID_SIZE, gap="small")
    for c in range(GRID_SIZE):
        cell = board[r][c]
        with cols[c]:

            st.markdown(render_cell_html(cell), unsafe_allow_html=True)



