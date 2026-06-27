import streamlit as st
from googleapiclient.discovery import build
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone, date
import isodate
import pandas as pd

# --- 페이지 설정 ---
st.set_page_config(
    page_title="YouTube Insight DB Dashboard V6.6",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 구글 시트(DB) 연결 함수 ---
def get_gsheet_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(st.secrets["gserviceaccount"], scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"구글 시트 인증 실패: {e}")
        return None

# --- 구글 시트에 데이터 누적 저장하는 함수 ---
def save_to_gsheet(data_list):
    client = get_gsheet_client()
    if not client: return
    
    try:
        sheet_key = st.secrets["SPREADSHEET_KEY"]
        spreadsheet = client.open_by_key(sheet_key)
        worksheet = spreadsheet.get_worksheet(0)
    except Exception as e:
        st.error(f"구글 시트를 열 수 없습니다. 키(ID) 설정을 확인하세요: {e}")
        return

    existing_records = worksheet.get_all_records()
    existing_ids = {r["id"] for r in existing_records} if existing_records else set()
    
    if not existing_records and len(worksheet.get_all_values()) == 0:
        headers = ["id", "title", "channelTitle", "publishedAt", "thumb", "viewCount", "subCount", "duration", "viralScore", "collectedAt"]
        worksheet.append_row(headers)

    new_rows = []
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    for item in data_list:
        if item["id"] not in existing_ids:
            new_rows.append([
                item["id"], item["title"], item["channelTitle"], item["publishedAt"],
                item["thumb"], item["viewCount"], item["subCount"], item["duration"],
                item["viralScore"], collected_at
            ])
            
    if new_rows:
        worksheet.append_rows(new_rows)
        st.success(f"📊 신규 데이터 {len(new_rows)}건이 구글 시트 DB에 저장되었습니다!")
    else:
        st.info("🔄 최신 데이터가 이미 DB에 모두 동기화되어 있습니다. (중복 없음)")

# --- 구글 시트에서 전체 DB 불러오는 함수 ---
def load_from_gsheet():
    client = get_gsheet_client()
    if not client: return []
    try:
        sheet_key = st.secrets["SPREADSHEET_KEY"]
        worksheet = client.open_by_key(sheet_key).get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        return []

# --- 유튜브 원본 API에서 직접 조회수 높은 20개 가져오는 백업 함수 ---
def fetch_top_20_live(api_key, query_keyword, region):
    if not query_keyword:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        search_kwargs = {
            "part": "snippet",
            "q": query_keyword,
            "type": "video",
            "order": "viewCount",
            "maxResults": 20
        }
        if region: search_kwargs["regionCode"] = region
        
        search_res = youtube.search().list(**search_kwargs).execute()
        video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
        
        if not video_ids: return []
        
        video_res = youtube.videos().list(part="statistics,snippet,contentDetails", id=",".join(video_ids)).execute()
        channel_ids = list(set([item["snippet"]["channelId"] for item in video_res.get("items", [])]))
        channel_res = youtube.channels().list(part="statistics", id=",".join(channel_ids)).execute()
        channel_map = {c["id"]: int(c["statistics"].get("subscriberCount", 1)) for c in channel_res.get("items", [])}
        
        backup_list = []
        for item in video_res.get("items", []):
            views = int(item["statistics"].get("viewCount", 0))
            subs = channel_map.get(item["snippet"]["channelId"], 1) or 1
            iso_duration = item["contentDetails"].get("duration", "PT0S")
            duration_sec = int(isodate.parse_duration(iso_duration).total_seconds())
            
            backup_list.append({
                "id": item["id"], "title": item["snippet"]["title"], "channelTitle": item["snippet"]["channelTitle"],
                "publishedAt": item["snippet"]["publishedAt"], "thumb": item["snippet"]["thumbnails"]["high"]["url"],
                "viewCount": views, "subCount": subs, "duration": duration_sec, "viralScore": (views / subs) * 100
            })
        return backup_list
    except Exception as e:
        st.error(f"실시간 랭킹 백업 로딩 중 오류 발생: {e}")
        return []

# --- [요구사항 반영] 고정된 수집 기간에 맞춘 날짜 계산 함수 ---
def get_published_after(option):
    now = datetime.now(timezone.utc)
    if option == "1일": delta = timedelta(days=1)
    elif option == "3일": delta = timedelta(days=3)
    elif option == "15일": delta = timedelta(days=15)
    elif option == "1달": delta = timedelta(days=30)
    elif option == "3개월": delta = timedelta(days=90)
    elif option == "6개월": delta = timedelta(days=180)
    elif option == "1년": delta = timedelta(days=365)
    elif option == "2년": delta = timedelta(days=365 * 2)
    elif option == "3년": delta = timedelta(days=365 * 3)
    elif option == "4년": delta = timedelta(days=365 * 4)
    elif option == "5년": delta = timedelta(days=365 * 5)
    else: return None
    
    target_time = now - delta
    return target_time.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

def format_duration(seconds):
    m, s = divmod(seconds, 60)
    return f"{m}분 {s}초" if m > 0 else f"{s}초"

def format_num(n):
    n = int(n)
    if n >= 100000000: return f"{n / 100000000:.1f}억"
    if n >= 10000: return f"{n / 10000:.1f}만"
    return f"{n:,}"


# --- [세션 제어] 초기 앱 기동 시 DB 로드 ---
if "raw_data" not in st.session_state or not st.session_state.raw_data:
    st.session_state.raw_data = load_from_gsheet()


# --- 사이드바 제어 패널 UI ---
with st.sidebar:
    st.title("🚀 Insight DB Dash")
    st.caption("Streamlit v6.6 (기간 옵션 변경)")
    st.markdown("---")
    
    api_key = st.secrets.get("YOUTUBE_API_KEY", "")
    if api_key and "gserviceaccount" in st.secrets:
        st.success("✅ YouTube API & GSheet DB 연동 성공")
    else:
        st.error("⚠️ Secrets 환경 변수 세팅을 체크해 주세요.")
        
    st.markdown("---")
    st.subheader("📊 DB 실시간 정밀 필터")
    
    today = date.today()
    start_date = st.date_input("📅 업로드 시작일", today - timedelta(days=365))
    end_date = st.date_input("📅 업로드 종료일", today)
    
    min_view = st.number_input("📉 최소 조회수 (0: 제한없음)", min_value=0, value=0, step=1000)
    min_sub = st.number_input("👤 최소 구독자수 (0: 제한없음)", min_value=0, value=0, step=1000)
    max_view = st.number_input("📈 최대 조회수 (0: 무제한)", min_value=0, value=0, step=10000)
    
    media_type = st.radio("⏱️ 영상 형태 필터링", ["전체", "숏폼", "롱폼"], horizontal=True)

    st.markdown("---")
    st.subheader("📥 새로운 데이터 수집")
    keyword = st.text_input("🔍 키워드 검색", placeholder="검색어 입력 (필수)")
    
    # [요구사항 반영] 유저
