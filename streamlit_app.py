import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import altair as alt

# --- 1. 데이터 로드 및 전처리 (인코딩 및 병합 로직 포함) ---
@st.cache_data
def load_data(crime_file='seoul_crime_data.csv', coord_file='전국 중심 좌표데이터.csv'):
    encodings = ['utf-8', 'cp949', 'euc-kr']
    
    def try_read_csv(file_path):
        for enc in encodings:
            try:
                # 'header=0'은 첫 번째 줄을 컬럼 이름으로 인식하게 합니다.
                df = pd.read_csv(file_path, encoding=enc, header=0) 
                st.info(f"✅ 파일 '{file_path}'를 {enc} 인코딩으로 성공적으로 읽었습니다.")
                return df
            except Exception:
                continue
        raise UnicodeDecodeError(f"'{file_path}' 파일을 지원되는 인코딩으로 읽을 수 없습니다.")

    try:
        # 파일 로드 시도
        df_crime = try_read_csv(crime_file)
        df_coord = try_read_csv(coord_file)

        # -----------------------------------------------------------
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (이 부분을 반드시 수정하세요!) 🚨🚨🚨
        # -----------------------------------------------------------
        
        # 범죄 데이터 파일(df_crime)의 실제 컬럼 이름을 '시군구', '범죄대분류', '범죄중분류', '횟수'로 변경합니다.
        df_crime.rename(columns={
            '실제_구_이름': '시군구',             # 예: '자치구', '구명', '구_이름' 등을 '시군구'로 변경
            '실
