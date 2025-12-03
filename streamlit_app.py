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
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (최종 수정) 🚨🚨🚨
        # -----------------------------------------------------------
        
        # 1. Wide Format을 Long Format으로 변환 (컬럼명 확정)
        # 이미 파일에 '범죄대분류', '범죄중분류' 컬럼이 존재함.
        id_cols = ['범죄대분류', '범죄중분류'] 
        
        # '횟수' 컬럼명을 아직 모르므로, 횟수 부분은 melt의 value_name으로 처리
        # melt를 실행하기 위해, id_cols와 겹치지 않는 나머지 컬럼(oo구)들을 value_vars로 간주함.

        df_long = pd.melt(df_crime, 
                          id_vars=id_cols,
                          var_name='시군구',      
                          value_name='횟수')       
        
        # 2. '시군구' 컬럼 정리 (좌표 데이터와 일치시키기 위해)
        # 만약 구 이름이 '종로구'처럼 좌표 데이터와 정확히 일치하지 않는다면 여기서 수정 필요
        # 예: df_long['시군구'] = df_long['시군구'].str.replace('서울', '').str.strip() 

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
        st.error(f"🔴 Fatal Error: CSV 파일 인코딩 오류. 파일을 UTF-8로 저장 후 재시도하세요.")
        return pd.DataFrame()
    except KeyError as e:
        # 이 시점에서 KeyError가 발생하면 대부분 '시군구' 병합 오류 또는 '범죄대분류/중분류' 오류가 아님.
        # 다른 컬럼(예: '시도', '위도', '경도')이 없거나, melt 과정에서 문제가 발생한 경우임.
        st.error(f"🔴 Critical Error: 데이터 구조 오류 발생! 다음 컬럼을 찾을 수 없습니다: {e}")
        st.warning("🚨 [해결 방법]: 범죄 데이터 파일의 '범죄대분류' 또는 '범죄중분류' 컬럼 외에, 좌표 파일에 '시도', '시군구' 컬럼이 있는지 확인하세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"🔴 Data Processing Error: 데이터 처리 중 일반 오류 발생: {e}")
        return pd.DataFrame()

# --------------------------------------------------------------------------------------
## 📊 Streamlit 대시보드 레이아웃 및 시각화 로직
# --------------------------------------------------------------------------------------

df_raw = load_data()

st.set_page_config(layout="wide")
st.title("⚖️ 서울시 범죄 통계 분석 대시보드")
st.markdown("---")

if df_raw.empty:
    st.error("데이터 로드에 실패했거나, 병합 후 남아있는 유효한 데이터가 없습니다. 위 오류 메시지를 확인하세요.")
    st.stop()
    
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
    selected_gu_detail = st.sidebar.selectbox("세부 정보를 볼 자치구 선택", options=gu_options)

# --------------------------------------------------------------------------------------
## 📌 메인 콘텐츠 출력
# --------------------------------------------------------------------------------------

# ----------------------------------------------------
# 모드 1: 지도 시각화
# ----------------------------------------------------
if analysis_mode == '지도 시각화 (범죄 분류 기준)':
    st.header(f"📍 {selected_major} - {selected_minor} 범죄 구별 발생 횟수 지도")
    
    df_map = df_filtered.groupby('시군구').agg(
        total_count=('횟수', 'sum'),
        위도=('위도', 'first'),
        경도=('경도', 'first')
    ).reset_index()
    
    if df_map.empty or df_map['total_count'].sum() == 0:
        st.warning("선택 조건에 맞는 데이터가 없거나 횟수가 0
