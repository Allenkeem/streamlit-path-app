import streamlit as st
import pandas as pd
from pulp import LpProblem, LpVariable, lpSum, LpMinimize, LpBinary, LpStatus
import folium
from streamlit_folium import st_folium

# --- 내부 데이터 불러오기 ---
nodes_df = pd.read_excel("locations.xlsx", sheet_name="Sheet1")
nodes_df = nodes_df.rename(columns={"Node No.": "node", "위도": "lat", "경도": "lon"})

edges_df = pd.read_excel("paths.xlsx", sheet_name="Sheet2")

# 타입 맞추기
nodes_df["node"] = nodes_df["node"].astype(int)
edges_df["from"] = edges_df["from"].astype(int)
edges_df["to"] = edges_df["to"].astype(int)

# --- Solver 방식 최단 경로 함수 ---
def solve_path_lp(df, start, end, max_angle):
    uses = [LpVariable(f"use_{i}", cat=LpBinary) for i in range(len(df))]

    prob = LpProblem("Shortest_Path_With_Angle_Constraint", LpMinimize)
    prob += lpSum(uses[i] * df.loc[i, 'distance (m)'] for i in range(len(df)))

    for i in range(len(df)):
        if df.loc[i, 'angle'] > max_angle or df.loc[i, 'allowed angle (binary)'] == 0:
            prob += uses[i] == 0

    nodes = set(df['from']).union(set(df['to']))
    for node in nodes:
        in_flow = lpSum(uses[i] for i in range(len(df)) if df.loc[i, 'to'] == node)
        out_flow = lpSum(uses[i] for i in range(len(df)) if df.loc[i, 'from'] == node)
        if node == start:
            prob += (out_flow - in_flow) == 1
        elif node == end:
            prob += (in_flow - out_flow) == 1
        else:
            prob += (in_flow - out_flow) == 0

    prob.solve()

    if LpStatus[prob.status] == "Optimal":
        result = df.copy()
        result['use'] = [int(uses[i].value()) for i in range(len(df))]
        total_distance = sum(result.loc[i, 'distance (m)'] for i in range(len(df)) if result.loc[i, 'use'] == 1)
        return result[result['use'] == 1], total_distance
    else:
        return None, None

# --- Streamlit 앱 ---
st.title("📝 교내 최적 길 찾기 + 지도 시각화")

# Description ↔ node 매핑
node_dict = dict(zip(nodes_df["Description"], nodes_df["node"]))
descriptions = sorted(nodes_df["Description"].tolist())

# 사용자 입력
start_desc = st.selectbox("출발 지점", descriptions)
end_desc = st.selectbox("도착 지점", descriptions)
start = node_dict[start_desc]
end = node_dict[end_desc]
max_angle = st.number_input("최대 각도 (단위: 도)", value=1000)

# 상태 저장
if "clicked" not in st.session_state:
    st.session_state.clicked = False

if st.button("탐색 시작"):
    st.session_state.clicked = True

if st.session_state.clicked:
    result_df, total_dist = solve_path_lp(edges_df, int(start), int(end), max_angle)

    if result_df is not None:
        st.success(f"총 거리: {total_dist} m")
        st.dataframe(result_df[['from', 'to', 'distance (m)', 'angle']])

        m = folium.Map(location=[nodes_df['lat'].mean(), nodes_df['lon'].mean()], zoom_start=17)

        for _, row in result_df.iterrows():
            from_node = row['from']
            to_node = row['to']

            from_match = nodes_df[nodes_df['node'] == from_node]
            to_match = nodes_df[nodes_df['node'] == to_node]

            if from_match.empty or to_match.empty:
                continue

            latlon_from = from_match[['lat', 'lon']].values[0]
            latlon_to = to_match[['lat', 'lon']].values[0]

            folium.PolyLine([latlon_from, latlon_to], tooltip=f"{from_node} ➔ {to_node}", color="blue", weight=5).add_to(m)
            folium.CircleMarker(latlon_from, radius=5, color='green', fill=True).add_to(m)
            folium.CircleMarker(latlon_to, radius=5, color='red', fill=True).add_to(m)

        st.subheader("📍 최적 경로 지도")
        st_folium(m, width=800, height=600)
    else:
        st.error("해당 조건에 맞는 경로가 없습니다.")
