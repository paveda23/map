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
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (이 부분만 수정하세요!) 🚨🚨🚨
        # -----------------------------------------------------------
        
        # Wide Format (oo구 컬럼)을 Long Format으로 변환하기 위한 ID 컬럼 정의
        id_cols = [
            '범죄대분류',  # 예: '범죄대분류', '구분'
            '범죄중분류'   # 예: '범죄중분류', '항목'
        ]

        # 1. Wide Format을 Long Format으로 변환
        df_long = pd.melt(df_crime, 
                          id_vars=id_cols,
                          var_name='시군구',      # 자치구 컬럼 이름 설정
                          value_name='횟수')       # 횟수 컬럼 이름 설정
        
        # 2. ID_VARS를 표준 이름으로 매핑
        df_long.rename(columns={
            id_cols[0]: '범죄대분류',
            id_cols[1]: '범죄중분류',
        }, inplace=True)
        
        df_crime = df_long 

        # 3. 위경도 데이터 전처리 (서울시 구별 평균 좌표 계산)
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
        
        # 5. 필수 컬럼 정리
        df_merged['횟수'] = pd.to_numeric(df_merged['횟수'], errors='coerce').fillna(0)
        df_merged.dropna(subset=['위도', '경도'], inplace=True)
            
        return df_merged

    except UnicodeDecodeError as e:
        # 이 오류가 발생하면, 사용자에게 인코딩 문제임을 명확히 알립니다.
        st.error(f"🔴 Fatal Error: CSV 파일 인코딩 오류가 발생했습니다. 파일을 UTF-8로 저장 후 다시 시도하세요.")
        st.dataframe(df_crime.head()) # 로드된 데이터의 상위 몇 행 출력
        return pd.DataFrame()
    except KeyError as e:
        # 컬럼 이름 오류가 발생하면, 어떤 컬럼이 문제인지 정확히 알려줍니다.
        st.error(f"🔴 Critical Error: 컬럼 이름 오류 발생! 다음 컬럼을 찾을 수 없습니다: {e}")
        st.warning("🚨 [해결 방법]: `load_data` 함수 내 `id_cols` 변수에 실제 CSV 파일에 있는 컬럼 이름(따옴표 포함)을 정확히 입력했는지 확인하세요.")
        st.dataframe(df_crime.head())
        return pd.DataFrame()
    except Exception as e:
        # 기타 모든 오류는 일반 Exception으로 처리합니다.
        st.error(f"🔴 Data Processing Error: 데이터 처리 중 일반 오류 발생: {e}")
        return pd.DataFrame()

# --------------------------------------------------------------------------------------
## 📊 Streamlit 대시보드 레이아웃 및 시각화 로직
# --------------------------------------------------------------------------------------

df_raw = load_data()

# if df_raw.empty: st.stop() 명령을 제거하여 오류 메시지가 표시되도록 유도합니다.

if df_raw.empty:
    st.error("데이터 로드에 실패했거나, 병합 후 남아있는 유효한 데이터가 없습니다.")
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
    st.sidebar.subheader("범
