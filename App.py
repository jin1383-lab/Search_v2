import streamlit as st
import pandas as pd
import requests
import isodate
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

st.set_page_config(page_title="Pixeling Master DB v2", page_icon="🌙", layout="wide")

st.markdown("""<style>
    .stApp { background-color: #0B0F19 !important; color: #E5E7EB; }
    .brand-title { font-size: 24pt; font-weight: 800; background: linear-gradient(135deg, #FF0055, #4FACFE); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .url-wrapper { background: #161D30; border-radius: 8px; padding: 10px; border: 1px solid #24314D; color: #34D399; font-family: monospace; font-size: 9pt; margin-bottom: 15px; }
    .mvp-hero-card { background: linear-gradient(135deg, #1A1225, #131B2E); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #FF3366; }
    .grid-card { background: #131B2E; border-radius: 10px; border: 1px solid #212B41; padding: 15px; margin-bottom: 20px; height: auto; }
    .metric-box { background: #1A2338; border-radius: 6px; padding: 8px; margin-top: 5px; border: 1px solid #24314D; font-size: 9pt; }
    .thumb-link img { transition: transform 0.2s ease, opacity 0.2s ease; }
    .thumb-link img:hover { transform: scale(1.02); opacity: 0.85; cursor: pointer; }
</style>""", unsafe_allow_html=True)

st.markdown('<div class="brand-title">Pixeling Cloud Sheets DB v2 👑</div><div style="color:#9CA3AF;font-size:9pt;">YouTube Category Multi-Scaler & Tracking Engine</div><br>', unsafe_allow_html=True)

# 🔐 API 자격 증명 로드룸 (구글 시트 API 할당량 초과 방지 캐싱 세션 적용)
@st.cache_resource(ttl=3600)
def get_google_worksheet(spreadsheet_key, sa_info):
    gcp_info = {
        "type": sa_info["type"], "project_id": sa_info["project_id"], "private_key_id": sa_info["private_key_id"],
        "private_key": sa_info["private_key"].replace('\\n', '\n'), "client_email": sa_info["client_email"],
        "client_id": sa_info["client_id"], "auth_uri": sa_info["auth_uri"], "token_uri": sa_info["token_uri"],
        "auth_provider_x509_cert_url": sa_info["auth_provider_x509_cert_url"], "client_x509_cert_url": sa_info["client_x509_cert_url"]
    }
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(gcp_info, scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_key)
    return sh.get_worksheet(0)

try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
    SPREADSHEET_KEY = st.secrets["SPREADSHEET_KEY"]
    
    # 캐시 래핑 처리된 시트 로드
    worksheet = get_google_worksheet(SPREADSHEET_KEY, st.secrets["gcp_service_account"])
except Exception as e:
    st.error(f"🚨 자격 증명 파싱 실패. 에러 파트: {e}")
    st.stop()

# 🗄️ 구글 시트 백업 엔진
def save_data_to_google_sheet(df, period_txt, category_txt):
    try:
        current_log_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if len(worksheet.get_all_values()) == 0:
            worksheet.append_row(["Log_Time", "Target_Category", "Target_Period", "Video_URL", "Channel_Name", "Handle", "Format", "Likes", "Comments", "Calculated_Score", "Estimated_Revenue"])
        
        rows_to_append = []
        for _, row in df.iterrows():
            rows_to_append.append([
                current_log_time, category_txt, period_txt, row["video_url"], row["name"], row["handle"], 
                row["type"], row["likes"], row["comments"], row["score"], row["rev"]
            ])
        worksheet.append_rows(rows_to_append)
        return True
    except Exception as e:
        st.sidebar.error(f"시트 백업 실패: {e}")
        return False

