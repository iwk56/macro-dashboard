"""
세계 이해 대시보드 — 앱 전체 진입점 (멀티페이지 셸)
======================================================

실행 방법: streamlit run app.py

이 파일은 이제 화면을 직접 그리지 않는다. st.navigation()으로 전체 로드맵의
"겉 포장지"를 구성하고, 각 페이지의 실제 내용은 별도 모듈에 위임한다.

- 채권·금리(bond_module.py): 유일하게 실제 데이터/분석 로직이 있는 모듈.
  원래 이 파일(app.py) 전체였던 내용을 그대로 옮긴 것으로, 동작은 100% 동일하다.
- 홈(home.py): 전체 로드맵을 카드 형태로 보여주는 첫 화면.
- 나머지(stubs.py): 아직 비어있는 자산 모듈/공용 기능의 placeholder 페이지.
  나중에 이 파일들의 함수 본문만 채우면 앱 구조를 바꾸지 않고도 기능이 늘어난다.
"""

import streamlit as st

import bond_module
import home
import stubs

st.set_page_config(page_title="세계 이해 대시보드", layout="wide", page_icon="🌍")

home_page = st.Page(home.render, title="홈", icon="🏠", url_path="home", default=True)

bond_page = st.Page(bond_module.render, title="채권·금리", icon="📈", url_path="bond")
gold_page = st.Page(stubs.gold_page, title="금·귀금속", icon="🪙", url_path="gold")
commodities_page = st.Page(stubs.commodities_page, title="원자재", icon="🛢️", url_path="commodities")
fx_page = st.Page(stubs.fx_page, title="환율", icon="💱", url_path="fx")

daily_summary_page = st.Page(stubs.daily_summary_page, title="오늘의 요약", icon="🗞️", url_path="daily-summary")
timeline_page = st.Page(stubs.timeline_page, title="연표형 스토리텔링", icon="🕰️", url_path="timeline")
pattern_page = st.Page(stubs.pattern_matching_page, title="패턴 매칭", icon="🔍", url_path="pattern-matching")
prediction_page = st.Page(stubs.prediction_tracker_page, title="내 예측 vs 실제", icon="🎯", url_path="prediction-tracker")
glossary_page = st.Page(stubs.glossary_page, title="누적 용어사전", icon="📖", url_path="glossary")

pages = {
    "": [home_page],
    "📊 자산 모듈": [bond_page, gold_page, commodities_page, fx_page],
    "🧩 공용 기능": [daily_summary_page, timeline_page, pattern_page, prediction_page, glossary_page],
}

# 홈 화면의 카드에서 st.page_link로 각 페이지에 바로 이동할 수 있도록 주입.
home.NAV_PAGES = {
    "bond": bond_page,
    "gold": gold_page,
    "commodities": commodities_page,
    "fx": fx_page,
    "daily_summary": daily_summary_page,
    "timeline": timeline_page,
    "pattern": pattern_page,
    "prediction": prediction_page,
    "glossary": glossary_page,
}

pg = st.navigation(pages)
pg.run()
