"""
2s10s (10Y-2Y 국채금리 스프레드) 이론-실증 분석 스크립트
====================================================

무엇을 하는가
------------
1. FRED(세인트루이스 연은)에서 아래 공식 데이터를 가져온다.
   - T10Y2Y : 10년물-2년물 국채금리 스프레드 (일별, FRED가 이미 계산해서 제공)
   - USREC  : 미국 공식 경기침체 여부 더미 (월별, NBER 기준, 0=평시/1=침체)
2. 스프레드가 마이너스(역전)인 구간을 자동으로 탐지한다.
3. 각 역전 구간의 시작일부터, 그 이후 처음 시작되는 공식 침체까지 몇 개월
   걸렸는지 계산해서 "역전 -> 침체 시차 표"를 만든다. (교과서 이론 검증)
4. 스프레드 시계열 그래프를 그리고, 역전 구간(빨강)과 실제 침체 구간(회색 음영)을
   겹쳐서 보여준다.

실행 전 꼭 확인할 것
-------------------
이 스크립트는 인터넷에서 fred.stlouisfed.org 에 접속해야 동작한다.
현재 이 스크립트를 준비한 클라우드 작업환경은 보안 정책상 외부 네트워크
접속이 막혀 있어서(패키지 설치 사이트만 허용), 여기서는 직접 실행해서
데이터를 받아올 수 없었다. 인터넷이 열려 있는 인욱님의 개인 컴퓨터나
Google Colab 같은 환경에서 실행하면 바로 동작한다.

필요한 패키지: pip install pandas_datareader matplotlib pandas
"""

import datetime as dt

import glob

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import pandas_datareader.data as web

# 한글 라벨이 깨지지 않도록 CJK 폰트를 등록한다.
# (Noto Sans CJK/나눔고딕이 없는 환경이면 자동으로 기본 폰트로 대체되어,
#  한글 대신 빈 네모(글리프 누락)로만 보일 수 있다 - 그럴 땐 아래 폰트 후보군을
#  시스템에 맞게 설치하거나 라벨을 영문으로 바꿔서 실행하면 된다.)
_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK (리눅스에 흔함)
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",          # 나눔고딕
]
_font_family = "sans-serif"
for _path in _FONT_CANDIDATES:
    for _match in glob.glob(_path):
        fm.fontManager.addfont(_match)
        _font_family = fm.FontProperties(fname=_match).get_name()
        break
    if _font_family != "sans-serif":
        break

