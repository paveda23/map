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
        # 🚨 데이터 처리 및 정규화 (오류 방지 핵심 로직)
        # -----------------------------------------------------------
        
        # 1. Wide Format을 Long Format으로 변환 (범죄 데이터)
        # ID 컬럼은 '범죄대분류', '범죄중분류'로 확정
        id_cols = ['범죄대분류', '범죄중분류'] 
        
        df_long = pd.melt(df_crime, 
                          id_vars=id_cols,
                          var_name='시군구',      
                          value_name='횟수')       
        
        df_crime = df_long 
        
        # 2. 위경도 데이터 전처리 (좌표 데이터)
        # 좌표 파일 컬럼명 확정 및 서울 필터링
        df_coord_seoul = df_coord[df_coord['시도'] == '서울특별시'].copy()
        
        # 3. 시군구 이름 정규화 (두 데이터의 구 이름 불일치 방지)
        
        # 3.1 범죄 데이터 '시군구' 정규화
        # 예: '서울종로구' -> '종로구', '종로구 ' -> '종로구'
        df_crime['시군구'] = df_crime['시군구'].str.replace('서울', '').str.strip()
        
        # 3.2 좌표 데이터 '시군구' 정규화
        df_coord_seoul['시군구'] = df_coord_seoul['시군구'].str.strip() 

        # 4. 구별 평균 위경도 계산
        df_gu_coord = df_coord_seoul.groupby('시군구').agg(
            위도=('위도', 'mean'),
            경도=('경도', 'mean')
        ).reset_index()
        
        # 5. 데이터 병합 (Merge)
        df_merged = pd.merge(df_crime, 
                             df_gu_coord, 
                             on='시군구', 
                             how='left')
        
        # 6. 필수 컬럼 정리
        required_cols = ['시군구', '위도', '경도', '범죄대분류', '범죄중분류', '횟수']
        if not all(col in df_merged.columns for col in required_cols):
             # 이 단계에서 오류가 발생하면, merge가 실패했거나 정규화가 잘못된 것입니다.
            raise KeyError(f"최종 필수 컬럼 누락: {', '.join([c for c in required_cols if c not in df_merged.columns])}")

        df_merged['횟수'] = pd.to_numeric(df_merged['횟수'], errors='coerce').fillna(0)
        df_merged.dropna(subset=['위도', '경도'], inplace=True)
            
        return df_merged

    except UnicodeDecodeError as e:
        st.error(f"🔴 Fatal Error: CSV 파일 인코딩 오류.")
        return pd.DataFrame()
    except KeyError as e:
        st.error(f"🔴 Critical Error: 데이터 구조 오류 발생! 다음 컬럼을 찾을 수 없습니다: {e}")
        st.warning(f"🚨 [해결 방법]: 범죄 데이터에 '범죄대분류', '범죄중분류' 컬럼이 실제로 있는지, 또는 좌표 데이터에 '시도', '시군구', '위도', '경도' 컬럼이 있는지 확인하세요.")
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
    st.info("데이터 로드가 완료되지 않아 대시보드가 표시되지 않습니다. 위 오류 메시지를 확인하세요.")
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
# ----------------------------------------------------
# 모드 1: 지도 시각화
# ----------------------------------------------------
if analysis_mode == '지도 시각화 (범죄 분류 기준)':
    st.header(f"📍 {selected_major} - {selected_minor} 범죄 구별 발생 횟수 지도")
    
    # 1. 구별로 횟수 합산 및 지도 시각화에 필요한 정보만 그룹화
    df_map = df_filtered.groupby('시군구').agg(
        total_count=('횟수', 'sum'),
        위도=('위도', 'first'),
        경도=('경도', 'first')
    ).reset_index()

    if df_map.empty or df_map['total_count'].sum() == 0:
        st.warning("선택 조건에 맞는 데이터가 없거나 횟수가 0입니다.")
    else:
        min_count = df_map['total_count'].min()
        max_count = df_map['total_count'].max()
        
        # 🚨 [새로운 로직] 전체 합계 대비 비율 계산
        total_sum_all_gu = df_map['total_count'].sum()
        df_map['비율'] = (df_map['total_count'] / total_sum_all_gu) * 100
        
        center_lat = df_map['위도'].mean()
        center_lon = df_map['경도'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")
        
        def get_color(count, min_val, max_val):
            if max_val == min_val: return '#FF0000'
            normalized = (count - min_val) / (max_val - min_val)
            g_value = int(255 * (1 - normalized))
            return f'#{255:02x}{g_value:02x}{0:02x}'

        for idx, row in df_map.iterrows():
            crime_count = row['total_count']
            fill_color = get_color(crime_count, min_count, max_count)
            
            radius = (crime_count * 0.05) if crime_count > 0 else 5
            
            # 🚨 [수정된 팝업] 팝업 내용에 범죄 횟수와 비율 추가
            popup_html = f"""
            <b>📍 {row['시군구']} 범죄 현황</b><br>
            --------------------------<br>
            총 횟수: <b>{int(crime_count)}건</b><br>
            전체 대비 비율: <b>{row['비율']:.2f}%</b>
            """
            
            line_weight = 2
            border_color = fill_color
            
            if crime_count == max_count and max_count > 0:
                line_weight = 5
                border_color = 'black'
            elif crime_count == min_count and min_count < max_count:
                line_weight = 5
                border_color = 'white'
                
            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=radius + 10,
                popup=folium.Popup(popup_html, max_width=300), # max_width 설정으로 가독성 개선
                color=border_color,
                weight=line_weight,
                fill=True,
                fill_color=fill_color,
                fill_opacity=0.7
            ).add_to(m)

        folium_static(m, width=1000, height=650)
        
        st.markdown(f"**범례:** 🟥 높은 횟수 (최고 **{int(max_count)}**건, **{df_map['비율'].max():.2f}%**), 🟨 낮은 횟수 (최저 **{int(min_count)}**건, **{df_map['비율'].min():.2f}%**)")
        
# ----------------------------------------------------
# 모드 2: 지역 세부 통계
# ----------------------------------------------------
else: 
    st.header(f"📊 {selected_gu_detail} 세부 범죄 통계")
    
    df_gu = df_raw[df_raw['시군구'] == selected_gu_detail].copy()
    
    if df_gu.empty:
        st.warning(f"데이터가 없습니다.")
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
