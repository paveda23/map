import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import altair as alt

# --- 1. 데이터 로드 및 전처리 (인코딩 및 병합 로직 포함) ---
@st.cache_data
def load_data(crime_file='seoul_crime_data.csv', coord_file='전국 중심 좌표데이터.csv'):
    # 인코딩 시도 목록 (한국어 CSV 파일에 가장 흔한 순서)
    encodings = ['utf-8', 'cp949', 'euc-kr']
    df_crime = None
    df_coord = None
    
    # 두 파일의 인코딩을 순차적으로 시도하는 헬퍼 함수
    def try_read_csv(file_path):
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                st.info(f"✅ 파일 '{file_path}'를 {enc} 인코딩으로 성공적으로 읽었습니다.")
                return df
            except Exception:
                continue
        raise UnicodeDecodeError(f"'{file_path}' 파일을 지원되는 인코딩으로 읽을 수 없습니다.")

    try:
        # 파일 로드 시도
        df_crime = try_read_csv(crime_file)
        df_coord = try_read_csv(coord_file)

        # 2. 위경도 데이터 전처리 (서울시 구별 평균 좌표 계산)
        
        # '시도' 컬럼을 포함하는지 확인 후 서울시 데이터 필터링
        if '시도' in df_coord.columns:
            # 전국 데이터이므로 '서울특별시' 또는 '서울'로 시작하는 데이터 필터링
            df_coord = df_coord[df_coord['시도'].str.contains('서울', na=False)].copy()
        else:
            st.warning("경고: 좌표 데이터에 '시도' 컬럼이 없어 전국 데이터를 모두 사용하거나, 이미 서울시로 필터링되어 있다고 가정합니다.")

        # 구별 평균 위경도 계산
        df_gu_coord = df_coord.groupby('시군구').agg(
            위도=('위도', 'mean'),
            경도=('경도', 'mean')
        ).reset_index()
        
        # 3. 범죄 데이터와 구별 평균 좌표 합치기 (Merge)
        df_merged = pd.merge(df_crime, 
                             df_gu_coord, 
                             on='시군구', 
                             how='left')
        
        # 4. 필수 컬럼 검사 및 숫자형 변환
        required_cols = ['시군구', '위도', '경도', '범죄대분류', '범죄중분류', '횟수']
        if not all(col in df_merged.columns for col in required_cols):
            st.error(f"⚠️ 병합된 데이터에 다음 필수 컬럼이 모두 포함되어야 합니다: {', '.join(required_cols)}")
            st.dataframe(df_merged.head()) # 데이터 구조 확인을 위해 상위 5개 행 출력
            return pd.DataFrame() 

        df_merged['횟수'] = pd.to_numeric(df_merged['횟수'], errors='coerce').fillna(0)
        
        # 위경도 정보가 없는 구가 있다면 경고
        if df_merged['위도'].isnull().any():
            st.warning("⚠️ 일부 구의 위경도 정보가 좌표 파일에 없어 시각화에서 누락될 수 있습니다.")
            df_merged.dropna(subset=['위도', '경도'], inplace=True) # 위경도 없는 행 제거
            
        return df_merged

    except UnicodeDecodeError as e:
        st.error(f"Fatal Error: CSV 파일의 인코딩을 자동으로 찾을 수 없습니다. 파일을 UTF-8로 변환하거나 인코딩을 수동으로 확인해 주세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return pd.DataFrame()

df_raw = load_data()

if df_raw.empty:
    st.stop()

# --------------------------------------------------------------------------------------
## 📊 Streamlit 대시보드 레이아웃 및 시각화 로직
# --------------------------------------------------------------------------------------

st.set_page_config(layout="wide")
st.title("⚖️ 서울시 범죄 통계 분석 대시보드")
st.markdown("---")

# --- 사이드바 설정 ---
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
        st.warning("선택하신 조건에 해당하는 범죄 데이터가 없거나 횟수가 0입니다.")
    else:
        min_count = df_map['total_count'].min()
        max_count = df_map['total_count'].max()
        
        center_lat = df_map['위도'].mean()
        center_lon = df_map['경도'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")
        
        # 색상 설정 함수 (Yellow -> Red 스케일)
        def get_color(count, min_val, max_val):
            if max_val == min_val: return '#FF0000'
            normalized = (count - min_val) / (max_val - min_val)
            g_value = int(255 * (1 - normalized))
            return f'#{255:02x}{g_value:02x}{0:02x}'

        # 지도에 마커 추가
        for idx, row in df_map.iterrows():
            crime_count = row['total_count']
            fill_color = get_color(crime_count, min_count, max_count)
            
            radius_scale = 0.05 
            radius = (crime_count * radius_scale) if crime_count > 0 else 5
            
            popup_html = f"**자치구:** {row['시군구']}<br>**범죄 횟수:** {int(crime_count)}건<br>"
            
            line_weight = 2
            border_color = fill_color
            
            # 최고/최저 범죄 구 강조 시각화
            if crime_count == max_count and max_count > 0:
                line_weight = 5
                border_color = 'black' # 최고값 강조 (테두리 두께)
            elif crime_count == min_count and min_count < max_count:
                line_weight = 5
                border_color = 'white' # 최저값 강조 (테두리 두께)
                
            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=radius + 10,
                popup=popup_html,
                color=border_color,
                weight=line_weight,
                fill=True,
                fill_color=fill_color,
                fill_opacity=0.7
            ).add_to(m)

        folium_static(m, width=1000, height=650)
        
        st.markdown(f"**범례:** 🟥 진한 붉은색일수록 횟수가 높음 (최고 **{int(max_count)}**건), 🟨 노란색일수록 횟수가 낮음 (최저 **{int(min_count)}**건)")
        
# ----------------------------------------------------
# 모드 2: 지역 세부 통계
# ----------------------------------------------------
else: 
    st.header(f"📊 {selected_gu_detail} 세부 범죄 통계")
    
    df_gu = df_raw[df_raw['시군구'] == selected_gu_detail].copy()
    
    if df_gu.empty:
        st.warning(f"{selected_gu_detail}의 세부 데이터가 없습니다.")
    else:
        # --- 4.1 대분류별 통계 Bar Chart ---
        st.subheader("1. 범죄 대분류별 횟수")
        df_major = df_gu.groupby('범죄대분류')['횟수'].sum().reset_index()
        
        chart_major = alt.Chart(df_major).mark_bar().encode(
            x=alt.X('횟수', title='범죄 횟수'),
            y=alt.Y('범죄대분류', sort='-x', title='범죄 대분류'),
            tooltip=['범죄대분류', '횟수'],
            color=alt.Color('횟수', scale=alt.Scale(range=['#ADD8E6', '#00008B']), legend=None)
        ).properties(
            height=300
        ).interactive()
        
        st.altair_chart(chart_major, use_container_width=True)

        # --- 4.2 중분류별 상세 통계 Table ---
        st.subheader(f"2. 범죄 중분류별 상세 횟수")
        df_minor = df_gu.pivot_table(
            index='범죄대분류', 
            columns='범죄중분류', 
            values='횟수', 
            aggfunc='sum'
        ).fillna(0).astype(int)
        
        st.dataframe(df_minor)

        st.markdown("---")
        st.info(f"💡 **인사이트 도출:** {selected_gu_detail}에서 가장 높은 비율을 차지하는 **대분류** 범죄가 무엇인지 확인하고, 해당 분류에 속하는 **중분류** 범계의 세부 횟수를 분석하세요.")