@st.cache_data(ttl=600)
def fetch_engagement_trending_data(days, cc, fmt, cat_id):
    url = "https://www.googleapis.com/youtube/v3/videos"
    data = []
    next_page_token = None
    max_loops = 5 if fmt == "숏폼 전용" else 3
    now = datetime.now(timezone.utc)
    
    for _ in range(max_loops):
        p = {"part": "id,snippet,contentDetails,statistics", "chart": "mostPopular", "regionCode": cc, "maxResults": 50, "key": API_KEY}
        if cat_id: p["videoCategoryId"] = cat_id
        if next_page_token: p["pageToken"] = next_page_token
            
        try: res = requests.get(url, params=p).json()
        except: break
        if "error" in res or "items" not in res: break

        for item in res["items"]:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            v_id = item.get("id")
            
            try: secs = isodate.parse_duration(item["contentDetails"].get("duration", "PT0S")).total_seconds()
            except: secs = 0
            m_type = "Shorts" if secs <= 60 else "Long-form"
            if (fmt == "롱폼 전용" and m_type != "Long-form") or (fmt == "숏폼 전용" and m_type != "Shorts"): continue
            
            published_at_str = snippet.get("publishedAt")
            try:
                published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                elapsed_days = (now - published_at).days + (now - published_at).seconds / 86400.0
                if elapsed_days < 0.1: elapsed_days = 0.1
            except:
                elapsed_days = 1.0
            
            raw_likes = int(stats.get("likeCount", 0))
            raw_comments = int(stats.get("commentCount", 0))
            raw_views = int(stats.get("viewCount", 0))
            
            calc_likes = int((raw_likes / elapsed_days) * days)
            calc_comments = int((raw_comments / elapsed_days) * days)
            calc_views = int((raw_views / elapsed_days) * days)
            engagement_score = calc_likes + (calc_comments * 2) 
            
            if m_type == "Shorts": rpm = 110 if cc == "KR" else 150 if cc == "US" else 120
            else: rpm = 4500 if cc == "KR" else 9000 if cc == "US" else 5500
                
            estimated_revenue = int((calc_views / 1000) * rpm)
            currency_symbol = "₩" if cc == "KR" else "$" if cc == "US" else "¥"
            
            data.append({
                "video_url": f"https://youtu.be/{v_id}",
                "name": snippet.get("channelTitle", "익명"),
                "handle": f"@{snippet.get('channelId')[:12]}",
                "type": m_type, "likes": calc_likes, "comments": calc_comments,
                "score": engagement_score, "rev": estimated_revenue, "symbol": currency_symbol,
                "img": snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            })
            
        next_page_token = res.get("nextPageToken")
        if not next_page_token: break

    df = pd.DataFrame(data)
    if df.empty: return df
    
    # 🎯 괄호 오류 완벽 수정 완료 파트
    df = df.drop_duplicates(subset=["handle"]).sort_values(by="score", ascending=False).reset_index(drop=True)
    return df.head(20)

# 🛠️ 사이드바 컨트롤 매트릭스 패널 (모바일 최적화 레이아웃)
st.sidebar.markdown("### 🗄️ DATABASE CONTROL")
db_view = st.sidebar.checkbox("📂 구글 시트 백업 DB 조회하기")

st.sidebar.markdown("### 📌 FILTER CONFIG")
CATEGORY_MAP = {
    "전체 (All)": None, "영화 & 애니메이션": "1", "자동차 & 탈것": "2", "음악": "10", 
    "반려동물 & 동물": "15", "스포츠": "17", "여행 & 이벤트": "19", "게임": "20", 
    "인물 & 블로그": "22", "코미디": "23", "엔터테인먼트": "24", "뉴스 & 정치": "25", 
    "노하우 & 스타일": "26", "교육": "27", "과학 & 기술": "28"
}

# 🎯 자판 차단 치트키: 무조건 터치 기반 전용 radio 형태로 감싸서 로드
with st.sidebar.expander("📺 카테고리 선택 (터치 전용)", expanded=False):
    selected_cat_label = st.radio(
        "CATEGORY_SELECTION",
        options=list(CATEGORY_MAP.keys()),
        label_visibility="collapsed"
    )
target_cat_id = CATEGORY_MAP[selected_cat_label]

# 가로 배치 버튼형 미디어 포맷 필터
media_filter = st.sidebar.radio("FORMAT", ["전체 통합", "롱폼 전용", "숏폼 전용"], horizontal=True)

# 1일에서 최대 5년(1825일) 롱레인지 슬라이더 타임라인 스케일러
period_label = st.sidebar.select_slider(
    "PERIOD SCALE", 
    options=["1D", "7D", "30D", "90D", "180D", "1 Year", "3 Years", "5 Years"]
)
day_mapping = {"1D": 1, "7D": 7, "30D": 30, "90D": 90, "180D": 180, "1 Year": 365, "3 Years": 1095, "5 Years": 1825}
days_param = day_mapping[period_label]

nations = ["South Korea (KR)", "United States (US)", "Japan (JP)"]
selected_nation = st.sidebar.radio("NATION", nations, horizontal=True) # 국가 탭도 키보드 방지를 위해 라디오로 교체
country_code = "US" if "US" in selected_nation else "JP" if "JP" in selected_nation else "KR"

