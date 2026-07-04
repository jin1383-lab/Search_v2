import streamlit as st
import requests
from datetime import datetime, timedelta
import html

# -----------------------------------------------------------------------------
# [1] 페이지 기본 설정 및 YouTube 다크 테마 CSS 주입
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="YouTube 트렌드 탐색기",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 기존 HTML/CSS 디자인 특성을 Streamlit에 그대로 반영
st.markdown("""
    <style>
    /* 배경 및 기본 폰트 색상 제어 (Streamlit 기본 기본값 오버라이드) */
    [data-testid="stAppViewContainer"] {
        background-color: #0f0f0f;
        color: #f1f1f1;
    }
    header, [data-testid="stHeader"] {
        background-color: #181818 !important;
    }
    
    /* 타이틀 및 UI 요소 스타일 */
    .main-title { color: #ff0000; font-size: 24px; font-weight: bold; margin-bottom: 5px; }
    .status-text { font-size: 12px; color: #aaa; margin-bottom: 15px; }
    
    /* 비디오 카드 레이아웃 (Grid & Flex) */
    .video-card {
        display: flex;
        align-items: center;
        background: #181818;
        border: 1px solid #272727;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        gap: 16px;
    }
    .video-rank {
        font-size: 22px;
        font-weight: bold;
        color: #ff0000;
        min-width: 40px;
        text-align: center;
    }
    .video-thumb {
        width: 168px;
        height: 94px;
        object-fit: cover;
        border-radius: 6px;
        background: #000;
    }
    .video-meta {
        flex: 1;
    }
    .video-title {
        color: #f1f1f1;
        text-decoration: none;
        font-size: 15px;
        font-weight: bold;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin-bottom: 4px;
    }
    .video-title:hover { color: #ffffff; }
    .video-channel { color: #aaa; font-size: 13px; margin-bottom: 4px; text-decoration: none;}
    .video-channel:hover { color: #fff; }
    .video-stats { color: #777; font-size: 12px; }
    
    /* 컴포넌트 간격 조정 */
    div[data-testid="stBlock"] { gap: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# [2] 헬퍼 함수 (유틸리티)
# -----------------------------------------------------------------------------
def fmt_number(n):
    """숫자를 만, 억 단위 한글로 포맷팅"""
    try:
        n = int(n)
        if n >= 1e8: return f"{n/1e8:.1f}억"
        if n >= 1e4: return f"{n/1e4:.1f}만"
        return f"{n:,}"
    except:
        return "0"

def time_ago(iso_str):
    """ISO 8601 날짜를 몇 시간 전, 몇 일 전 형식으로 변환"""
    try:
        pub_time = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.utcnow()
        diff = now - pub_time
        
        seconds = diff.total_seconds()
        if seconds < 60: return f"{int(seconds)}초 전"
        minutes = seconds / 60
        if minutes < 60: return f"{int(minutes)}분 전"
        hours = minutes / 60
        if hours < 24: return f"{int(hours)}시간 전"
        days = hours / 24
        if days < 30: return f"{int(days)}일 전"
        months = days / 30
        if months < 12: return f"{int(months)}개월 전"
        return f"{int(months/12)}년 전"
    except:
        return ""

def yt_fetch(endpoint, params):
    """YouTube API 요청 전송 및 공통 에러 핸들링"""
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}"
    
    # [TOML 방식 적용] st.secrets 구조에서 API 키 로딩 우선순위 체크
    if "youtube" in st.secrets and "api_key" in st.secrets["youtube"]:
        params["key"] = st.secrets["youtube"]["api_key"]
    elif "api_key" in st.secrets:
        params["key"] = st.secrets["api_key"]
    elif "api_key" in st.session_state and st.session_state["api_key"]:
        params["key"] = st.session_state["api_key"]
    else:
        raise Exception("API 키가 설정되지 않았습니다. .streamlit/secrets.toml 파일을 확인하거나 입력해 주세요.")
        
    res = requests.get(url, params=params)
    data = res.json()
    if res.status_code != 200:
        error_msg = data.get("error", {}).get("message", f"API 오류: {res.status_code}")
        raise Exception(error_msg)
    return data

# -----------------------------------------------------------------------------
# [3] 상태 관리 및 TOML 검증 유효성 체크
# -----------------------------------------------------------------------------
st.markdown('<div class="main-title">▶ YouTube 트렌드 탐색기</div>', unsafe_allow_html=True)

# TOML 파일 세팅 여부 확인
has_toml_key = False
toml_key = ""
if "youtube" in st.secrets and "api_key" in st.secrets["youtube"]:
    toml_key = st.secrets["youtube"]["api_key"]
    has_toml_key = True
elif "api_key" in st.secrets:
    toml_key = st.secrets["api_key"]
    has_toml_key = True

if "api_key" not in st.session_state:
    st.session_state["api_key"] = toml_key if has_toml_key else ""

# TOML 인증키 주입 결과 피드백 가이드라인 구성
if has_toml_key:
    st.markdown('<div class="status-text">✅ <b>secrets.toml (TOML 방식)</b> 인증을 통해 API 키를 자동으로 관리 중입니다.</div>', unsafe_allow_html=True)
else:
    # TOML이 설정되지 않은 비상 케이스용 수동 입력창 컴포넌트 출력 유지
    col_input, col_save, col_del = st.columns([5, 1, 1])
    with col_input:
        api_input = st.text_input(
            "YouTube Data API v3 키를 입력하세요", 
            type="password", 
            value=st.session_state["api_key"], 
            label_visibility="collapsed", 
            placeholder="YouTube Data API v3 키를 입력하세요 (또는 .streamlit/secrets.toml에 등록)"
        )
    with col_save:
        if st.button("저장 / 사용", use_container_width=True, type="primary"):
            if api_input.strip():
                st.session_state["api_key"] = api_input.strip()
                st.rerun()
    with col_del:
        if st.button("삭제", use_container_width=True):
            st.session_state["api_key"] = ""
            st.rerun()
            
    if st.session_state["api_key"]:
        st.markdown('<div class="status-text">⚠️ 임시 수동 입력창을 기반으로 작동 중입니다. (.streamlit/secrets.toml 파일 사용을 적극 권장합니다)</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-text">❌ 키가 저장되어 있지 않습니다. .streamlit/secrets.toml 파일을 등록하시거나 임시 키를 상단에 기입해 주세요.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# [4] 메인 탭 구성 (Trending / Search)
# -----------------------------------------------------------------------------
tab_trending, tab_search = st.tabs(["🔥 인기 급상승 TOP 50", "🔍 키워드 트렌드"])

# --- [Tab 1] 인기 급상승 페이지 ---
with tab_trending:
    c1, c2, c3 = st.columns([2, 3, 1])
    with c1:
        region_dict = {"대한민국": "KR", "미국": "US", "일본": "JP", "영국": "GB", "독일": "DE", "프랑스": "FR", "인도": "IN", "브라질": "BR"}
        region_sel = st.selectbox("지역 선택", list(region_dict.keys()), index=0, label_visibility="collapsed")
        region_code = region_dict[region_sel]
    with c2:
        categories = [("0", "전체 카테고리")]
        if has_toml_key or st.session_state["api_key"]:
            try:
                cat_data = yt_fetch("videoCategories", {"part": "snippet", "regionCode": region_code})
                for item in cat_data.get("items", []):
                    if item["snippet"]["assignable"]:
                        categories.append((item["id"], item["snippet"]["title"]))
            except:
                pass
        cat_sel = st.selectbox("카테고리 선택", [c[1] for c in categories], index=0, label_visibility="collapsed")
        cat_id = [c[0] for c in categories if c[1] == cat_sel][0]
    with c3:
        load_trending = st.button("불러오기", key="btn_trend", type="primary", use_container_width=True)

    if load_trending:
        with st.spinner("불러오는 중..."):
            try:
                params = {
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": region_code,
                    "maxResults": 50
                }
                if cat_id != "0":
                    params["videoCategoryId"] = cat_id
                
                data = yt_fetch("videos", params)
                items = data.get("items", [])
                
                if not items:
                    st.info("결과가 없습니다.")
                
                for idx, item in enumerate(items):
                    v_id = item["id"]
                    sn = item.get("snippet", {})
                    st_dict = item.get("statistics", {})
                    
                    title = html.escape(sn.get("title", ""))
                    channel = html.escape(sn.get("channelTitle", ""))
                    thumb = sn.get("thumbnails", {}).get("medium", {}).get("url", "")
                    views = fmt_number(st_dict.get("viewCount", 0))
                    time_str = time_ago(sn.get("publishedAt", ""))
                    
                    v_url = f"https://www.youtube.com/watch?v={v_id}"
                    ch_url = f"https://www.youtube.com/channel/{sn.get('channelId', '')}"
                    
                    card_html = f"""
                    <div class="video-card">
                        <div class="video-rank">{idx + 1}</div>
                        <a href="{v_url}" target="_blank"><img class="video-thumb" src="{thumb}"></a>
                        <div class="video-meta">
                            <a class="video-title" href="{v_url}" target="_blank">{title}</a>
                            <div style="margin-top:2px;"><a class="video-channel" href="{ch_url}" target="_blank">{channel}</a></div>
                            <div class="video-stats">조회수 {views}회 · {time_str}</div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")

# --- [Tab 2] 키워드 트렌드 페이지 ---
with tab_search:
    s1, s2, s3, s4 = st.columns([3, 1, 1, 1])
    with s1:
        search_q = st.text_input("키워드 입력", placeholder="키워드를 입력하세요 (예: AI, 요리, 게임)", label_visibility="collapsed")
    with s2:
        order_dict = {"조회수": "viewCount", "관련성": "relevance", "최신순": "date", "평점순": "rating"}
        order_sel = st.selectbox("정렬 기준", list(order_dict.keys()), index=0, label_visibility="collapsed")
        order_code = order_dict[order_sel]
    with s3:
        period_dict = {"전체 기간": "", "최근 1일": "1", "최근 7일": "7", "최근 30일": "30", "최근 90일": "90"}
        period_sel = st.selectbox("기간 설정", list(period_dict.keys()), index=2, label_visibility="collapsed")
        period_days = period_dict[period_sel]
    with s4:
        search_btn = st.button("검색", key="btn_search", type="primary", use_container_width=True)

    if search_btn:
        if not search_q.strip():
            st.warning("키워드를 입력하세요.")
        else:
            with st.spinner("검색 중..."):
                try:
                    search_params = {
                        "part": "snippet",
                        "type": "video",
                        "q": search_q.strip(),
                        "order": order_code,
                        "maxResults": 50,
                        "regionCode": "KR"
                    }
                    if period_days:
                        target_date = datetime.utcnow() - timedelta(days=int(period_days))
                        search_params["publishedAfter"] = target_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                    s_data = yt_fetch("search", search_params)
                    v_ids = [item["id"]["videoId"] for item in s_data.get("items", []) if "videoId" in item["id"]]
                    
                    if not v_ids:
                        st.info("결과가 없습니다.")
                    else:
                        details = yt_fetch("videos", {
                            "part": "snippet,statistics",
                            "id": ",".join(v_ids),
                            "maxResults": 50
                        })
                        items = details.get("items", [])
                        
                        if order_code == "viewCount":
                            items.sort(key=lambda x: int(x.get("statistics", {}).get("viewCount", 0)), reverse=True)
                            
                        for idx, item in enumerate(items):
                            v_id = item["id"]
                            sn = item.get("snippet", {})
                            st_dict = item.get("statistics", {})
                            
                            title = html.escape(sn.get("title", ""))
                            channel = html.escape(sn.get("channelTitle", ""))
                            thumb = sn.get("thumbnails", {}).get("medium", {}).get("url", "")
                            views = fmt_number(st_dict.get("viewCount", 0))
                            time_str = time_ago(sn.get("publishedAt", ""))
                            
                            v_url = f"https://www.youtube.com/watch?v={v_id}"
                            ch_url = f"https://www.youtube.com/channel/{sn.get('channelId', '')}"
                            
                            card_html = f"""
                            <div class="video-card">
                                <div class="video-rank">{idx + 1}</div>
                                <a href="{v_url}" target="_blank"><img class="video-thumb" src="{thumb}"></a>
                                <div class="video-meta">
                                    <a class="video-title" href="{v_url}" target="_blank">{title}</a>
                                    <div style="margin-top:2px;"><a class="video-channel" href="{ch_url}" target="_blank">{channel}</a></div>
                                    <div class="video-stats">조회수 {views}회 · {time_str}</div>
                                </div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {str(e)}")
