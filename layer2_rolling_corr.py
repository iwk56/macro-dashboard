"""
레이어 2 : 과거 학습 / 감지
==========================

"교과서 이론이 지금도 맞는지"를 롤링(이동) 상관관계로 감지하는 범용 함수.
이 파일은 특정 요인에 종속되지 않는다 - drivers.py 에 등록된 어떤 요인이든
이 함수 하나로 이론-실증 비교 차트를 만들 수 있다.

주의: 이 모듈은 "언제, 얼마나 어긋났는지"만 감지한다. "왜 어긋났는지"는
drivers.py 의 deviation_note(직접 리서치) 나, 레이어 1의 뉴스 요약 엔진이
채워준다 - 이 셋이 합쳐져야 하나의 "이론-실증-괴리" 카드가 완성된다.
"""

import pandas as pd
import plotly.graph_objects as go

# dataviz 스킬 검증 완료 색상 (blue #2a78d6 <-> red #e34948, 중립 gray #f0efec)
COLOR_MATCH = "#2a78d6"      # 실제 상관관계가 이론(예상 부호)과 일치하는 구간
COLOR_MISMATCH = "#e34948"   # 이론과 어긋나는 구간
COLOR_ZERO = "#9a9a95"


def rolling_correlation(series_a: pd.Series, series_b: pd.Series, window_days: int = 252) -> pd.Series:
    """두 시계열을 공통 일별 인덱스로 맞추고 롤링 피어슨 상관계수를 계산한다.

    window_days=252는 거래일 기준 약 1년.
    """
    df = pd.concat(
        [series_a.rename("a"), series_b.rename("b")], axis=1
    ).sort_index()
    # 서로 다른 발표 주기(예: 월별 vs 일별)를 다룰 수 있도록 앞선 값으로 채움
    df = df.ffill().dropna()
    corr = df["a"].rolling(window_days, min_periods=int(window_days * 0.6)).corr(df["b"])
    return corr.dropna()


def match_flags(corr_series: pd.Series, expected_sign: int) -> pd.Series:
    """실제 상관계수의 부호가 이론이 예상한 부호와 맞는지를 True/False로 반환."""
    if expected_sign >= 0:
        return corr_series >= 0
    return corr_series < 0


def build_rolling_corr_chart(driver: dict, corr_series: pd.Series) -> go.Figure:
    """이론-실증 비교를 위한 인터랙티브(hover 지원) 롤링 상관관계 차트."""
    matches = match_flags(corr_series, driver["expected_sign"])

    fig = go.Figure()

    # 기준선(0)
    fig.add_hline(y=0, line_color=COLOR_ZERO, line_width=1)

    # 일치/불일치 구간을 색으로 구분한 두 개의 트레이스 (겹치지 않게 NaN으로 분리)
    match_y = corr_series.where(matches)
    mismatch_y = corr_series.where(~matches)

    fig.add_trace(
        go.Scatter(
            x=corr_series.index, y=match_y, mode="lines",
            line=dict(color=COLOR_MATCH, width=2),
            name="이론과 일치",
            hovertemplate="%{x|%Y-%m-%d}<br>상관계수 %{y:.2f} (이론과 일치)<extra></extra>",
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=corr_series.index, y=mismatch_y, mode="lines",
            line=dict(color=COLOR_MISMATCH, width=2),
            name="이론과 어긋남",
            hovertemplate="%{x|%Y-%m-%d}<br>상관계수 %{y:.2f} (이론과 어긋남)<extra></extra>",
            connectgaps=False,
        )
    )

    sign_txt = "양(+)" if driver["expected_sign"] > 0 else "음(-)"
    fig.update_layout(
        title=f"{driver['name']} — 10년물 금리와의 1년 롤링 상관관계 (이론상 예상 부호: {sign_txt})",
        yaxis_title="롤링 상관계수",
        yaxis_range=[-1, 1],
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        margin=dict(t=70, l=60, r=30, b=40),
    )
    return fig


def summarize_deviation_periods(corr_series: pd.Series, expected_sign: int, min_days: int = 60):
    """이론과 어긋난 구간(불일치)이 min_days 이상 지속된 시기만 골라 요약한다."""
    matches = match_flags(corr_series, expected_sign)
    mismatch = ~matches
    episodes = []
    in_ep, start = False, None
    prev_date = None
    for date, is_mismatch in mismatch.items():
        if is_mismatch and not in_ep:
            in_ep, start = True, date
        elif not is_mismatch and in_ep:
            in_ep = False
            if (prev_date - start).days >= min_days:
                episodes.append((start, prev_date))
        prev_date = date
    if in_ep and prev_date is not None and (prev_date - start).days >= min_days:
        episodes.append((start, prev_date))
    return episodes
