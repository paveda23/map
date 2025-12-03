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
        # 🚨🚨🚨 범죄 데이터 컬럼 이름 매핑 (사용자가 반드시 수정해야 할 부분) 🚨🚨🚨
        # -----------------------------------------------------------
        # 이 부분이 실행될 때 '시군구' 오류가 발생했다면, 
        # 실제 범죄 데이터의 컬럼 이름을 확인 후 아래 매핑 예시를 수정해야 합니다.
        df_crime.rename(columns={
            '실제_구_이름': '시군구',             
            '실제_대분류_이름': '범죄대분류',   
            '실제_중분류_이름': '범죄중분류',   
            '실제_횟수_이름': '횟수'          
        }, inplace=True)
        # -----------------------------------------------------------


        # 2. 위경도 데이터 전처리 (서울시 구별 평균 좌표 계산)
        
        # 좌표 데이터는 사용자님 CSV 구조 ('시도', '시군구', '읍면동', '위도', '경도')를 따름
        
        # 서울시 데이터로 필터링
        # 제공해주신 구조에 따라 '시도' 컬럼을 사용합니다.
        df_coord_seoul = df_coord[df_coord['시도'] == '서울특별시'].copy()
        
        # 구별 평균 위경도 계산 (동별 데이터를 구의 중심으로 집계)
        df_gu_coord = df_coord_seoul.groupby('시군구').agg(
            위도=('위도', 'mean'),
            경도=('경도', 'mean')
        ).reset_index()
        
        # 3. 범죄 데이터와 구별 평균 좌표 합치기 (Merge)
        # 범죄 데이터의 '시군구' 컬럼과 좌표 데이터의 '시군구' 컬럼을 기준으로 합칩니다.
        df_merged = pd.merge(df_crime, 
                             df_gu_coord, 
                             on='시군구', 
                             how='left')
        
        # 4. 필수 컬럼 검사 및 숫자형 변환 (코드의 안정성을 위해 유지)
        required_cols = ['시군구', '위도', '경도', '범죄대분류', '범죄중분류', '횟수']
        if not all(col in df_merged.columns for col in required_cols):
            st.error(f"⚠️ 병합된 데이터에 다음 필수 컬럼이 모두 포함되어야 합니다: {', '.join(required_cols)}")
            return pd.DataFrame() 

        df_merged['횟수'] = pd.to_numeric(df_merged['횟수'], errors='coerce').fillna(0)
        df_merged.dropna(subset=['위도', '경도'], inplace=True) # 위경도 없는 행 제거
            
        return df_merged

    except UnicodeDecodeError as e:
        st.error(f"Fatal Error: CSV 파일의 인코딩을 자동으로 찾을 수 없습니다. 파일을 UTF-8로 변환하거나 인코딩을 수동으로 확인해 주세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        st.error(f"주로 컬럼 이름 오류입니다. 범죄 데이터의 '시군구', '범죄대분류', '범죄중분류', '횟
