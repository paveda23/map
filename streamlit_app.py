import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static

## 1. 데이터 로드 및 전처리 (예시)
# 실제 데이터셋(범죄 통계, 지역별 위경도 정보 등)의 경로로 변경해야 합니다.
# 이 예시에서는 가상의 데이터 구조를 가정합니다.
# 데이터 파일명: safety_data.csv
@st.cache_data
def load_data():
    # 실제 데이터셋을 로드하는 코드로 대체하세요.
    # 예시 데이터 생성: '시도', '시군구', '위도', '경도', '범죄_발생건수' 등의 컬럼이 필요합니다.
    data = pd.DataFrame({
        '시도': ['서울', '서울', '부산', '대구', '서울'],
        '시군구': ['강남구', '노원구', '해운대구', '수성구', '강남구'],
        '위도': [37.5172, 37.6542, 35.1601, 35.8458, 37.5172],
        '경도': [127.0473, 127.0567, 129.1610, 128.6253, 127.0473],
        '범죄_발생건수': [800, 350, 450, 200, 800],
        '인구수': [500000, 450000, 400000, 430000, 500000],
        '범죄율_만명당': [16.0, 7.8, 11.3, 4.7, 16.0] # (발생건수/인구수) * 10000
    })
    return data

df = load_data()

## 2. Streamlit 레이아웃 설정
st.set_page_config(layout="wide")
st.title("🚨 우리 동네 안전 지도 대시보드 (범죄율 분석)")
st.markdown("---")

# 레이아웃 분할 (사이드바와 메인 화면)
st.sidebar.header("🔍 분석 필터")

## 3. 사이드바 인터랙션 요소 (필터)

# 지역 선택 필터
selected_city = st.sidebar.selectbox(
    "시/도 선택",
    options=['전체'] + sorted(df['시도'].unique().tolist())
)

# 데이터 필터링
if selected_city != '전체':
    filtered_df = df[df['시도'] == selected_city].copy()
else:
    filtered_df = df.copy()

# 범죄율 기준 슬라이더
min_crime_rate = filtered_df['범죄율_만명당'].min()
max_crime_rate = filtered_df['범죄율_만명당'].max()

rate_range = st.sidebar.slider(
    '만 명당 범죄율 범위 선택',
    min_value=min_crime_rate,
    max_value=max_crime_rate,
    value=(min_crime_rate, max_crime_rate)
)

final_df = filtered_df[
    (filtered_df['범죄율_만명당'] >= rate_range[0]) &
    (filtered_df['범죄율_만명당'] <= rate_range[1])
]

## 4. 메인 콘텐츠 (지도 및 통계)

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"🗺️ {selected_city} 지역 안전 지도")

    if not final_df.empty:
        # Folium 지도 초기화 (필터링된 데이터의 평균 위경도를 중심으로 설정)
        center_lat = final_df['위도'].mean()
        center_lon = final_df['경도'].mean()
        
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11, 
            tiles="CartoDB positron"
        )
        
        # 지도에 마커/원형 마커 추가 (범죄율에 따라 크기/색상 변화)
        for idx, row in final_df.iterrows():
            # 범죄율에 따른 색상 설정 (예시: 높을수록 빨강)
            color_scale = 1 + (row['범죄율_만명당'] - min_crime_rate) / (max_crime_rate - min_crime_rate + 1e-6) * 4 
            fill_color = 'red' if row['범죄율_만명당'] >= final_df['범죄율_만명당'].mean() else 'blue'

            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=row['범죄율_만명당'] * 2,  # 범죄율에 따라 크기 조정
                popup=f"**지역:** {row['시군구']} ({row['시도']})<br>**범죄율 (만 명당):** {row['범죄율_만명당']:.2f}<br>**발생 건수:** {row['범죄_발생건수']}건",
                color=fill_color,
                fill=True,
                fill_color=fill_color,
                fill_opacity=0.6
            ).add_to(m)

        # Streamlit에 Folium 지도 출력
        folium_static(m, width=800, height=600)
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")

with col2:
    st.subheader("📊 통계 요약")
    if not final_df.empty:
        st.metric(
            label="선택 지역 평균 범죄율 (만 명당)",
            value=f"{final_df['범죄율_만명당'].mean():.2f}"
        )
        st.metric(
            label="최고 범죄율 지역",
            value=final_df.loc[final_df['범죄율_만명당'].idxmax(), '시군구']
        )
        st.markdown("**필터링된 데이터 미리보기**")
        st.dataframe(final_df[['시도', '시군구', '범죄율_만명당', '범죄_발생건수']].sort_values(by='범죄율_만명당', ascending=False).head(5))
    else:
        st.info("데이터가 필터링되지 않았거나 존재하지 않습니다.")

## 5. 결론 및 인사이트
st.markdown("---")
st.header("💡 주요 인사이트 도출")
st.info("""
    이 대시보드를 통해 특정 지역의 **범죄율이 높은 이유**를 분석할 수 있습니다. 
    예: '강남구'는 발생 건수가 높지만, 인구 밀집도와 비교한 **범죄율**을 기준으로 실제 위험도를 판단해야 합니다.
    """)

# 실행 방법: 터미널에서 `streamlit run [파일명].py` 명령어로 실행
