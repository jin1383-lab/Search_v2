import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 1. Google Sheets 연결 함수 (에러가 발생했던 캐싱 구간)
# 매개변수 앞에 언더바(_)를 붙여 Streamlit이 AttrDict를 해싱하지 않도록 차단합니다.
@st.cache_resource
def get_google_worksheet(_sa_info, spreadsheet_key):
    # Secrets에서 가져온 딕셔너리 정보로 권한(Credentials) 생성
    creds = Credentials.from_service_account_info(
        _sa_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    # gspread 클라이언트 인증 및 스프레드시트 열기
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_key)
    # 첫 번째 워크시트 반환
    return sheet.get_worksheet(0)

# 2. YouTube API 호출 함수 (선택 사항: 캐싱 적용으로 속도 향상)
@st.cache_resource
def get_youtube_client(api_key):
    return build("youtube", "v3", developerKey=api_key)

def main():
    st.set_page_config(page_title="YouTube & Google Sheets Dashboard", layout="wide")
    st.title("📊 유튜브 데이터 및 구글 시트 대시보드")

    # Streamlit Secrets에서 설정값 안전하게 불러오기
    try:
        youtube_api_key = st.secrets["YOUTUBE_API_KEY"]
        spreadsheet_key = st.secrets["SPREADSHEET_KEY"]
        # 이전에 바꾼 [gcp_service_account] 키를 통째로 가져옵니다.
        sa_info = st.secrets["gcp_service_account"]
    except KeyError as e:
        st.error(f"Streamlit Cloud의 Secrets 설정에서 Key를 찾을 수 없습니다: {e}")
        st.info("Advanced settings -> Secrets에 값이 올바르게 입력되었는지 확인해 주세요.")
        return

    # 구글 시트 연결 실행
    try:
        worksheet = get_google_worksheet(sa_info, spreadsheet_key)
        st.success("✅ 구gl 스프레드시트 연결에 성공했습니다!")
        
        # 예시 데이터 가져오기 (시트 전체 레코드 읽기)
        data = worksheet.get_all_records()
        if data:
            st.subheader("📋 구글 시트 데이터 현황")
            st.dataframe(data)
        else:
            st.info("시트에 표시할 데이터가 없거나 비어 있습니다.")
            
    except Exception as e:
        st.error(f"구글 시트를 불러오는 중 에러가 발생했습니다: {e}")

    # 유튜브 API 객체 생성 실행
    try:
        youtube = get_youtube_client(youtube_api_key)
        # 여기에 추가적인 유튜브 채널 검색이나 영상 데이터를 가져오는 로직을 작성하시면 됩니다.
    except Exception as e:
        st.error(f"유튜브 API 연결 중 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
