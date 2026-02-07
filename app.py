import streamlit as st
import requests
import re
import random
import time
import concurrent.futures
import json
import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

# =========================================================
# 0) 기본 설정
# =========================================================
st.set_page_config(
    layout="wide",
    page_title="BAEKJOON BINGO : SPEED",
    initial_sidebar_state="expanded"
)

GRID_SIZE = 5
MAX_LEVEL = 5
SHEET_NAME = "BingoData"  # 구글 시트 이름

try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except:
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
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

# =========================================================
# 1) UI (CSS 스타일)
# =========================================================
st.markdown("""
<style>
div[data-testid="stStatusWidget"] { visibility: hidden; height: 0%; position: fixed; }
[data-testid="stSidebarCollapsedControl"] {
    display: block !important; color: white !important;
    background-color: rgba(255, 255, 255, 0.1); border-radius: 5px; z-index: 999999 !important;
}
header[data-testid="stHeader"] { background: transparent !important; pointer-events: none; }
header[data-testid="stHeader"] > div { pointer-events: auto; }
.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }

:root{
  --bg:#0b1220; --panel:#101a2f; --card:#0f1a30; --border:rgba(255,255,255,.09);
  --text:#eaf1ff; --muted:#b9c5e6; --muted2:#8ea0c9;
  --red1:#ff4d6d; --red2:#c9184a; --blue1:#4dabf7; --blue2:#1864ab;
  --shadow: 0 14px 35px rgba(0,0,0,.35);
}
.stApp{
  background: radial-gradient(1200px 600px at 30% 10%, rgba(77,171,247,.15), transparent 55%),
              radial-gradient(900px 600px at 80% 30%, rgba(255,77,109,.12), transparent 55%),
              var(--bg);
  color: var(--text); font-family: 'Pretendard','Apple SD Gothic Neo',sans-serif;
}
h1,h2,h3,h4 { color: var(--text) !important; }
section[data-testid="stSidebar"]{ background: linear-gradient(180deg, rgba(16,26,47,.95), rgba(10,16,30,.95)); border-right: 1px solid var(--border); }
hr { border-color: rgba(255,255,255,.08) !important; }

a.problem-link{ text-decoration:none; color: var(--muted); font-size: .78rem; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,.03); display: inline-block; }
a.problem-link:hover{ color: var(--text); border-color: rgba(255,255,255,.2); }

.bingo-card{
  position: relative; background: rgba(255,255,255,.03); border: 1px solid var(--border);
  border-radius: 22px; padding: 14px 14px 12px 14px; min-height: 168px;
  box-shadow: var(--shadow); overflow: hidden; transition: transform 0.2s ease;
}
.bingo-card:hover{ border-color: rgba(255,255,255,.18); transform: translateY(-2px); }

.badge{ font-size: .72rem; padding: 6px 12px; border-radius: 999px; font-weight: 900; letter-spacing: .2px; border: 1px solid rgba(255,255,255,.10); }
.lv-dots{ font-size: .85rem; color: var(--muted2); letter-spacing: 1px; }
.pid{ font-size: 1.75rem; font-weight: 1000; letter-spacing: -0.8px; margin-top: 8px; }
.ptitle{ margin-top: 6px; font-size: .95rem; color: var(--muted); line-height: 1.25; min-height: 2.4em; }
.card-bottom{ margin-top: 12px; display:flex; justify-content:space-between; align-items:center; }
.red-glow{ box-shadow: 0 0 0 1px rgba(255,77,109,.25), 0 18px 40px rgba(255,77,109,.08); }
.blue-glow{ box-shadow: 0 0 0 1px rgba(77,171,247,.25), 0 18px 40px rgba(77,171,247,.08); }

.team-panel{ background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 22px; padding: 16px; box-shadow: var(--shadow); }
.team-title{ font-size: 1.1rem; font-weight: 1000; letter-spacing: -.4px; margin-bottom: 12px; }
.player-card{ display:flex; justify-content:space-between; align-items:center; gap: 12px; padding: 12px 14px; border-radius: 18px; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.02); margin-bottom: 10px; }
.player-left{ display:flex; flex-direction:column; gap: 3px; }
.player-handle{ font-weight: 1000; font-size: 1.05rem; }
.player-tier{ color: var(--muted2); font-size: .85rem; font-weight: 800; }
.player-right{ text-align:right; display:flex; flex-direction:column; gap: 3px; }
.capture-num{ font-size: 1.25rem; font-weight: 1000; }
.capture-label{ color: rgba(255,255,255,.55); font-size: .78rem; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2) 데이터 저장/불러오기 (Google Sheets)
# =========================================================
def get_google_sheet_connection():
    try:
        credentials_dict = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        st.error(f"구글 시트 연결 실패: {e}")
        return None

def save_state():
    keys = ["game_started", "red_users", "blue_users", "logs", "board", "participants"]
    data = {}
    for k in keys:
        if k in st.session_state:
            data[k] = st.session_state[k]
    if "used_problem_ids" in st.session_state:
        data["used_problem_ids"] = list(st.session_state.used_problem_ids)
    
    try:
        sheet = get_google_sheet_connection()
        if sheet:
            json_str = json.dumps(data, ensure_ascii=False)
            sheet.update(range_name='A1', values=[[json_str]])
    except Exception as e:
        print(f"Cloud Save failed: {e}")

def load_state():
    try:
        sheet = get_google_sheet_connection()
        if not sheet: return False
        val = sheet.acell('A1').value
        if not val: return False
        data = json.loads(val)
        for k, v in data.items():
            st.session_state[k] = v
        if "used_problem_ids" in data:
            st.session_state.used_problem_ids = set(data["used_problem_ids"])
        
        # 호환성: capturer 필드 추가
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
    try:
        sheet = get_google_sheet_connection()
        if sheet: sheet.update(range_name='A1', values=[['']])
    except: pass
    for k in list(st.session_state.keys()):
        del st.session_state[k]

# =========================================================
# 3) Solved.ac & Crawling (최적화 적용됨)
# =========================================================
TIER_NAMES = ["Unrated"] + [f"{r} {5-i}" for r in ["Bronze","Silver","Gold","Platinum","Diamond","Ruby"] for i in range(5)]
def tier_to_name(tier: int):
    if tier is None: return "?"
    return TIER_NAMES[tier] if 0 <= tier < len(TIER_NAMES) else str(tier)

@st.cache_data(ttl=600)
def solved_user_exists(handle: str):
    try:
        return requests.get(f"{SOLVED_USER_SHOW}?handle={handle}", timeout=3).status_code == 200
    except: return False

@st.cache_data(ttl=600)
def fetch_user_tier(handle: str):
    try:
        res = requests.get(f"{SOLVED_USER_SHOW}?handle={handle}", timeout=3)
        return res.json().get("tier") if res.status_code == 200 else None
    except: return None

@st.cache_data(ttl=600)
def fetch_problems_with_filter(level: int, user_filter_query: str):
    tier_range = LEVEL_MAPPING.get(level, "6..10")
    query = f"tier:{tier_range} solvable:true lang:ko {user_filter_query}".strip()
    try:
        res = requests.get(SOLVED_SEARCH, params={"query": query, "sort": "random", "page": 1}, timeout=3)
        return res.json().get("items", []) if res.status_code == 200 else []
    except: return []

# =========================================================
# [수정] 실시간 반영을 위한 하이브리드 크롤링
# =========================================================

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.acmicpc.net/",
    }

def get_user_solved_set(session, user_id: str):
    """
    [하이브리드 수집]
    1. 프로필 페이지: 전체 푼 문제 (업데이트 느림, 대량 데이터)
    2. 채점 현황판: 최근 푼 문제 (업데이트 즉시, 소량 데이터)
    => 두 결과를 합쳐서 반환합니다.
    """
    solved = set()
    
    # -----------------------------------------------------
    # 1. [실시간] 채점 현황판 크롤링 (가장 중요)
    # -----------------------------------------------------
    # result_id=4 (맞았습니다) 필터 적용
    url_status = f"https://www.acmicpc.net/status?user_id={user_id}&result_id=4"
    try:
        # 캐싱 방지용 헤더 추가
        headers = get_headers()
        headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        headers["Pragma"] = "no-cache"
        
        res = session.get(url_status, headers=headers, timeout=5)
        if res.status_code == 200:
            # 채점 현황판에 있는 문제 번호 링크(/problem/xxxx)를 정규식으로 모두 추출
            # BeautifulSoup보다 정규식이 빠르고 HTML 구조 변화에 강함
            found_ids = re.findall(r'/problem/(\d+)', res.text)
            for pid in found_ids:
                solved.add(int(pid))
        else:
            print(f"Status check failed for {user_id} (Code: {res.status_code})")
    except Exception as e:
        print(f"Error fetching status for {user_id}: {e}")

    # -----------------------------------------------------
    # 2. [전체] 프로필 페이지 크롤링
    # -----------------------------------------------------
    url_profile = f"https://www.acmicpc.net/user/{user_id}"
    try:
        res = session.get(url_profile, headers=get_headers(), timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # '맞은 문제' 영역 찾기 (.problem-list)
            # 보통 첫 번째 .problem-list가 맞은 문제임
            problem_list_div = soup.select_one(".problem-list")
            
            if problem_list_div:
                links = problem_list_div.select("a")
                for link in links:
                    txt = link.text.strip()
                    if txt.isdigit():
                        solved.add(int(txt))
        else:
            print(f"Profile check failed for {user_id} (Code: {res.status_code})")
    except Exception as e:
        print(f"Error fetching profile for {user_id}: {e}")

    return solved

def get_submission_id_optimized(session, user_id: str, problem_id: int):
    """정밀 검사: 채점 현황판에서 제출 번호를 가져옴"""
    url = f"https://www.acmicpc.net/status?problem_id={problem_id}&user_id={user_id}&result_id=4"
    try:
        res = session.get(url, headers=get_headers(), timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("tbody tr")
        best = float("inf")
        for row in rows:
            tds = row.find_all("td")
            if tds:
                try:
                    best = min(best, int(tds[0].text.strip()))
                except: pass
        return best
    except: return float("inf")

# =========================================================
# 4) 게임 로직
# =========================================================
def init_state():
    if "game_started" not in st.session_state:
        if not load_state():
            st.session_state.game_started = False
            st.session_state.red_users = []
            st.session_state.blue_users = []
            st.session_state.logs = []
            st.session_state.used_problem_ids = set()

def add_log(msg: str):
    st.session_state.logs.insert(0, msg)
    st.session_state.logs = st.session_state.logs[:7]
    save_state()

def init_game():
    board = []
    participants = {}
    for u in st.session_state.red_users: participants[u] = "RED"
    for u in st.session_state.blue_users: participants[u] = "BLUE"
    st.session_state.participants = participants
    st.session_state.used_problem_ids = set()

    filter_query = " ".join([f"-s@{u}" for u in participants.keys()]).strip()
    
    # 문제 뽑기
    pool = []
    for _ in range(GRID_SIZE * GRID_SIZE):
        # 레벨 1 문제로 초기화
        items = fetch_problems_with_filter(1, filter_query)
        if not items: items = fetch_problems_with_filter(1, "")
        
        # 중복 방지 로직 (간단 구현)
        candidate = None
        for _ in range(5):
            c = random.choice(items) if items else {"problemId": 0, "titleKo": "문제 부족", "level": 0}
            if c["problemId"] not in st.session_state.used_problem_ids:
                candidate = c
                break
        if not candidate: candidate = items[0]
        
        pool.append(candidate)
        st.session_state.used_problem_ids.add(candidate["problemId"])

    idx = 0
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            row.append({"owner": None, "capturer": None, "level": 1, "info": pool[idx]})
            idx += 1
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
    cell["capturer"] = winner_id
    
    # 레벨업
    next_lv = min(cell["level"] + 1, MAX_LEVEL)
    
    # 새 문제 찾기
    filter_q = " ".join([f"-s@{u}" for u in participants.keys()]).strip()
    new_items = fetch_problems_with_filter(next_lv, filter_q)
    if not new_items: new_items = fetch_problems_with_filter(next_lv, "")
    
    picked = random.choice(new_items) if new_items else cell["info"]
    # 중복 회피 시도
    for _ in range(5):
        if picked["problemId"] not in st.session_state.used_problem_ids:
            break
        picked = random.choice(new_items)

    cell["info"] = picked
    cell["level"] = next_lv
    st.session_state.used_problem_ids.add(picked["problemId"])
    add_log(f"{winner_team} 점령! #{old_pid} (by {winner_id})")
    save_state()

def check_cell_worker_optimized(r, c, cell_info, participants, solved_maps, session):
    pid = cell_info["problemId"]
    
    # 1. 푼 사람이 있는지 메모리에서 확인 (매우 빠름)
    candidates = [u for u in participants.keys() if pid in solved_maps.get(u, set())]
    if not candidates:
        return (r, c, None, None)

    # 2. 푼 사람이 있다면, '누가 가장 빨리 풀었나' 정밀 검사 (API 호출)
    min_sub_id = float("inf")
    winner_team = None
    winner_id = None

    for user_id in candidates:
        team = participants[user_id]
        sub_id = get_submission_id_optimized(session, user_id, pid)
        if sub_id != float("inf") and sub_id < min_sub_id:
            min_sub_id = sub_id
            winner_team = team
            winner_id = user_id

    return (r, c, winner_team, winner_id)

def scan_all_cells_parallel():
    board = st.session_state.board
    participants = st.session_state.participants
    solved_maps = {}
    
    # [최적화] 세션 하나로 모든 요청 처리
    with requests.Session() as session:
        session.headers.update(get_headers())
        
        # 1. 모든 참가자의 '푼 문제 목록' 한 번씩 긁어오기 (유저 수 N만큼 요청)
        for u in participants.keys():
            solved_maps[u] = get_user_solved_set(session, u)
        
        # 2. 각 셀 검사 (병렬 처리)
        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE):
                    cell = board[r][c]
                    # 이미 점령된 땅이어도 '스틸' 가능성이 있으므로 검사 (단, 주인 바뀔때만)
                    tasks.append(
                        executor.submit(check_cell_worker_optimized, 
                                        r, c, cell['info'], participants, solved_maps, session)
                    )
        
        results = [f.result() for f in concurrent.futures.as_completed(tasks)]
    
    changes = 0
    for r, c, w_team, w_id in results:
        if w_team:
            cell = board[r][c]
            # 새 주인이 나타났고, 기존 주인이 아니거나, 아직 주인이 없을 때
            if cell["owner"] != w_team:
                update_cell_after_win(cell, w_team, w_id)
                changes += 1
            # 같은 팀이지만 다른 사람이 더 빨리 푼 기록이 발견된 경우는 
            # 굳이 업데이트 안 해도 됨 (단순화)
    
    if changes > 0:
        st.toast(f"{changes}개의 타일이 점령되었습니다!", icon="🎉")
        time.sleep(1) # UI 갱신 대기
        st.rerun()
    else:
        st.toast("변동 사항이 없습니다.", icon="💤")

def check_winner():
    board = st.session_state.board
    lines = []
    # 가로, 세로
    for i in range(GRID_SIZE):
        lines.append([(i, c) for c in range(GRID_SIZE)])
        lines.append([(r, i) for r in range(GRID_SIZE)])
    # 대각선
    lines.append([(i, i) for i in range(GRID_SIZE)])
    lines.append([(i, GRID_SIZE - 1 - i) for i in range(GRID_SIZE)])

    r_cnt, b_cnt = 0, 0
    for line in lines:
        owners = [board[r][c]["owner"] for r, c in line]
        if all(o == "RED" for o in owners): r_cnt += 1
        if all(o == "BLUE" for o in owners): b_cnt += 1
    return r_cnt, b_cnt

# =========================================================
# 5) 렌더링 헬퍼
# =========================================================
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

def render_team_panel_html(team_name: str, users: list, cap_cnt: dict):
    is_red = (team_name == "RED")
    grad = "linear-gradient(90deg,var(--red1),var(--red2))" if is_red else "linear-gradient(90deg,var(--blue1),var(--blue2))"
    icon = "🔴" if is_red else "🔵"
    
    enriched = []
    for u in users:
        enriched.append((u, fetch_user_tier(u), cap_cnt.get(u, 0)))
    enriched.sort(key=lambda x: (-x[2], -(x[1] or 0), x[0].lower()))
    
    players_html = ""
    if not enriched:
        players_html = "<div style='color:rgba(255,255,255,.55); font-weight:800;'>(없음)</div>"
    else:
        for u, tier, captured in enriched:
            tier_name = tier_to_name(tier)
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
    
    return f"""
<div class="team-panel">
  <div class="team-title" style="background:{grad}; -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
    {icon} {team_name} TEAM
  </div>
  {players_html}
</div>"""

# =========================================================
# 6) 메인 실행
# =========================================================
init_state()

st.markdown("""
<div style="margin-bottom: 20px;">
  <div style="font-size: .95rem; color: var(--muted2); font-weight: 800; letter-spacing: .5px;">⚔️ BAEKJOON</div>
  <div style="font-size: 2.4rem; font-weight: 1000; letter-spacing: -1px;">BINGO ARENA <span style="font-size:1rem; color:#4dabf7;">SPEED</span></div>
</div>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("## 🎮 Game Control")
    st.markdown("---")
    
    if not st.session_state.game_started:
        # 팀 설정
        st.markdown("### 🔴 RED TEAM")
        r_in = st.text_input("RED 추가", key="r_in")
        if st.button("➕ RED 추가", use_container_width=True):
            if r_in and r_in not in st.session_state.red_users and r_in not in st.session_state.blue_users:
                if solved_user_exists(r_in): st.session_state.red_users.append(r_in)
                else: st.error("존재하지 않음")
        for u in st.session_state.red_users:
            c1, c2 = st.columns([4,1])
            c1.write(f"• {u}")
            if c2.button("x", key=f"dr_{u}"): 
                st.session_state.red_users.remove(u)
                st.rerun()

        st.markdown("### 🔵 BLUE TEAM")
        b_in = st.text_input("BLUE 추가", key="b_in")
        if st.button("➕ BLUE 추가", use_container_width=True):
            if b_in and b_in not in st.session_state.red_users and b_in not in st.session_state.blue_users:
                if solved_user_exists(b_in): st.session_state.blue_users.append(b_in)
                else: st.error("존재하지 않음")
        for u in st.session_state.blue_users:
            c1, c2 = st.columns([4,1])
            c1.write(f"• {u}")
            if c2.button("x", key=f"db_{u}"): 
                st.session_state.blue_users.remove(u)
                st.rerun()

        st.markdown("---")
        if st.button("🚀 START GAME", type="primary", use_container_width=True, 
                     disabled=not (st.session_state.red_users and st.session_state.blue_users)):
            init_game()
            st.rerun()
    else:
        st.success("🟢 게임 진행 중")
        st.markdown("### ⚡ Action")
        if st.button("🔄 업데이트", type="primary", use_container_width=True):
            with st.spinner("채점 현황 분석 중... (최적화 모드)"):
                scan_all_cells_parallel()
        
        st.markdown("---")
        st.markdown("### 📜 Logs")
        for x in st.session_state.logs: st.write("• "+x)
        
        st.markdown("---")
        with st.expander("관리자 모드"):
            pw = st.text_input("Admin PW", type="password")
            if st.button("❌ 게임 초기화", use_container_width=True):
                if pw == ADMIN_PASSWORD:
                    clear_state()
                    st.rerun()
                else: st.error("비번 오류")

if not st.session_state.game_started:
    st.info("👈 왼쪽 사이드바에서 플레이어를 등록하고 게임을 시작하세요!")
    st.stop()

# 점수판
r_score, b_score = check_winner()
c1, c2, c3 = st.columns(3)
c1.markdown(f"""<div style="background:rgba(255,77,109,.1); border:1px solid rgba(255,77,109,.3); border-radius:18px; padding:15px; text-align:center;">
<div style="color:#ffd6de; font-weight:900;">🔴 RED</div><div style="font-size:2.2rem; font-weight:1000;">{r_score}</div></div>""", unsafe_allow_html=True)

c2.markdown(f"""<div style="background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.1); border-radius:18px; padding:15px; text-align:center;">
<div style="color:var(--muted); font-weight:900;">STATUS</div><div style="font-size:1rem; margin-top:10px;">Running</div></div>""", unsafe_allow_html=True)

c3.markdown(f"""<div style="background:rgba(77,171,247,.1); border:1px solid rgba(77,171,247,.3); border-radius:18px; padding:15px; text-align:center;">
<div style="color:#d6ecff; font-weight:900;">🔵 BLUE</div><div style="font-size:2.2rem; font-weight:1000;">{b_score}</div></div>""", unsafe_allow_html=True)

st.write("")

# 승리
if r_score >= 3 or b_score >= 3:
    win = "RED" if r_score >= 3 else "BLUE"
    bg = "linear-gradient(90deg,var(--red1),var(--red2))" if win=="RED" else "linear-gradient(90deg,var(--blue1),var(--blue2))"
    st.balloons()
    st.markdown(f"""<div style="background:{bg}; padding:20px; border-radius:20px; text-align:center; font-size:1.8rem; font-weight:1000; box-shadow:0 10px 30px rgba(0,0,0,.5);">🏆 {win} WIN! 🏆</div>""", unsafe_allow_html=True)

# 팀 패널
cap_cnt = {}
for r in range(GRID_SIZE):
    for c in range(GRID_SIZE):
        cp = st.session_state.board[r][c].get("capturer")
        if cp: cap_cnt[cp] = cap_cnt.get(cp, 0) + 1

tc1, tc2 = st.columns(2, gap="medium")
tc1.markdown(render_team_panel_html("RED", st.session_state.red_users, cap_cnt), unsafe_allow_html=True)
tc2.markdown(render_team_panel_html("BLUE", st.session_state.blue_users, cap_cnt), unsafe_allow_html=True)

st.write("")

# 빙고판
board = st.session_state.board
for r in range(GRID_SIZE):
    cols = st.columns(GRID_SIZE, gap="small")
    for c in range(GRID_SIZE):
        with cols[c]:
            st.markdown(render_cell_html(board[r][c]), unsafe_allow_html=True)


