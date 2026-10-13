import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date

# -------------------------------------------------------------
# 1. Google Apps Script Web App URL 설정
# -------------------------------------------------------------
GAS_URL = "https://script.google.com/macros/s/AKfycbz2FbQaTcmPAx-DMJGnNmhrBTBc6ZZJHd2ASmm4YWPaGzuQ7OvSL-4Gf02XFx_Vqv7ZDw/exec"

st.set_page_config(page_title="Focus Mission Control", page_icon="⏱️", layout="centered")
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("⏱️ Focus Mission Control")

# -------------------------------------------------------------
# 2. 통신 함수 (GAS API 연동)
# -------------------------------------------------------------
def fetch_sheet_data(sheet_name):
    try:
        res = requests.get(f"{GAS_URL}?sheet={sheet_name}", timeout=8)
        if res.status_code == 200 and res.text:
            return pd.DataFrame(res.json())
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
    return pd.DataFrame()

def post_to_gas(payload):
    try:
        requests.post(GAS_URL, json=payload, timeout=8)
    except Exception as e:
        st.error(f"저장 실패: {e}")

# -------------------------------------------------------------
# 3. 날짜 선택 및 과거/오늘 모드 판별
# -------------------------------------------------------------
today_date = date.today()
today_str = today_date.strftime("%Y-%m-%d")

selected_d = st.date_input("📅 날짜 선택 (과거 기록 조회 가능)", today_date)
selected_date = selected_d.strftime("%Y-%m-%d")

is_today = (selected_d == today_date)

if not is_today:
    st.info(f"🔒 **{selected_date} 과거 기록 조회 모드 (읽기 전용)** — 신규 등록 및 시간 조작은 오늘 날짜만 가능합니다.")

# -------------------------------------------------------------
# 4. [A] 새 미션 등록 (오늘 날짜 전용)
# -------------------------------------------------------------
if is_today:
    with st.expander("➕ 새 과제/도서 등록", expanded=False):
        col_cat, col_name = st.columns([1, 2])
        with col_cat:
            category = st.selectbox("카테고리", ["오늘 읽을 책/챕터", "학교 과제/숙제", "기타(산책/청소 등)"])
        with col_name:
            hints = {
                "오늘 읽을 책/챕터": "예: 찰리손 Book 2",
                "학교 과제/숙제": "예: BF history, 수학 문제 1장",
                "기타(산책/청소 등)": "예: 카이 개 산책, 방 청소"
            }
            task_name = st.text_input("제목", placeholder=hints[category])
        
        if st.button("목록에 추가"):
            if task_name.strip():
                post_to_gas({
                    "action": "add_task",
                    "record_date": selected_date,
                    "category": category,
                    "task_name": task_name.strip()
                })
                st.success("등록 완료!")
                st.rerun()

# -------------------------------------------------------------
# 5. [B] 미션 리스트 (오늘: 제어 가능 / 과거: 조회 전용)
# -------------------------------------------------------------
st.subheader(f"📋 {selected_date} 미션 현황")

tasks_df = fetch_sheet_data("tasks")
logs_df = fetch_sheet_data("time_logs")

day_tasks = pd.DataFrame()
if not tasks_df.empty and "record_date" in tasks_df.columns:
    tasks_df["clean_date"] = tasks_df["record_date"].astype(str).apply(lambda x: x[:10] if len(x) >= 10 else x)
    day_tasks = tasks_df[tasks_df["clean_date"] == selected_date]

if day_tasks.empty:
    st.warning(f"선택하신 날짜({selected_date})에는 기록된 미션이 없습니다.")
