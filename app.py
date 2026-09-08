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

import drivers
import layer2_rolling_corr as l2
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

st.title("채권·금리 매크로 대시보드")
st.caption("교과서 이론이 지금도 맞는지 데이터로 검증하고, 안 맞으면 왜 안 맞는지 설명하는 개인 매크로 학습 도구")

tab1, tab2 = st.tabs(["📌 2s10s 플래그십 분석", "📊 요인별 이론-실증 카드"])

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

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("이론")
        st.write(
            "장단기 금리차가 역전(마이너스)되면 시장이 향후 경기 둔화·침체를 예상한다는 "
            "신호로 해석됩니다. 실제로 1950년대 이후 미국의 거의 모든 공식 침체가 이 "
            "역전 뒤 6~24개월 사이에 뒤따라왔습니다."
        )
        st.subheader("괴리 (교과서와 다르게 흘러간 지점)")
        st.write(
            "2022년 7월부터 2024년 말까지 27개월간(역대 최장) 역전이 지속됐음에도 "
            "예상됐던 침체가 제때 오지 않았습니다. 코로나 이후 초과저축, 노동시장의 "
            "구조적 타이트함, 자연이자율 추정치 변화 등이 원인으로 거론됩니다. 최근 "
            "스프레드 정상화도 회복 신호가 아니라, 재정적자·국채발행 증가로 인한 "
            "텀프리미엄 상승('베어 스티프닝')이라는 다른 이유 때문이라는 해석이 있습니다."
        )
    with col2:
        st.subheader("역전 → 침체 시차 (실증 데이터)")
        lag_table = build_lag_table(inversion_episodes, recession_episodes)
        st.dataframe(lag_table, use_container_width=True, hide_index=True)

# ===== 탭 2 : 요인별 이론-실증 카드 =====
with tab2:
    driver_names = {d["name"]: d["key"] for d in drivers.DRIVERS}
    chosen_name = st.selectbox("살펴볼 요인을 선택하세요", list(driver_names.keys()))
    driver = drivers.get_driver(driver_names[chosen_name])

    st.subheader("이론")
    st.write(driver["theory_text"])
    st.caption(f"데이터 출처: {driver['source_note']}")

    if driver["fred_ticker"] is None:
        st.info("이 요인은 아직 자동 데이터 수집이 구현되지 않았습니다 (별도 조사 필요 항목으로 표시됨).")
    else:
        series, series_is_demo = get_series(driver["fred_ticker"])
        yield10, yield_is_demo = get_series("DGS10")
        is_demo = series_is_demo or yield_is_demo

        if is_demo:
            st.warning(
                "⚠️ 지금 보고 있는 건 실제 데이터가 아니라 화면 구조 확인용 데모(합성) 데이터입니다.",
                icon="⚠️",
            )

        corr = l2.rolling_correlation(series, yield10, window_days=252)
        fig2 = l2.build_rolling_corr_chart(driver, corr)
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("괴리 (이론과 어긋난 구간)")
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
