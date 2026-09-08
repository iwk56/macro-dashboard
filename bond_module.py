"""
채권·금리 매크로 모듈
======================

전체 앱(app.py)의 "자산 모듈" 중 현재 유일하게 실제로 동작하는 모듈이다.
다른 모듈(금·귀금속/원자재/환율)이나 공용 기능(오늘의 요약 등)은 아직
껍데기(placeholder)만 있고, 이 모듈이 실제 데이터·분석 로직을 담고 있다.

원래는 app.py 전체가 이 내용이었지만, 여러 자산/기능을 담는 앱 전체 구조
(st.navigation 기반 멀티페이지)로 넓히면서 이 파일로 옮겼다. 동작은 이전과
100% 동일하고, render() 함수 하나로 감싸졌을 뿐이다.
"""

import datetime as dt
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import cases
import drivers
import event_calendar
import layer2_rolling_corr as l2
import news_engine
import notes_store
from fetch_and_analyze_2s10s import build_lag_table, find_episodes

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
# 요인별 이론-실증 카드
# ---------------------------------------------------------------------------

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


def anthropic_key_setup_block(key_suffix: str = "default") -> None:
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
        typed_key = st.text_input(
            "Anthropic API 키 (임시, 이번 세션에만 사용)", type="password",
            key=f"anthropic_key_typed_{key_suffix}",
        )
        if typed_key:
            st.session_state["anthropic_api_key_input"] = typed_key
            st.rerun()


def github_token_setup_block(key_suffix: str = "default") -> None:
    with st.container(border=True):
        st.markdown("#### 🔑 GitHub 토큰이 필요해요 (기록을 계속 쌓아두려면)")
        st.write(
            "분석 결과를 저장하면 새로고침해도 사라지지 않고 GitHub 저장소에 "
            "계속 쌓이도록, 쓰기 권한이 있는 개인 토큰이 하나 필요해요.\n\n"
            "1. GitHub 우측 상단 프로필 → **Settings** → 왼쪽 맨 아래 "
            "**Developer settings** → **Personal access tokens** → "
            "**Fine-grained tokens** → **Generate new token**\n\n"
            "2. Repository access: **Only select repositories** → "
            "`macro-dashboard` 선택\n\n"
            "3. Permissions → Repository permissions → **Contents** 를 "
            "**Read and write** 로 변경\n\n"
            "4. **Generate token** 클릭 → 생성된 토큰(`github_pat_...`)을 복사 "
            "(이 화면을 벗어나면 다시 볼 수 없으니 꼭 지금 복사)\n\n"
            "5. Streamlit Cloud 앱 관리 화면 → Settings → Secrets 에 추가:\n\n"
            "```\nGITHUB_TOKEN = \"github_pat_여기에-실제-토큰\"\n```"
        )
        typed_token = st.text_input(
            "GitHub 토큰 (임시, 이번 세션에만 사용)", type="password",
            key=f"github_token_typed_{key_suffix}",
        )
        if typed_token:
            st.session_state["github_token_input"] = typed_token
            st.rerun()


TOPIC_OPTIONS = [d["name"] for d in drivers.DRIVERS] + ["미국 장단기 금리차(2s10s)"]


# ---------------------------------------------------------------------------
# 화면 구성
# ---------------------------------------------------------------------------

