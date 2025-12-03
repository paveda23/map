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
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (이 부분을 실제 파일 이름으로 수정해야 함) 🚨🚨🚨
        # -----------------------------------------------------------
        df_crime.rename(columns={
            '실제_구_이름': '시군구',             
            '실제_대분류_이름': '범죄대분류',   
            '실제_중분류_이름': '범죄중분류',   
            '실제_횟수_이름': '횟수'          
        }, inplace=True)
        # -----------------------------------------------------------

        # 2. 위경도 데이터 전처리 (서울시 구별 평균 좌표 계산)
        df_coord_seoul = df_coord[df_coord['시도'] == '서울특별시'].copy()
        
        df_gu_