st.sidebar.markdown("<br>", unsafe_allow_html=True)
run_engine = st.sidebar.button("RUN & SYNC CLOUD SHEET", type="primary", use_container_width=True)

if db_view:
    st.markdown("### 🗄️ Google Sheets DB Cumulative History")
    try:
        sheet_data = worksheet.get_all_records()
        if sheet_data:
            db_df = pd.DataFrame(sheet_data)
            st.dataframe(db_df.tail(100), use_container_width=True)
            st.info(f"💡 현재 구글 시트에 총 {len(db_df)}개의 누적 트렌드 시계열 로그가 보관 중입니다.")
        else:
            st.warning("시트에 데이터 로그가 존재하지 않습니다.")
    except Exception as e:
        st.error(f"구글 시트 로드 에러: {e}")

if run_engine:
    with st.spinner(f"⚡ {country_code} ({selected_cat_label}) - {period_label} 타겟 환산 연산 중..."): 
        df = fetch_engagement_trending_data(days_param, country_code, media_filter, target_cat_id)
        
    if not df.empty:
        sheet_sync_success = save_data_to_google_sheet(df, period_label, selected_cat_label)
        if sheet_sync_success:
            st.markdown(f'<div class="url-wrapper">✅ CLOUD SHEET SYNC SUCCESS | 카테고리 [{selected_cat_label}] 기준 {period_label} 데이터가 실시간 누적되었습니다.</div>', unsafe_allow_html=True)
        
        m = df.iloc[0]
        c = "color:#F87171;" if m['type'] == "Shorts" else "color:#60A5FA;"
        st.markdown(f"""<div class="mvp-hero-card"><div style="display:flex;justify-content:space-between;font-size:9pt;font-weight:600;"><span style="color:#FF0055;">🔥 {period_label} {selected_cat_label} NO.1</span><span style="{c}">{m['type']}</span></div><div style="display:flex;align-items:center;gap:15px;margin-top:10px;"><a href="{m['video_url']}" target="_blank" class="thumb-link"><img src="{m['img']}" style="width:100px;height:70px;border-radius:6px;object-fit:cover;"></a><div style="flex-grow:1;"><div style="font-size:14pt;font-weight:800;color:#FFF;">{m['name']}</div><div style="color:#9CA3AF;font-size:9pt;">{m['handle']}</div></div><div><div class="metric-box"><span style="color:#F87171;">❤️ 환산 좋아요:</span> <b>{m['likes']:,}개</b></div><div class="metric-box"><span style="color:#38BDF8;">💬 환산 댓글수:</span> <b>{m['comments']:,}개</b></div></div></div></div>""", unsafe_allow_html=True)
        
        st.markdown(f"<h5 style='font-weight:700;color:#E5E7EB;margin-bottom:15px;'>👥 TOP 2 - 20 REACTION LEADERS</h5>", unsafe_allow_html=True)
        g_data = df.iloc[1:].reset_index(drop=True)
        total_rows = (len(g_data) + 2) // 3
        grid_rows = [st.columns(3) for _ in range(total_rows)]
        
        for idx in range(len(g_data)):
            row_pos = idx // 3
            col_pos = idx % 3
            item = g_data.iloc[idx]
            tc = "color:#F87171;" if item['type'] == "Shorts" else "color:#60A5FA;"
            
            with grid_rows[row_pos][col_pos]:
                st.markdown(f"""<div class="grid-card">
                    <div>
                        <div style="display:flex;justify-content:space-between;font-size:8pt;"><b>TOP {idx+2}</b><span style="{tc}">{item['type']}</span></div>
                        <a href="{item['video_url']}" target="_blank" class="thumb-link">
                            <img src="{item['img']}" style="width:100%;height:120px;border-radius:6px;object-fit:cover;margin:8px 0;border:1px solid #24314D;">
                        </a>
                        <div style="font-size:10.5pt;font-weight:700;color:#FFF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{item['name']}</div>
                        <div style="color:#9CA3AF;font-size:8.5pt;margin-bottom:8px;">{item['handle']}</div>
                    </div>
                    <div>
                        <div class="metric-box"><span style="color:#F87171;">❤️ 좋아요:</span> <b>{item['likes']:,}</b></div>
                        <div class="metric-box"><span style="color:#38BDF8;">💬 댓글수:</span> <b>{item['comments']:,}</b></div>
                    </div>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("조건에 맞는 트렌딩 연산 데이터를 확보하지 못했습니다.")
