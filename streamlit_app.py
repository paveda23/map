import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static

# --- 1. 데이터 로드 및 전처리 ---
# GitHub 저장소에 있는 CSV 파일을 읽기 위한 함수
# 파일명을 'seoul_crime_data.csv'라고 가정하고, 상대 경로로 접근합니다.
@st.cache_data
def load_data(file_path='seoul_crime_data.csv'):
    try:
        # 실제 데이터 로드
        df = pd.read_csv(file_path)

        # 데이터 클리닝 및 서울시로 한정 (필요하다면)
        if '시도' in df.columns:
            df = df[df['시도'] == '서울'].copy()
        
        # 필수 컬럼 검사 및 처리
        required_cols = ['시군구', '동', '위도', '경도', '범죄_발생건수', '인구수']
        if not all(col in df.columns for col in required_cols):
            st.error(f"⚠️ 데이터 파일에 다음 필수 컬럼이 모두 포함되어야 합니다: {', '.join(required_cols)}")
            return pd.DataFrame() # 빈 데이터프레임 반환

        # 숫자형 변환 및 범죄율 계산 (만 명당)
        df['범죄_발생건수'] = pd.to_numeric(df['범죄_발생건수'], errors='coerce')
        df['인구수'] = pd.to_numeric(df['인구수'], errors='coerce')
        
        # 인구수가 0이 아닌 경우에만 계산, 0일 경우 1로 대체하여 나눗셈 오류 방지
        df['범죄율_만명당'] = (df['범죄_발생건수'] / df['인구수'].replace(0, 1)) * 10000 
        
        return df

    except FileNotFoundError:
        st.error(f"⚠️ 데이터 파일 '{file_path}'를 찾을 수 없습니다. GitHub 경로와 파일명을 확인해 주세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 로드 및 처리 중 오류 발생: {e}")
        return pd.DataFrame()

df = load_data()

# 데이터가 비어있으면 앱 실행 중단
if df.empty:
    st.stop()

# --- 2. Streamlit 레이아웃 설정 ---
st.set_page_config(layout="wide")
st.title("🚨 서울시 안전 지도 대시보드: 구/동별 범죄율 분석")
st.markdown("---")

# --- 3. 사이드바 인터랙션 요소 (필터) ---
st.sidebar.header("🔍 분석 필터")

# 시군구(구) 선택 필터
selected_gu = st.sidebar.selectbox(
    "자치구 선택",
    options=['전체'] + sorted(df['시군구'].unique().tolist())
)

# 데이터 필터링 (구 단위)
if selected_gu != '전체':
    filtered_df = df[df['시군구'] == selected_gu].copy()
    unit_name = selected_gu # 현재 선택된 단위를 표시
else:
    filtered_df = df.copy()
    unit_name = "서울시 전체"

# 범죄율 기준 슬라이더
min_rate = filtered_df['범죄율_만명당'].min()
max_rate = filtered_df['범죄율_만명당'].max()

rate_range = st.sidebar.slider(
    '만 명당 범죄율 범위 선택',
    min_value=min_rate,
    max_value=max_rate,
    value=(min_rate, max_rate)
)

# 최종 데이터 필터링
final_df = filtered_df[
    (filtered_df['범죄율_만명당'] >= rate_range[0]) &
    (filtered_df['범죄율_만명당'] <= rate_range[1])
]

# --- 4. 메인 콘텐츠 (지도 및 통계) ---

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"🗺️ {unit_name} 지역별 안전 지도 (구/동)")

    if not final_df.empty:
        # Folium 지도 초기화: 필터링된 데이터의 평균 위경도를 중심으로 설정
        center_lat = final_df['위도'].mean()
        center_lon = final_df['경도'].mean()
        
        # 줌 레벨 조정: '전체' 선택 시 더 넓게, 특정 '구' 선택 시 더 상세하게
        zoom_level = 11 if selected_gu == '전체' else 13
        
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=zoom_level, 
            tiles="CartoDB positron"
        )
        
        # 지도에 마커 추가
        global_min_rate = df['범죄율_만명당'].min()
        global_max_rate = df['범죄율_만명당'].max()
        
        for idx, row in final_df.iterrows():
            # 범죄율에 따른 색상 설정 (예: 비율이 높을수록 빨강)
            normalized_rate = (row['범죄율_만명당'] - global_min_rate) / (global_max_rate - global_min_rate + 1e-6)
            
            # 색상을 Red (위험) - Blue (안전) 스케일로 지정
            # 높은 범죄율(Normalized 1.0)은 빨강, 낮은 범죄율(Normalized 0.0)은 파랑에 가깝게 설정
            color_hex = f'#{int(255 * normalized_rate):02x}{int(255 * (1-normalized_rate)):02x}00'
            
            # 마커 팝업 내용
            popup_html = f"""
            **자치구:** {row['시군구']}<br>
            **행정동:** {row['동']}<br>
            **범죄율 (만 명당):** {row['범죄율_만명당']:.2f}<br>
            **발생 건수:** {row['범죄_발생건수']}건
            """

            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=row['범죄율_만명당'] * 0.8, # 범죄율에 따라 크기 조정 (단위가 동이라서 반경을 좀 줄였습니다.)
                popup=popup_html,
                color=f"#{int(255 * normalized_rate):02x}{int(255 * (1-normalized_rate)):02x}00",
                fill=True,
                fill_color=f"#{int(255 * normalized_rate):02x}{int(255 * (1-normalized_rate)):02x}00",
                fill_opacity=0.7
            ).add_to(m)

        # Streamlit에 Folium 지도 출력
        folium_static(m, width=800, height=600)
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")

with col2:
    st.subheader("📊 통계 요약")
    if not final_df.empty:
        st.metric(
            label=f"{unit_name} 평균 범죄율 (만 명당)",
            value=f"{final_df['범죄율_만명당'].mean():.2f}"
        )
        
        # 최고 범죄율 지역 (동 단위)
        highest_crime_loc = final_df.loc[final_df['범죄율_만명당'].idxmax()]
        st.metric(
            label="최고 범죄율 동",
            value=f"{highest_crime_loc['시군구']} {highest_crime_loc['동']}",
            delta=f"{highest_crime_loc['범죄율_만명당']:.2f} (만 명당)"
        )
        st.markdown("**필터링된 위험 지역**")
        st.dataframe(
            final_df[['시군구', '동', '범죄율_만명당', '범죄_발생건수']]
            .sort_values(by='범죄율_만명당', ascending=False)
            .head(10) # 상위 10개 동만 표시
        )
    else:
        st.info("데이터가 필터링되지 않았습니다.")

# --- 5. 결론 및 인사이트 ---
st.markdown("---")
st.header("💡 분석 인사이트 제안")
st.info("""
    특정 '자치구'를 선택하여 그 안의 '동별' 범죄율을 비교 분석해 보세요.
    인구수 대비 범죄율이 높은 '동'을 찾아 해당 지역의 특성(예: 유동 인구, 상업 시설)을 연결하여 문제의식을 구체화할 수 있습니다.
""")

# 실행 방법: 터미널에서 `streamlit run [파일명].py` 명령어로 실행