def render() -> None:
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📌 2s10s 플래그십 분석",
        "📊 요인별 이론-실증 카드",
        "📰 뉴스 분석",
        "🗂️ 예시·기록",
        "🗓️ 향후 이벤트",
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
        news_sub1, news_sub2 = st.tabs(["🔍 최신 이슈 검색", "📋 기사 분석·저장"])

        stored_key = news_engine.get_stored_api_key()

        # ----- 3-1 : 주제를 고르면 웹 검색으로 최신 이슈 요약 -----
        with news_sub1:
            st.caption(
                "Claude API의 웹 검색 기능으로 최근 뉴스를 찾아, 선택한 요인이 왜 최근 "
                "이렇게 움직였는지 요약합니다."
            )
            if not stored_key:
                anthropic_key_setup_block(key_suffix="search")
            else:
                model_label = st.selectbox("사용할 모델", list(news_engine.MODEL_OPTIONS.keys()), key="search_model")
                model_id = news_engine.MODEL_OPTIONS[model_label]
                topic = st.selectbox("어떤 주제의 최근 뉴스를 찾을까요?", TOPIC_OPTIONS, key="search_topic")

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

        # ----- 3-2 : 기사를 직접 붙여넣으면 분석 + 기록으로 저장 -----
        with news_sub2:
            st.caption(
                "읽은 기사를 붙여넣으면 요약·용어정리·중요도·영향 분석·향후 시나리오까지 "
                "정리해줘요. 저장하면 GitHub 저장소에 계속 쌓여서, 다음에 다시 열어볼 수 있어요."
            )

            if not stored_key:
                anthropic_key_setup_block(key_suffix="article")
            else:
                gh_token, gh_repo = notes_store.get_config()

                article_title = st.text_input("제목 (비워두면 자동으로 붙여요)", key="article_title")
                article_text = st.text_area(
                    "기사 원문을 붙여넣으세요", height=220, key="article_text_input",
                    placeholder="여기에 기사 전문을 복사해서 붙여넣으세요...",
                )
                article_topic = st.selectbox("이 기사는 무엇과 관련 있나요?", TOPIC_OPTIONS, key="article_topic")
                use_search = st.checkbox("관련 최신 뉴스도 함께 검색해서 참고하기 (비용 조금 더 듦)", key="article_use_search")
                analyze_model_label = st.selectbox(
                    "사용할 모델", list(news_engine.MODEL_OPTIONS.keys()), key="article_model"
                )

                if st.button("🧠 분석하기", type="primary", disabled=not article_text.strip()):
                    with st.spinner("기사를 읽고 분석하는 중..."):
                        try:
                            result = news_engine.analyze_article(
                                article_text=article_text,
                                target_name=article_topic,
                                model=news_engine.MODEL_OPTIONS[analyze_model_label],
                                api_key=stored_key,
                                use_web_search=use_search,
                            )
                        except Exception as e:
                            st.error(f"분석에 실패했습니다: {e}")
                            result = None
                    if result is not None:
                        st.session_state["current_analysis"] = {
                            "title": article_title.strip() or (article_text.strip()[:40] + "..."),
                            "topic": article_topic,
                            "article_text": article_text,
                            **result,
                        }

                analysis = st.session_state.get("current_analysis")
                if analysis:
                    if analysis.get("_parse_error"):
                        st.warning("모델 응답을 구조화하지 못해 원문 그대로 보여드려요.")

                    with st.container(border=True):
                        st.markdown("#### 📖 요약")
                        st.write(analysis.get("summary", ""))

                    if analysis.get("terms"):
                        with st.container(border=True):
                            st.markdown("#### 📚 용어 정리")
                            for t in analysis["terms"]:
                                st.markdown(f"- **{t.get('term', '')}**: {t.get('definition', '')}")

                    with st.container(border=True):
                        st.markdown("#### 💡 왜 중요한가")
                        st.write(analysis.get("why_it_matters", ""))

                    with st.container(border=True):
                        st.markdown(f"#### 📊 {analysis.get('topic', '')}에 미치는 영향")
                        st.write(analysis.get("impact_on_target", ""))

                    with st.container(border=True):
                        st.markdown("#### 🔮 향후 시나리오")
                        st.write(analysis.get("future_scenarios", ""))

                    my_notes = st.text_area(
                        "📝 내 메모 (모르는 부분, 더 알아볼 것, 내 생각 등)",
                        value=st.session_state.get("current_analysis_notes", ""),
                        height=120,
                        key="current_analysis_notes",
                    )

                    if not gh_token:
                        st.info(
                            "GitHub 토큰을 등록하면 이 분석 결과를 계속 쌓이는 기록으로 저장할 수 있어요. "
                            "지금은 저장 대신 파일로 내려받아서 보관하세요."
                        )
                        github_token_setup_block()
                        export_payload = json.dumps(
                            {**analysis, "my_notes": my_notes, "saved_at": notes_store.now_iso()},
                            ensure_ascii=False, indent=2,
                        )
                        st.download_button(
                            "💾 이 분석 결과 .json으로 저장",
                            data=export_payload.encode("utf-8"),
                            file_name=f"analysis_{dt.date.today().isoformat()}.json",
                            mime="application/json",
                        )
                    else:
                        if st.button("💾 기록에 저장하기 (GitHub)"):
                            entry = {
                                "id": notes_store.new_entry_id(),
                                "created_at": notes_store.now_iso(),
                                "title": analysis["title"],
                                "topic": analysis.get("topic", ""),
                                "article_text": analysis.get("article_text", "")[:5000],
                                "summary": analysis.get("summary", ""),
                                "terms": analysis.get("terms", []),
                                "why_it_matters": analysis.get("why_it_matters", ""),
                                "impact_on_target": analysis.get("impact_on_target", ""),
                                "future_scenarios": analysis.get("future_scenarios", ""),
                                "my_notes": my_notes,
                            }
                            try:
                                with st.spinner("GitHub에 저장하는 중..."):
                                    notes_store.save_entry(gh_token, gh_repo, entry)
                            except Exception as e:
                                st.error(f"저장에 실패했습니다: {e}")
                            else:
                                st.success("저장했어요! 아래 '저장된 기록'에서 확인할 수 있어요.")
                                st.session_state.pop("current_analysis", None)
                                st.session_state.pop("current_analysis_notes", None)
                                st.session_state["notes_cache"] = None
                                st.rerun()

            st.divider()

            # ----- 저장된 기록 목록 -----
            st.markdown("### 📂 저장된 기록")
            gh_token, gh_repo = notes_store.get_config()
            if not gh_token:
                st.caption("GitHub 토큰을 등록하면 여기에 지금까지 쌓인 기록이 모두 나타나요.")
            else:
                if st.button("🔄 새로고침", key="refresh_notes"):
                    st.session_state["notes_cache"] = None

                if st.session_state.get("notes_cache") is None:
                    try:
                        st.session_state["notes_cache"] = notes_store.load_entries(gh_token, gh_repo)
                    except Exception as e:
                        st.error(f"기록을 불러오지 못했습니다: {e}")
                        st.session_state["notes_cache"] = []

                saved_entries = st.session_state.get("notes_cache") or []
                if not saved_entries:
                    st.caption("아직 저장된 기록이 없어요. 위에서 기사를 분석하고 저장해보세요.")
                for entry in saved_entries:
                    header = f"{entry.get('created_at', '')[:10]} · {entry.get('title', '(제목 없음)')}"
                    with st.expander(header):
                        st.caption(f"관련: {entry.get('topic', '')}")
                        st.write(f"**요약**: {entry.get('summary', '')}")
                        if entry.get("terms"):
                            st.markdown("**용어 정리**")
                            for t in entry["terms"]:
                                st.markdown(f"- **{t.get('term', '')}**: {t.get('definition', '')}")
                        st.write(f"**왜 중요한가**: {entry.get('why_it_matters', '')}")
                        st.write(f"**영향**: {entry.get('impact_on_target', '')}")
                        st.write(f"**향후 시나리오**: {entry.get('future_scenarios', '')}")
                        if entry.get("my_notes"):
                            st.write(f"**내 메모**: {entry.get('my_notes', '')}")
                        if st.button("🗑️ 이 기록 삭제", key=f"delete_{entry.get('id')}"):
                            try:
                                notes_store.delete_entry(gh_token, gh_repo, entry["id"])
                            except Exception as e:
                                st.error(f"삭제에 실패했습니다: {e}")
                            else:
                                st.session_state["notes_cache"] = None
                                st.rerun()

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

    # ===== 탭 5 : 향후 이벤트 (레이어 3) =====
    with tab5:
        st.caption(
            "채권 금리에 직접 영향을 주는 4가지 정기 이벤트(FOMC, CPI, 고용보고서, GDP)의 "
            "예정된 일정입니다. 실시간 자동 수집 대신, 연준·BLS·BEA 공식 발표 자료를 직접 "
            "확인해서 정리해둔 표예요 — 크롤링이 조용히 깨져서 틀린 날짜를 보여주는 사고를 "
            "막기 위한 선택입니다. 아래 출처에서 새 일정이 나오면 event_calendar.py만 "
            "업데이트하면 돼요."
        )

        upcoming = event_calendar.upcoming_events()

        if not upcoming:
            st.info("정리된 예정 이벤트가 없어요. event_calendar.py에 새 일정을 추가해주세요.")
        else:
            next_event = upcoming[0]
            days_left = (next_event["date"] - dt.date.today()).days

            with st.container(border=True):
                st.markdown("#### ⏭️ 다음 이벤트")
                c1, c2, c3 = st.columns([2, 1, 3])
                c1.metric(f"{next_event['icon']} {next_event['title']}", next_event["date"].strftime("%Y-%m-%d"))
                c2.metric("D-day", f"D-{days_left}" if days_left > 0 else "D-DAY")
                with c3:
                    st.write(next_event["detail"])
                    st.caption(f"💡 {next_event['driver_link']}")

            st.divider()
            st.markdown("### 📋 예정된 전체 일정")

            rows = []
            for e in upcoming:
                date_str = e["date"].strftime("%Y-%m-%d")
                if e.get("end_date"):
                    date_str += f" ~ {e['end_date'].strftime('%m-%d')}"
                d = (e["date"] - dt.date.today()).days
                rows.append({
                    "날짜": date_str,
                    "D-day": f"D-{d}" if d > 0 else "D-DAY",
                    "이벤트": f"{e['icon']} {e['title']}",
                    "설명": e["detail"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            with st.expander("📖 각 이벤트가 요인 카드와 어떻게 연결되는지"):
                seen_kinds = set()
                for e in upcoming:
                    if e["kind"] not in seen_kinds:
                        seen_kinds.add(e["kind"])
                        st.markdown(f"- **{e['icon']} {e['title']}**: {e['driver_link']}")

        st.caption(
            "출처: "
            "[연준 FOMC 일정](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) · "
            "[BLS CPI](https://www.bls.gov/schedule/news_release/cpi.htm) · "
            "[BLS 고용보고서](https://www.bls.gov/schedule/news_release/empsit.htm) · "
            "[BEA GDP](https://www.bea.gov/news/schedule)  \n"
            "마지막 확인일: 2026-09-08"
        )
