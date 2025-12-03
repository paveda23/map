import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import altair as alt

# --- 1. 데이터 로드 및 전처리 ---
@st.cache_data
def load_data(crime_file='seoul_crime_data.csv', coord_file='전국 중심 좌표데이터.csv'):
    encodings = ['utf-8', 'cp949', 'euc-kr']
    
    def try_read_csv(file_path):
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc, header=0) 
                return df
            except Exception:
                continue
        raise UnicodeDecodeError(f"'{file_path}' 파일을 지원되는 인코딩으로 읽을 수 없습니다.")

    try:
        df_crime = try_read_csv(crime_file)
        df_coord = try_read_csv(coord_file)

        # -----------------------------------------------------------
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (이 부분만 정확히 수정해야 함) 🚨🚨🚨
        # -----------------------------------------------------------
        
        # 1. 범죄 데이터 컬럼 이름 변경: '시군구'와 나머지 필수 컬럼을 매핑합니다.
        df_crime.rename(columns={
            '<실제 구 이름 컬럼명>': '시군구',             
            '<실제 대분류 컬럼명>': '범죄대분류',   
            '<실제 중분류 컬럼명>': '범죄중분류',   
            '<실제 횟수 컬럼명>': '횟수'          
        }, inplace=True)
        
        # 2. '서울종로구'와 같이 붙어있는 경우, '서울'을 제거하여 '종로구'만 남김 (필요시 주석 해제)
        # if '시군구' in df_crime.columns:
        #     df_crime['시군구'] = df_crime['시군구'].str.replace('서울', '').str.strip()

        # -----------------------------------------------------------

        # 3. 위경도 데이터 전처리 (서울시 구별 평균 좌표 계산)
        # 좌표 파일은 '시도', '시군구' 컬럼을 가지고 있다고 가정합니다.
        df_coord_seoul = df_coord[df_coord['시도'] == '서울특별시'].copy()
        
        df_gu_coord = df_coord_seoul.groupby('시군구').agg(
            위도=('위도', 'mean'),
            경도=('경도', 'mean')
        ).reset_index()
        
        # 4. 데이터 병합 (Merge)
        df_merged = pd.merge(df_crime, 
                             df_gu_coord, 
                             on='시군구', 
                             how='left')
        
        # 5. 필수 컬럼 검사 및 정리
        required_cols = ['시군구', '위도', '경도', '범죄대분류', '범죄중분류', '횟수']
        if not all(col in df_merged.columns for col in required_cols):
            st.error(f"⚠️ 병합된 데이터에 다음 필수 컬럼이 모두 포함되어야 합니다: {', '.join(required_cols)}")
            return pd.DataFrame() 

        df_merged['횟수'] = pd.to_numeric(df_merged['횟수'], errors='coerce').fillna(0)
        df_merged.dropna(subset=['위도', '경도'], inplace=True)
            
        return df_merged

    except UnicodeDecodeError as e:
        st.error(f"Fatal Error: CSV 파일 인코딩 오류.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        st.error("컬럼 이름 매핑을 다시 확인하세요.")
        return pd.DataFrame()

# --------------------------------------------------------------------------------------
## 📊 Streamlit 대시보드 레이아웃 및 시각화 로직
# --------------------------------------------------------------------------------------

df_raw = load_data()

if df_raw.empty:
    st.stop()

st.set_page_config(layout="wide")
st.title("⚖️ 서울시 범죄 통계 분석 대시보드")
st.markdown("---")

st.sidebar.header("🔍 분석 설정")

analysis_mode = st.sidebar.radio(
    "분석 모드 선택",
    ('지도 시각화 (범죄 분류 기준)', '지역 세부 통계 (자치구 기준)'),
    index=0
)

# --- 지도 시각화 모드 필터 ---
if analysis_mode == '지도 시각화 (범죄 분류 기준)':
    st.sidebar.subheader("범죄 분류 필터")
    
    major_categories = ['전체'] + sorted(df_raw['범죄대분류'].unique().tolist())
    selected_major = st.sidebar.selectbox("범죄 대분류 선택", options=major_categories)

    minor_options = ['전체']
    filtered_by_major = df_raw.copy()
    if selected_major != '전체':
        filtered_by_major = df_raw[df_raw['범죄대분류'] == selected_major]
        minor_options += sorted(filtered_by_major['범죄중분류'].unique().tolist())
    
    selected_minor = st.sidebar.selectbox("범죄 중분류 선택", options=minor_options)

    df_filtered = filtered_by_major.copy()
    if selected_minor != '전체':
        df_filtered = df_filtered[df_filtered['범죄중분류'] == selected_minor]

# --- 지역 세부 통계 모드 필터 ---
else:
    st.sidebar.subheader("지역 선택 필터")
    gu_options = sorted(df_raw['시군구'].unique().tolist())
    selected_gu_detail = st.sidebar.selectbox
