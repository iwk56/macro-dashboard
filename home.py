"""
홈 페이지 — 전체 로드맵을 한눈에 보여주는 첫 화면
====================================================

이전에 만든 "세계 이해 지도" HTML 아티팩트의 카드 구조를, 실제로 클릭해서
이동할 수 있는 진짜 앱 내비게이션으로 옮긴 페이지다. 채권·금리만 실제로
동작하고, 나머지는 stubs.py의 placeholder 페이지로 연결된다.

app.py가 st.navigation()으로 만든 각 st.Page 객체를 NAV_PAGES 딕셔너리에
담아 이 모듈에 주입해준다 (app.py에서 `home.NAV_PAGES = {...}` 로 설정).
그래야 st.page_link()가 실제 페이지 객체를 참조해서 사이드바 없이도
카드 클릭만으로 이동할 수 있다.
"""

from __future__ import annotations

import streamlit as st

# app.py가 실행 시점에 채워준다. (키: "bond", "gold", "commodities", "fx",
# "daily_summary", "timeline", "pattern", "prediction", "glossary")
NAV_PAGES: dict = {}

STATUS_BADGE = {
    "done": "✅ 완료",
    "progress": "🔨 진행 중",
    "idea": "💡 아이디어",
}


def _asset_card(col, icon: str, title: str, status: str, desc: str, page_key: str) -> None:
    with col:
        with st.container(border=True):
            st.markdown(f"### {icon} {title}")
            st.caption(STATUS_BADGE.get(status, status))
            st.write(desc)
            page = NAV_PAGES.get(page_key)
            if page is not None:
                st.page_link(page, label="열기", icon="➡️")


def _feature_card(col, icon: str, title: str, status: str, desc: str, page_key: str | None, note: str | None = None) -> None:
    with col:
        with st.container(border=True):
            st.markdown(f"##### {icon} {title}")
            st.caption(STATUS_BADGE.get(status, status))
            st.write(desc)
            if note:
                st.caption(note)
            if page_key:
                page = NAV_PAGES.get(page_key)
                if page is not None:
                    st.page_link(page, label="열기", icon="➡️")


def render() -> None:
    st.title("🌍 세계 이해 대시보드")
    st.caption(
        "교과서 이론이 지금도 실제 데이터와 맞는지 확인하고, 안 맞으면 왜 안 맞는지 "
        "설명해가며 세상이 돌아가는 원리를 익히는 개인 학습 도구입니다. "
        "지금은 채권·금리 하나만 실제로 채워져 있고, 나머지는 앞으로 하나씩 채워나갈 "
        "자리를 미리 만들어둔 '겉 포장지' 상태예요."
    )

    st.divider()

    st.markdown("#### 🧬 레이어 아키텍처")
    st.caption("모든 자산 모듈이 공유하는 4단계 파이프라인입니다.")
    l1, l2, l3, l4 = st.columns(4)
    with l1:
        st.markdown("**1. 데이터 수집**")
        st.caption("FRED 등 공개 데이터를 실시간으로 가져오거나, 실패 시 데모 데이터로 전환")
    with l2:
        st.markdown("**2. 이론 ↔ 실증 매칭**")
        st.caption("교과서 이론이 실제 상관관계와 맞는지 롤링 윈도우로 검증 (Layer 2)")
    with l3:
        st.markdown("**3. 향후 이벤트**")
        st.caption("FOMC·CPI 등 다가올 이벤트를 D-day로 추적 (Layer 3, API 불필요)")
    with l4:
        st.markdown("**4. 시나리오/경보**")
        st.caption("과거 패턴 + 다가올 이벤트를 엮어 시나리오 제시 (Layer 4, 예정)")

    st.divider()

    st.markdown("#### 📊 자산 모듈")
    st.caption("같은 이론-실증-괴리 구조를 여러 자산에 적용해나가는 것이 목표입니다.")
    a1, a2, a3, a4 = st.columns(4)
    _asset_card(a1, "📈", "채권·금리", "done",
                "2s10s 스프레드, 6개 요인 카드, 뉴스 분석, 향후 이벤트까지 실제로 동작하는 유일한 모듈이에요.",
                "bond")
    _asset_card(a2, "🪙", "금·귀금속", "idea",
                "실질금리·안전자산 수요로 금값을 이해하는 모듈이 될 예정이에요.",
                "gold")
    _asset_card(a3, "🛢️", "원자재", "idea",
                "원유·구리 등 경기 민감 원자재를 성장·인플레 기대와 연결할 예정이에요.",
                "commodities")
    _asset_card(a4, "💱", "환율", "idea",
                "금리차·수급으로 원/달러 등 환율을 이해하는 모듈이 될 예정이에요.",
                "fx")

    st.divider()

    st.markdown("#### 🧩 공용 기능")
    st.caption("특정 자산에 묶이지 않고, 모든 모듈을 가로질러 쓰이는 기능들이에요.")

    f1, f2, f3, f4 = st.columns(4)
    _feature_card(f1, "🗞️", "오늘의 요약", "idea",
                  "오늘 하루 흩어진 소식을 한 화면에 모아 보여주는 홈 피드예요.",
                  "daily_summary")
    _feature_card(f2, "🗓️", "향후 이벤트 캘린더", "done",
                  "FOMC·CPI·고용보고서·GDP 일정을 D-day로 추적해요.",
                  "bond", note="지금은 채권·금리 페이지 안 탭으로 들어있어요.")
    _feature_card(f3, "📰", "뉴스 분석", "done",
                  "기사를 붙여넣으면 요약·용어정리·영향·시나리오까지 정리해줘요.",
                  "bond", note="지금은 채권·금리 페이지 안 탭으로 들어있어요.")
    _feature_card(f4, "🗂️", "기록 저장소", "progress",
                  "분석 기록을 GitHub에 계속 쌓아두는 기능이에요.",
                  "bond", note="지금은 채권·금리 페이지 안에 있고, 저장 방식은 재설계를 고민 중이에요.")

    f5, f6, f7, f8 = st.columns(4)
    _feature_card(f5, "🕰️", "연표형 스토리텔링", "idea",
                  "과거 사례들을 시간순 연표로 풀어서 보여줘요.",
                  "timeline")
    _feature_card(f6, "🔍", "패턴 매칭", "idea",
                  "지금 상황과 가장 비슷한 과거 사례를 자동으로 찾아줘요.",
                  "pattern")
    _feature_card(f7, "🎯", "내 예측 vs 실제", "idea",
                  "내가 남긴 예측을 실제 결과와 나중에 비교해봐요.",
                  "prediction")
    _feature_card(f8, "📖", "누적 용어사전", "idea",
                  "뉴스 분석에서 나온 용어들이 자동으로 모여 쌓여요.",
                  "glossary")

    st.divider()
    st.caption(
        "이 화면은 계속 자라나는 지도예요 — 빈 카드가 하나씩 채워질 때마다 여기서 바로 "
        "링크가 열리도록 만들었어요."
    )