else:
    for _, task in day_tasks.iterrows():
        t_id = int(task["id"])
        t_cat = str(task["category"])
        t_name = str(task["task_name"])
        is_active = bool(int(task["is_active"])) if str(task["is_active"]).isdigit() else False

        # 해당 Task의 세션 필터
        t_logs = pd.DataFrame()
        if not logs_df.empty and "task_id" in logs_df.columns:
            t_logs = logs_df[logs_df["task_id"].astype(str) == str(t_id)]

        total_mins = 0.0
        if not t_logs.empty and "duration_minutes" in t_logs.columns:
            total_mins = pd.to_numeric(t_logs["duration_minutes"], errors="coerce").fillna(0).sum()
        
        hrs, mins = int(total_mins // 60), int(total_mins % 60)
        time_display = f"{hrs}시간 {mins}분" if hrs > 0 else f"{mins}분"

        # 카드 컨테이너
        with st.container(border=True):
            col_info, col_act = st.columns([3, 2])
            
            with col_info:
                st.markdown(f"**[{t_cat}]** {t_name}")
                if is_active and is_today:
                    st.markdown("🔥 <span style='color:#ff4b4b; font-weight:bold;'>진행 중 (타이머 작동 중)</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"총 순공: **{time_display}** ({len(t_logs)}회 세션)")

            with col_act:
                if not is_today:
                    st.caption("✅ 기록 완료 (수정 불가)")
                else:
                    if not is_active:
                        if t_cat == "오늘 읽을 책/챕터":
                            with st.popover("📖 독서 시작"):
                                last_p = 1
                                if not t_logs.empty and "end_page" in t_logs.columns:
                                    valid_ep = pd.to_numeric(t_logs["end_page"], errors="coerce").dropna()
                                    if not valid_ep.empty:
                                        last_p = int(valid_ep.iloc[-1]) + 1
                                
                                sp_val = st.number_input("시작 페이지 넘버", min_value=1, value=last_p, step=1, key=f"sp_{t_id}")
                                st_override = st.text_input("시작 시각(필요시 수정)", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key=f"st_ov_{t_id}")
                                
                                if st.button("지금부터 독서 시작", key=f"btn_start_b_{t_id}", type="primary"):
                                    post_to_gas({
                                        "action": "start_session",
                                        "task_id": t_id,
                                        "start_time": st_override,
                                        "start_page": int(sp_val)
                                    })
                                    st.rerun()
                        else:
                            if st.button("▶ 작업 시작", key=f"start_{t_id}"):
                                post_to_gas({
                                    "action": "start_session",
                                    "task_id": t_id,
                                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                })
                                st.rerun()
                    else:
                        if t_cat == "오늘 읽을 책/챕터":
                            with st.popover("⏸️ 독서 멈춤 (끝 페이지 넘버 입력)"):
                                active_mask = pd.Series([False] * len(t_logs))
                                if not t_logs.empty and "end_time" in t_logs.columns:
                                    active_mask = t_logs["end_time"].isna() | (t_logs["end_time"].astype(str).str.strip() == "") | (t_logs["end_time"].astype(str).str.lower() == "none")
                                active_log = t_logs[active_mask]
                                
                                curr_sp = 1
                                if not active_log.empty and "start_page" in active_log.columns:
                                    val = active_log.iloc[-1]["start_page"]
                                    if pd.notnull(val) and str(val).isdigit():
                                        curr_sp = int(val)
                                        
                                ep_val = st.number_input("읽은 끝 페이지 넘버", min_value=curr_sp, value=curr_sp + 5, step=1, key=f"ep_{t_id}")
                                et_override = st.text_input("종료 시각(필요시 수정)", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key=f"et_ov_{t_id}")
                                
                                if st.button("독서 세션 종료 (휴식)", key=f"btn_stop_b_{t_id}", type="primary"):
                                    try:
                                        end_dt = datetime.strptime(et_override, "%Y-%m-%d %H:%M:%S")
                                    except Exception:
                                        end_dt = datetime.now()
                                        et_override = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    if not active_log.empty:
                                        start_str = str(active_log.iloc[-1]["start_time"])
                                    else:
                                        start_str = et_override
                                    
                                    try:
                                        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                                    except Exception:
                                        start_dt = end_dt
                                        
                                    duration = max(0.1, round((end_dt - start_dt).total_seconds() / 60.0, 1))
                                    pages_read = int(ep_val - curr_sp + 1)
                                    
                                    post_to_gas({
                                        "action": "stop_session",
                                        "task_id": t_id,
                                        "end_time": et_override,
                                        "duration": duration,
                                        "start_page": curr_sp,
                                        "end_page": int(ep_val),
                                        "pages_read": pages_read
                                    })
                                    st.rerun()
                        else:
                            if st.button("⏸️ 작업 멈춤 (휴식)", key=f"stop_{t_id}", type="primary"):
                                now = datetime.now()
                                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                                
                                active_mask = pd.Series([False] * len(t_logs))
                                if not t_logs.empty and "end_time" in t_logs.columns:
                                    active_mask = t_logs["end_time"].isna() | (t_logs["end_time"].astype(str).str.strip() == "") | (t_logs["end_time"].astype(str).str.lower() == "none")
                                active_log = t_logs[active_mask]
                                
                                duration = 0.0
                                if not active_log.empty:
                                    s_str = str(active_log.iloc[-1]["start_time"])
                                    try:
                                        s_dt = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
                                        duration = max(0.1, round((now - s_dt).total_seconds() / 60.0, 1))
                                    except Exception:
                                        duration = 1.0
                                
                                post_to_gas({
                                    "action": "stop_session",
                                    "task_id": t_id,
                                    "end_time": now_str,
                                    "duration": duration
                                })
                                st.rerun()

            # 세션 이력 & 독서 페이스 확인
            if not t_logs.empty:
                with st.expander(f"세부 세션 기록 ({len(t_logs)}건)"):
                    for _, row in t_logs.iterrows():
                        s_time = str(row["start_time"]).split(" ")[1][:5] if pd.notnull(row.get("start_time")) and " " in str(row.get("start_time")) else "-"
                        e_time = str(row["end_time"]).split(" ")[1][:5] if pd.notnull(row.get("end_time")) and " " in str(row.get("end_time")) else "진행 중"
                        dur = row.get("duration_minutes", 0)
                        txt = f"• {s_time} ~ {e_time} ({dur}분)"
                        
                        if pd.notnull(row.get("pages_read")) and str(row["pages_read"]).isdigit() and dur:
                            p_read = int(row["pages_read"])
                            dur_num = float(dur)
                            if dur_num > 0:
                                pace_10m = round((p_read / dur_num) * 10, 1)
                                sec_p = round((dur_num * 60) / p_read)
                                mp, sp_rem = divmod(sec_p, 60)
                                txt += f" | 📖 p.{int(row['start_page'])}~{int(row['end_page'])} ({p_read}쪽) ➔ ⚡ **10분당 {pace_10m}쪽** (쪽당 {mp}분 {sp_rem}초)"
                        st.markdown(txt)

# -------------------------------------------------------------
# 6. [C] 통계 리포트 (선택한 날짜 기준)
# -------------------------------------------------------------
st.divider()
st.subheader(f"📊 {selected_date} 통계 리포트")

if not day_tasks.empty and not logs_df.empty:
    m = pd.merge(day_tasks, logs_df, left_on="id", right_on="task_id")
    m_done = pd.DataFrame()
    if not m.empty and "duration_minutes" in m.columns:
        valid_mask = m["duration_minutes"].notna() & (m["duration_minutes"].astype(str).str.strip() != "")
        m_done = m[valid_mask].copy()

    if not m_done.empty:
        m_done["duration_minutes"] = pd.to_numeric(m_done["duration_minutes"], errors="coerce").fillna(0)
        tot_d = m_done["duration_minutes"].sum()
        th, tm = int(tot_d // 60), int(tot_d % 60)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("총 순공", f"{th}시간 {tm}분")
        c2.metric("완료 세션", f"{len(m_done)}회")
        
        if "pages_read" in m_done.columns:
            tot_p = pd.to_numeric(m_done["pages_read"], errors="coerce").sum()
            c3.metric("읽은 쪽수", f"{int(tot_p)}쪽" if tot_p > 0 else "-")
        else:
            c3.metric("읽은 쪽수", "-")
    else:
        st.caption("완료된 기록 세션이 없습니다.")