plt.rcParams["font.family"] = [_font_family, "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ---- dataviz 스킬 기준 색상 (검증 완료: blue #2a78d6 <-> red #e34948) ----
COLOR_NORMAL = "#2a78d6"      # 스프레드 양수(정상) 구간
COLOR_INVERTED = "#e34948"    # 스프레드 음수(역전) 구간
COLOR_RECESSION = "#9a9a95"   # 공식 침체 구간 음영 (중립 회색, FRED 관례와 동일)
COLOR_ZERO_LINE = "#52514e"   # 기준선(0%)


def fetch_data(start=dt.datetime(1976, 1, 1)):
    """FRED에서 2s10s 스프레드와 공식 침체 더미를 가져온다."""
    spread = web.DataReader("T10Y2Y", "fred", start)["T10Y2Y"].dropna()
    recession = web.DataReader("USREC", "fred", start)["USREC"]
    # 월별 데이터를 일별로 늘려서(forward-fill) 스프레드와 같은 축에서 다루기 쉽게 함
    recession_daily = recession.reindex(
        pd.date_range(recession.index.min(), recession.index.max(), freq="D"),
        method="ffill",
    )
    return spread, recession_daily


def find_episodes(binary_series):
    """0/1(혹은 True/False) 시계열에서 연속으로 1인 구간들의 (시작일, 종료일) 리스트를 뽑는다."""
    s = binary_series.fillna(0).astype(int)
    episodes = []
    in_episode = False
    start = None
    for date, value in s.items():
        if value == 1 and not in_episode:
            in_episode = True
            start = date
        elif value == 0 and in_episode:
            in_episode = False
            episodes.append((start, prev_date))
        prev_date = date
    if in_episode:
        episodes.append((start, s.index[-1]))
    return episodes


def build_lag_table(inversion_episodes, recession_episodes):
    """각 역전 구간 시작일 이후, 처음 시작되는 침체까지의 개월 수를 계산한다."""
    rows = []
    recession_starts = [start for start, _ in recession_episodes]
    for inv_start, inv_end in inversion_episodes:
        duration_months = round((inv_end - inv_start).days / 30.44, 1)
        next_recessions = [r for r in recession_starts if r > inv_start]
        if next_recessions:
            next_rec = min(next_recessions)
            lag_months = round((next_rec - inv_start).days / 30.44, 1)
            note = ""
        else:
            next_rec = None
            lag_months = None
            note = "이후 아직 공식 침체 없음 (관찰 시점 기준)"
        rows.append(
            {
                "역전 시작일": inv_start.date(),
                "역전 종료일": inv_end.date(),
                "역전 지속(개월)": duration_months,
                "다음 침체 시작일": next_rec.date() if next_rec else None,
                "역전->침체 시차(개월)": lag_months,
                "비고": note,
            }
        )
    return pd.DataFrame(rows)


def plot_spread(spread, recession_daily, inversion_episodes, recession_episodes, out_path):
    fig, ax = plt.subplots(figsize=(13, 6), dpi=150)

    # 1) 침체 구간 음영 (중립 회색, 스프레드 색상과 겹치지 않는 별도 인코딩)
    for start, end in recession_episodes:
        ax.axvspan(start, end, color=COLOR_RECESSION, alpha=0.25, lw=0, zorder=0,
                   label="_nolegend_")

    # 2) 스프레드 라인: 양수/음수에 따라 diverging 색상 적용
    ax.plot(spread.index, spread.values, color=COLOR_ZERO_LINE, lw=0.6, alpha=0.4, zorder=1)
    ax.fill_between(spread.index, spread.values, 0,
                     where=(spread.values >= 0), color=COLOR_NORMAL, alpha=0.85,
                     interpolate=True, lw=0, zorder=2)
    ax.fill_between(spread.index, spread.values, 0,
                     where=(spread.values < 0), color=COLOR_INVERTED, alpha=0.85,
                     interpolate=True, lw=0, zorder=2)

    ax.axhline(0, color=COLOR_ZERO_LINE, lw=1)

    # 범례 (색상만으로 구분하지 않도록 텍스트 라벨 포함)
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=COLOR_NORMAL, label="정상 (10Y > 2Y)"),
        Patch(facecolor=COLOR_INVERTED, label="역전 (10Y < 2Y)"),
        Patch(facecolor=COLOR_RECESSION, alpha=0.25, label="공식 침체 구간 (NBER)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False)

    ax.set_title("미국 10Y-2Y 국채금리 스프레드와 공식 침체 구간", fontsize=14, pad=12)
    ax.set_ylabel("스프레드 (%p)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e4e0", lw=0.6, zorder=0)

    fig.tight_layout()
    fig.savefig(out_path)
    print(f"차트 저장 완료: {out_path}")


def main():
    spread, recession_daily = fetch_data()

    inversion_episodes = find_episodes(spread < 0)
    recession_episodes = find_episodes(recession_daily)

    lag_table = build_lag_table(inversion_episodes, recession_episodes)
    lag_table.to_csv("inversion_to_recession_lag.csv", index=False, encoding="utf-8-sig")
    print(lag_table.to_string(index=False))

    plot_spread(spread, recession_daily, inversion_episodes, recession_episodes,
                "2s10s_spread_chart.png")


if __name__ == "__main__":
    main()
