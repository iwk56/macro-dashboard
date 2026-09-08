"""
채권·금리 매크로 대시보드 (MVP)
================================

실행 방법: streamlit run app.py

인터넷이 열려 있는 환경(개인 컴퓨터, Colab 등)에서 실행하면 FRED 실제 데이터로
동작한다. 혹시 그 순간 FRED 접속이 안 되면(네트워크 문제, 방화벽 등) 자동으로
"데모 모드"(합성 데이터)로 전환되고 화면 상단에 크게 경고 배너가 뜬다 -
실제 데이터인지 데모 데이터인지 절대 헷갈리지 않도록 설계했다.
"""

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import cases
import drivers
import layer2_rolling_corr as l2
import news_engine
from fetch_and_analyze_2s10s import build_lag_table, find_episodes

st.set_page_config(page_title="채권·금리 매크로 대시보드", layout="wide")

COLOR_NORMAL = "#2a78d6"
COLOR_INVERTED = "#e34948"
COLOR_RECESSION = "rgba(154,154,149,0.25)"


# ---------------------------------------------------------------------------
# 데이터 로딩 (실제 FRED 우선 시도, 실패 시 데모 데이터로 자동 전환)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="FRED에서 데이터를 가져오는 중...")
def load_fred_series(ticker: str, start: str = "1976-01-01") -> pd.Series | None:
    """FRED 시리즈 하나를 가져온다. 실패하면 None을 반환한다 (예외를 위로 던지지 않음)."""
    try:
        import pandas_datareader.data as web

        s = web.DataReader(ticker, "fred", start)[ticker].dropna()
        return s
    except Exception:
        return None


def make_demo_series(kind: str) -> pd.Series:
    """네트워크가 없을 때 화면 구조를 보여주기 위한 합성 데이터.
    실제 값이 아니며, 화면에 항상 '데모 데이터' 경고와 함께만 표시된다."""
    dates = pd.date_range("2000-01-01", dt.date.today(), freq="D")
    rng = np.random.default_rng(abs(hash(kind)) % (2**32))
    if kind == "T10Y2Y":
        base = 1.0 + 0.9 * np.sin(np.linspace(0, 14, len(dates)))
        noise = rng.normal(0, 0.08, len(dates))
        return pd.Series(base + noise, index=dates, name=kind)
    if kind == "USREC":
        s = pd.Series(0, index=dates, name=kind)
        for start, end in [("2001-03-01", "2001-11-01"), ("2007-12-01", "2009-06-01"),
                            ("2020-02-01", "2020-04-01")]:
            s.loc[start:end] = 1
        return s
    # 나머지 요인들은 임의보행 + 완만한 추세로 생성
    base = np.cumsum(rng.normal(0, 0.01, len(dates)))
    return pd.Series(base, index=dates, name=kind)


def get_series(ticker: str) -> tuple[pd.Series, bool]:
    """(시계열, is_demo) 튜플을 반환한다."""
    real = load_fred_series(ticker)
    if real is not None and len(real) > 30:
        return real, False
    return make_demo_series(ticker), True


# ---------------------------------------------------------------------------
# 화면 구성
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("채권·금리 매크로 대시보드")
    st.caption(
        "교과서 이론이 지금도 맞는지 데이터로 검증하고, "
        "안 맞으면 왜 안 맞는지 설명하는 개인 매크로 학습 도구입니다."
    )
    st.divider()
    st.markdown(
        "**보는 법**\n\n"
        "각 카드는 항상 3단 구조예요.\n\n"
        "📖 이론 → 📊 실증(데이터) → ⚠️ 괴리(왜 안 맞았나)"
    )
    st.divider()
    st.caption("데이터 출처: FRED (세인트루이스 연은)")

st.title("채권·금리 매크로 대시보드")

tab1, tab2, tab3, tab4 = st.tabs([
    "📌 2s10s 플래그십 분석",
    "📊 요인별 이론-실증 카드",
    "📰 뉴스 분석",
    "🗂️ 예시·기록",
])

