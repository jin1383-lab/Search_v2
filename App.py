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
    df = df.drop_duplicates(subset=
