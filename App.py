import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 1. Google Sheets 연결 함수
@st.cache_resource
def get_google_worksheet(_sa_info, spreadsheet_key):
    # Secrets 원본 손상을 막기 위해 딕셔너리 복사
    info = dict(_sa_info)
    
    # Secrets창에 한 줄로 입력된 \n 문자열을 파이썬이 인식하는 실제 줄바꿈(개행문자)으로 강제 변환
    if "private_key" in info and isinstance(info["private_key"], str):
        # 역슬래시 2개로 들어오는 경우와 1개로 들어오는 경우를 모두 처리합니다.
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        
    # 복원된 자격 증명 정보로 구글 권한(Credentials) 생성
    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    # gspread를 통한 스프레드시트 열기
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_key)
    return sheet.get_worksheet(0)

# 2. YouTube API 호출 함수
@st.cache_resource
def get_youtube_client(api_key):
    return build("youtube", "v3", developerKey=api_key)

def main():
    st.set_page_config(page_title="YouTube & Google Sheets Dashboard", layout="wide")
    st.title("📊 유튜브 데이터 및 구글 시트 대시보드")

    # Streamlit Cloud 세팅에 등록한 Secrets 값 안전하게 파싱
    try:
        youtube_api_key = st.secrets["YOUTUBE_API_KEY"]
        spreadsheet_key = st.secrets["SPREADSHEET_KEY"]
        sa_info = st.secrets["gcp_service_account"]
    except KeyError as e:
        st.error(f"Streamlit Cloud의 Secrets 설정에서 Key를 찾을 수 없습니다: {e}")
        st.info("Advanced settings -> Secrets에 값이 올바르게 입력되었는지 확인해 주세요.")
        return

    # 구글 시트 데이터 연동 실행
    try:
        worksheet = get_google_worksheet(sa_info, spreadsheet_key)
        st.success("✅ 구글 스프레드시트 연결에 성공했습니다!")
        
        # 전체 행 읽어오기 테스트
        data = worksheet.get_all_records()
        if data:
            st.subheader("📋 구글 시트 데이터 현황")
            st.dataframe(data)
        else:
            st.info("시트에 표시할 데이터가 없거나 비어 있습니다.")
            
    except Exception as e:
        st.error(f"구글 시트를 불러오는 중 에러가 발생했습니다: {e}")

    # 유튜브 API 연동 실행
    try:
        youtube = get_youtube_client(youtube_api_key)
    except Exception as e:
        st.error(f"유튜브 API 연결 중 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