# ===== 탭 1 : 2s10s 스프레드 =====
with tab1:
    spread, spread_is_demo = get_series("T10Y2Y")
    rec, rec_is_demo = get_series("USREC")
    is_demo = spread_is_demo or rec_is_demo

    if is_demo:
        st.warning(
            "⚠️ 지금 보고 있는 건 **실제 데이터가 아니라 화면 구조 확인용 데모(합성) 데이터**입니다. "
            "FRED 접속이 가능한 환경에서 실행하면 실제 데이터로 자동 교체됩니다.",
            icon="⚠️",
        )

    rec_daily = rec.reindex(pd.date_range(rec.index.min(), rec.index.max(), freq="D"), method="ffill")
    inversion_episodes = find_episodes(spread < 0)
    recession_episodes = find_episodes(rec_daily)

    latest_val = float(spread.iloc[-1])
    latest_date = spread.index[-1]
    is_inverted_now = latest_val < 0
    cur_episode_start = None
    for start, end in (inversion_episodes if is_inverted_now else []):
        if end >= latest_date:
            cur_episode_start = start
    days_in_regime = (latest_date - cur_episode_start).days if cur_episode_start else None

    m1, m2, m3 = st.columns(3)
    m1.metric("현재 스프레드 (2s10s)", f"{latest_val:+.2f}%p", help=f"기준일: {latest_date.date()}")
    m2.metric("현재 상태", "🔴 역전" if is_inverted_now else "🔵 정상")
    m3.metric(
        "역전 지속 기간" if is_inverted_now else "정상 전환 후 경과",
        f"{days_in_regime}일" if days_in_regime else "—",
    )

    st.divider()

    fig = go.Figure()
    for start, end in recession_episodes:
        fig.add_vrect(x0=start, x1=end, fillcolor=COLOR_RECESSION, line_width=0)
    fig.add_hline(y=0, line_color="#52514e", line_width=1)
    fig.add_trace(go.Scatter(
        x=spread.index, y=spread.where(spread >= 0), fill="tozeroy",
        line=dict(color=COLOR_NORMAL, width=1), name="정상 (10Y > 2Y)",
        hovertemplate="%{x|%Y-%m-%d}<br>스프레드 %{y:.2f}%p<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=spread.index, y=spread.where(spread < 0), fill="tozeroy",
        line=dict(color=COLOR_INVERTED, width=1), name="역전 (10Y < 2Y)",
        hovertemplate="%{x|%Y-%m-%d}<br>스프레드 %{y:.2f}%p<extra></extra>",
    ))
    fig.update_layout(
        title="미국 10Y-2Y 국채금리 스프레드와 공식 침체 구간(회색)",
        yaxis_title="스프레드 (%p)", template="plotly_white",
        hovermode="x unified", legend=dict(orientation="h", y=1.05),
        margin=dict(t=60, l=60, r=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 📖 이론")
        st.write(
            "장단기 금리차가 역전(마이너스)되면 시장이 향후 경기 둔화·침체를 예상한다는 "
            "신호로 해석됩니다. 실제로 1950년대 이후 미국의 거의 모든 공식 침체가 이 "
            "역전 뒤 6~24개월 사이에 뒤따라왔습니다."
        )

    with st.container(border=True):
        st.markdown("#### 📊 역전 → 침체 시차 (실증 데이터)")
        lag_table = build_lag_table(inversion_episodes, recession_episodes)
        st.dataframe(lag_table, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("#### ⚠️ 괴리 (교과서와 다르게 흘러간 지점)")
        st.write(
            "2022년 7월부터 2024년 말까지 27개월간(역대 최장) 역전이 지속됐음에도 "
            "예상됐던 침체가 제때 오지 않았습니다. 코로나 이후 초과저축, 노동시장의 "
            "구조적 타이트함, 자연이자율 추정치 변화 등이 원인으로 거론됩니다. 최근 "
            "스프레드 정상화도 회복 신호가 아니라, 재정적자·국채발행 증가로 인한 "
            "텀프리미엄 상승('베어 스티프닝')이라는 다른 이유 때문이라는 해석이 있습니다."
        )

# ===== 탭 2 : 요인별 이론-실증 카드 =====
DRIVER_ICONS = {
    "fed_funds": "🏦",
    "breakeven_inflation": "🔥",
    "real_yield": "💰",
    "gov_debt": "📄",
    "safe_haven": "🛡️",
    "foreign_demand": "🌏",
}

def render_driver_card(driver: dict) -> None:
    """요인 하나에 대한 이론-실증-괴리 카드를 화면에 그린다."""
    with st.container(border=True):
        st.markdown("#### 📖 이론")
        st.write(driver["theory_text"])
        st.caption(f"데이터 출처: {driver['source_note']}")

    if driver["fred_ticker"] is None:
        st.info("이 요인은 아직 자동 데이터 수집이 구현되지 않았습니다 (별도 조사 필요 항목으로 표시됨).")
        return

    series, series_is_demo = get_series(driver["fred_ticker"])
    yield10, yield_is_demo = get_series("DGS10")
    is_demo = series_is_demo or yield_is_demo

    if is_demo:
        st.warning(
            "⚠️ 지금 보고 있는 건 실제 데이터가 아니라 화면 구조 확인용 데모(합성) 데이터입니다.",
            icon="⚠️",
        )

    corr = l2.rolling_correlation(series, yield10, window_days=252)

    latest_corr = float(corr.iloc[-1])
    matches_now = l2.match_flags(corr, driver["expected_sign"]).iloc[-1]
    mc1, mc2 = st.columns(2)
    mc1.metric("현재 1년 롤링 상관계수", f"{latest_corr:+.2f}")
    mc2.metric("현재 이론과의 정합성", "✅ 일치" if matches_now else "❌ 어긋남")

    st.divider()

    fig2 = l2.build_rolling_corr_chart(driver, corr)
    st.plotly_chart(fig2, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### ⚠️ 괴리 (이론과 어긋난 구간)")
        mismatch_eps = l2.summarize_deviation_periods(corr, driver["expected_sign"], min_days=60)
        if mismatch_eps:
            st.write("2개월 이상 이론과 어긋난 것으로 감지된 구간:")
            st.table(pd.DataFrame(
                [(s.date(), e.date()) for s, e in mismatch_eps],
                columns=["시작일", "종료일"],
            ))
        else:
            st.write("2개월 이상 지속된 뚜렷한 괴리 구간이 감지되지 않았습니다.")

        if driver["deviation_note"]:
            st.write(f"**조사된 배경 설명:** {driver['deviation_note']}")
        else:
            st.caption("이 요인의 괴리 원인은 아직 직접 리서치가 채워지지 않았습니다 (TODO).")


with tab2:
    st.caption("채권·금리에 영향을 주는 6개 요인의 이론-실증-괴리 카드입니다. (분석 자산은 추후 확장 예정)")
    show_all = st.toggle("전체 요인 한 번에 보기 (스크롤)", value=False)

    driver_labels = {
        f"{DRIVER_ICONS.get(d['key'], '📊')} {d['name']}": d["key"] for d in drivers.DRIVERS
    }

    if show_all:
        for label, key in driver_labels.items():
            st.markdown(f"### {label}")
            render_driver_card(drivers.get_driver(key))
            st.divider()
    else:
        chosen_label = st.selectbox("살펴볼 요인을 선택하세요", list(driver_labels.keys()))
        render_driver_card(drivers.get_driver(driver_labels[chosen_label]))

# ===== 탭 3 : 뉴스 분석 (레이어 1) =====
with tab3:
    st.caption(
        "Claude API의 웹 검색 기능으로 최근 뉴스를 찾아, 선택한 요인이 왜 최근 "
        "이렇게 움직였는지 요약합니다. 이 기능만 유일하게 비용이 드는 부분입니다."
    )

    stored_key = news_engine.get_stored_api_key()

    if not stored_key:
        with st.container(border=True):
            st.markdown("#### 🔑 Anthropic API 키가 필요해요")
            st.write(
                "1. [console.anthropic.com](https://console.anthropic.com) 에서 계정을 만들고 "
                "'Get API Keys' 메뉴에서 키를 발급받으세요 (`sk-ant-`로 시작).\n\n"
                "2. Streamlit Cloud에 배포한 앱이라면, 앱 관리 화면(Manage app) → "
                "**Settings → Secrets** 에 아래처럼 등록하면 이 입력창 없이 자동으로 "
                "사용됩니다:\n\n"
                "```\nANTHROPIC_API_KEY = \"sk-ant-여기에-실제-키\"\n```\n\n"
                "3. 아니면 아래에 임시로 입력해서 지금 세션에서만 테스트해볼 수도 있어요 "
                "(새로고침하면 사라지고, 어디에도 저장되지 않습니다)."
            )
            typed_key = st.text_input("Anthropic API 키 (임시, 이번 세션에만 사용)", type="password")
            if typed_key:
                st.session_state["anthropic_api_key_input"] = typed_key
                st.rerun()
    else:
        model_label = st.selectbox("사용할 모델", list(news_engine.MODEL_OPTIONS.keys()))
        model_id = news_engine.MODEL_OPTIONS[model_label]

        topic_labels = {d["name"]: d["name"] for d in drivers.DRIVERS}
        topic_labels["미국 장단기 금리차(2s10s)"] = "미국 장단기 금리차(2s10s)"
        topic = st.selectbox("어떤 주제의 최근 뉴스를 찾을까요?", list(topic_labels.keys()))

        if st.button("🔍 최근 뉴스 요약하기", type="primary"):
            with st.spinner("웹 검색 중... (몇 초~몇십 초 걸릴 수 있어요)"):
                try:
                    summary, sources = news_engine.summarize_recent_news(
                        topic=topic, model=model_id, api_key=stored_key
                    )
                except Exception as e:
                    st.error(
                        f"요약을 가져오지 못했습니다: {e}\n\n"
                        "API 키가 올바른지, 선택한 모델이 웹 검색 기능을 지원하는지 "
                        "확인해보세요 (지원하지 않으면 다른 모델로 바꿔서 다시 시도)."
                    )
                else:
                    with st.container(border=True):
                        st.markdown(f"#### 📰 {topic} — 최근 동향 요약")
                        st.write(summary)
                    if sources:
                        st.caption("참고한 기사:")
                        for s in sources:
                            st.markdown(f"- [{s['title']}]({s['url']})")

# ===== 탭 4 : 예시·기록 =====
with tab4:
    sub1, sub2 = st.tabs(["📚 과거 사례 모음", "📝 내 기록"])

    with sub1:
        st.caption("채권·금리 외에도 '교과서와 현실이 어긋난' 유명한 매크로 사례들입니다.")
        for case in cases.CASES:
            with st.expander(f"{case['title']} ({case['period']})"):
                st.markdown("**📖 이론**")
                st.write(case["theory_text"])
                st.markdown("**📊 실증**")
                st.write(case["evidence_text"])
                st.markdown("**⚠️ 괴리**")
                st.write(case["deviation_note"])
                st.caption(f"출처: {case['source_note']}")

    with sub2:
        st.caption(
            "직접 공부하면서 든 생각이나 메모를 남기는 공간입니다. "
            "Streamlit Cloud는 새로고침하면 화면이 초기화되므로, 아래 다운로드 "
            "버튼으로 파일(.md)로 저장해뒀다가, 다음에 다시 올려서 이어 쓰면 됩니다."
        )

        uploaded = st.file_uploader("이전에 저장해둔 기록 파일 불러오기 (.md 또는 .txt)", type=["md", "txt"])
        default_text = ""
        if uploaded is not None:
            default_text = uploaded.read().decode("utf-8")

        note_text = st.text_area(
            "기록 작성",
            value=st.session_state.get("note_text", default_text),
            height=300,
            placeholder="예: 2026-09-08 - 2s10s가 왜 다시 벌어지고 있는지 뉴스 탭에서 확인해보니...",
        )
        st.session_state["note_text"] = note_text

        st.download_button(
            "💾 현재 기록 .md 파일로 저장",
            data=note_text.encode("utf-8"),
            file_name=f"macro_notes_{dt.date.today().isoformat()}.md",
            mime="text/markdown",
        )
