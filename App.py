import streamlit as st
from googleapiclient.discovery import build
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone, date
import isodate
import pandas as pd

# --- 페이지 설정 ---
st.set_page_config(
    page_title="YouTube Insight DB Dashboard V6.4",
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

# --- [추가 핵심 로직] 유튜브 원본 API에서 직접 조회수 높은 20개 가져오는 백업 함수 ---
def fetch_top_20_live(api_key, query_keyword, region):
    if not query_keyword:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        # 조회수(viewCount) 순서로 20개 긴급 조회 쿼리셋 빌드
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

# --- 헬퍼 함수 ---
def get_published_after(option):
    if option == "전체": return None
    now = datetime.now(timezone.utc)
    if option == "최근 3일": delta = timedelta(days=3)
    elif option == "최근 1주일": delta = timedelta(days=7)
    elif option == "최근 1달": delta = timedelta(days=30)
    elif option == "최근 3개월": delta = timedelta(days=90)
    elif option == "최근 6개월": delta = timedelta(days=180)
    elif option == "최근 1년": delta = timedelta(days=365)
    elif option == "최근 2년": delta = timedelta(days=365 * 2)
    elif option == "최근 3년": delta = timedelta(days=365 * 3)
    
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
    st.caption("Streamlit v6.4 (백업 라이브 서치 기능 탑재)")
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
    
    col_v1, col_v2 = st.columns(2)
    with col_v1: min_view = st.number_input("최소 조회수", min_value=0, value=0, step=1000)
    with col_v2: max_view = st.number_input("최대 조회수 (0: 무제한)", min_value=0, value=0, step=10000)
    
    media_type = st.radio("⏱️ 영상 형태 필터링", ["전체", "숏폼", "롱폼"], horizontal=True)

    st.markdown("---")
    st.subheader("📥 새로운 데이터 수집")
    keyword = st.text_input("🔍 키워드 검색", placeholder="검색어 입력 (필수)")
    date_option = st.selectbox("📅 수집 기간 선택", ["최근 3일", "최근 1주일", "최근 1달", "최근 3개월", "최근 6개월", "최근 1년", "최근 2년", "최근 3년", "전체"], index=5)
    
    region_dict = {"🌐 전체 국가": "", "🇰🇷 한국 (KR)": "KR", "🇺🇸 미국 (US)": "US", "🇯🇵 일본 (JP)": "JP"}
    region_label = st.selectbox("🌍 대상 국가 타겟", list(region_dict.keys()), index=1)
    region_code = region_dict[region_label]

    st.markdown(" ")
    search_triggered = st.button("🚀 신규 데이터 수집 및 DB 저장", use_container_width=True)


# --- API 통신 및 데이터 스크래핑/적재 파트 ---
if search_triggered:
    if not keyword:
        st.error("⚠️ 검색 키워드를 입력해 주세요.")
    else:
        with st.spinner("유튜브 데이터를 분석하여 구글 시트 DB에 기록 중입니다..."):
            try:
                youtube = build("youtube", "v3", developerKey=api_key)
                published_after = get_published_after(date_option)
                
                search_kwargs = {"part": "snippet", "q": keyword, "type": "video", "maxResults": 50}
                if region_code: search_kwargs["regionCode"] = region_code
                if published_after: search_kwargs["publishedAfter"] = published_after
                
                search_res = youtube.search().list(**search_kwargs).execute()
                video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
                
                if video_ids:
                    video_res = youtube.videos().list(part="statistics,snippet,contentDetails", id=",".join(video_ids)).execute()
                    channel_ids = list(set([item["snippet"]["channelId"] for item in video_res.get("items", [])]))
                    channel_res = youtube.channels().list(part="statistics", id=",".join(channel_ids)).execute()
                    channel_map = {c["id"]: int(c["statistics"].get("subscriberCount", 1)) for c in channel_res.get("items", [])}
                    
                    fetched_list = []
                    for item in video_res.get("items", []):
                        views = int(item["statistics"].get("viewCount", 0))
                        subs = channel_map.get(item["snippet"]["channelId"], 1) or 1
                        iso_duration = item["contentDetails"].get("duration", "PT0S")
                        duration_sec = int(isodate.parse_duration(iso_duration).total_seconds())
                        
                        fetched_list.append({
                            "id": item["id"], "title": item["snippet"]["title"], "channelTitle": item["snippet"]["channelTitle"],
                            "publishedAt": item["snippet"]["publishedAt"], "thumb": item["snippet"]["thumbnails"]["high"]["url"],
                            "viewCount": views, "subCount": subs, "duration": duration_sec, "viralScore": (views / subs) * 100
                        })
                    
                    save_to_gsheet(fetched_list)
                    st.session_state.raw_data = load_from_gsheet()
                else:
                    st.warning("일치하는 유튜브 검색 결과가 존재하지 않습니다.")
            except Exception as e:
                st.error(f"오류가 발생하였습니다: {e}")

# --- 메인 뷰 대시보드 데이터 연산 및 렌더링 파트 ---
st.title("📺 YouTube DB Insight Dashboard")

if st.button("🔄 구글 시트 DB 동기화/새로고침"):
    st.session_state.raw_data = load_from_gsheet()

filtered_data = st.session_state.raw_data
is_db_active = False

# DB에 정상 데이터가 적재되어 있을 때의 필터 제어식
if filtered_data and isinstance(filtered_data, list) and "publishedAt" in filtered_data[0]:
    df = pd.DataFrame(filtered_data)
    
    df['pub_date'] = pd.to_datetime(df['publishedAt']).dt.date
    df = df[(df['pub_date'] >= start_date) & (df['pub_date'] <= end_date)]
    
    df = df[df['viewCount'] >= min_view]
    if max_view > 0:
        df = df[df['viewCount'] <= max_view]
        
    if media_type == "숏폼":
        df = df[df['duration'] < 60]
    elif media_type == "롱폼":
        df = df[df['duration'] >= 60]

    if not df.empty:
        is_db_active = True
        col_count, col_sort = st.columns([2, 3])
        with col_sort:
            sort_by = st.radio("정렬 필터", ["조회수 순", "🔥 떡상 성과순", "최신순"], horizontal=True)
            
        if sort_by == "조회수 순":
            df = df.sort_values(by="viewCount", ascending=False)
        elif "떡상" in sort_by:
            df = df.sort_values(by="viralScore", ascending=False)
        elif sort_by == "최신순":
            df = df.sort_values(by="publishedAt", ascending=False)

        with col_count:
            st.subheader(f"🔍 DB 매칭 결과: {len(df)}개")

        # 4열 그리드 출력
        cols = st.columns(4)
        for idx, row in enumerate(df.to_dict(orient="records")):
            col = cols[idx % 4]
            with col:
                with st.container(border=True):
                    st.image(row["thumb"], use_container_width=True)
                    st.caption(f"📅 업로드: {row['pub_date']} | ⏱️ {format_duration(row['duration'])}")
                    st.markdown(f"**[{row['title']}](https://youtube.com/watch?v={row['id']})**")
                    st.caption(f"👤 {row['channelTitle']}")
                    
                    multiplier = float(row['viralScore']) / 100
                    if row['viralScore'] >= 500:
                        st.error(f"🔥 떡상급 성과 (x{multiplier:.1f})")
                    else:
                        st.info(f"📈 성과지수 (x{multiplier:.1f})")
                    
                    stat_col1, stat_col2 = st.columns(2)
                    with stat_col1: st.metric(label="조회수", value=format_num(row['viewCount']))
                    with stat_col2: st.metric(label="구독자", value=format_num(row['subCount']))

# --- [핵심 기능] DB가 비어있거나 조건 일치 항목이 0개일 때 발동하는 백업 서치 인터페이스 ---
if not is_db_active:
    if keyword:
        st.warning(f"💡 현재 구글 시트 DB에 데이터가 없거나 조건에 맞는 영상이 없습니다. 유튜브에서 '{keyword}'의 최다 조회수 영상 20개를 실시간으로 가져옵니다.")
        
        with st.spinner("유튜브 랭킹 데이터 로딩 중..."):
            live_top_20 = fetch_top_20_live(api_key, keyword, region_code)
            
        if live_top_20:
            st.subheader(f"🔥 유튜브 실시간 조회수 TOP {len(live_top_20)} 랭킹 리스트")
            cols = st.columns(4)
            for idx, item in enumerate(live_top_20):
                col = cols[idx % 4]
                with col:
                    with st.container(border=True):
                        st.image(item["thumb"], use_container_width=True)
                        st.caption(f"⏱️ 영상 길이: {format_duration(item['duration'])}")
                        st.markdown(f"**[{item['title']}](https://youtube.com/watch?v={item['id']})**")
                        st.caption(f"👤 {item['channelTitle']}")
                        
                        multiplier = item['viralScore'] / 100
                        if item['viralScore'] >= 500:
                            st.error(f"🔥 떡상 성과 (x{multiplier:.1f})")
                        else:
                            st.info(f"📈 성과지수 (x{multiplier:.1f})")
                        
                        stat_col1, stat_col2 = st.columns(2)
                        with stat_col1: st.metric(label="조회수", value=format_num(item['viewCount']))
                        with stat_col2: st.metric(label="구독자", value=format_num(item['subCount']))
        else:
            st.info("검색된 실시간 영상이 없습니다. 키워드를 올바르게 입력해 주세요.")
    else:
        st.info("📥 대시보드 활성화를 위해 왼쪽 사이드바 하단 '새로운 데이터 수집' 란에 키워드를 입력하고 검색을 시도해 주세요.")
