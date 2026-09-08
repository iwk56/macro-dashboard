"""
레이어 3 : 향후 이벤트 감지 - 캘린더 데이터
==========================================

FOMC 회의 일정과 미국 주요 경제지표(CPI, 고용보고서, GDP) 발표일을 정리해둔
참고 데이터. 채권·금리에 가장 직접적인 영향을 주는 4가지 정기 이벤트로
범위를 좁혔다 (기업 실적 발표 등은 이 대시보드의 채권 테마와 연관이 상대적으로
낮아 제외).

왜 실시간 크롤링이 아니라 수동으로 정리한 표인가
-----------------------------------------------
연준(FOMC)·노동통계국(BLS)·경제분석국(BEA) 공식 홈페이지에서 매번 실시간으로
긁어오는 방식도 가능하지만, 세 기관 모두 페이지 구조가 바뀔 수 있고 크롤링이
조용히 깨지면(예: 날짜를 엉뚱하게 파싱) "틀린 날짜를 진짜인 것처럼" 보여주는
사고로 이어질 수 있다. 이 대시보드는 처음부터 "실제 데이터인지 아닌지 절대
헷갈리지 않게"를 원칙으로 삼아왔기 때문에, drivers.py/cases.py와 같은 방식으로
공식 발표 자료를 직접 확인해서 정리해둔 표를 쓰고, 새 일정이 나오면 이 파일만
업데이트하는 방식을 택했다.

업데이트 방법 (아래 리스트에 항목만 추가하면 됨)
------------------------------------------------
- FOMC 일정: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- CPI 일정: https://www.bls.gov/schedule/news_release/cpi.htm
- 고용보고서 일정: https://www.bls.gov/schedule/news_release/empsit.htm
- GDP 일정: https://www.bea.gov/news/schedule

마지막 확인일: 2026-09-08 (2026년 잔여 일정 + 2027년 FOMC 일정까지 반영)
"""

from __future__ import annotations

import datetime as dt

# (시작일, 종료일, 기자회견 여부, SEP(경제전망 요약) 발표 여부)
# press_conference/sep 가 None 인 항목은 연준이 아직 공식적으로 표기하지 않은 경우.
FOMC_MEETINGS = [
    {"start": dt.date(2026, 9, 15), "end": dt.date(2026, 9, 16), "press_conference": False, "sep": True},
    {"start": dt.date(2026, 10, 27), "end": dt.date(2026, 10, 28), "press_conference": True, "sep": False},
    {"start": dt.date(2026, 12, 8), "end": dt.date(2026, 12, 9), "press_conference": True, "sep": True},
    {"start": dt.date(2027, 1, 26), "end": dt.date(2027, 1, 27), "press_conference": None, "sep": None},
    {"start": dt.date(2027, 3, 16), "end": dt.date(2027, 3, 17), "press_conference": None, "sep": True},
    {"start": dt.date(2027, 4, 27), "end": dt.date(2027, 4, 28), "press_conference": None, "sep": None},
    {"start": dt.date(2027, 6, 8), "end": dt.date(2027, 6, 9), "press_conference": None, "sep": True},
    {"start": dt.date(2027, 7, 27), "end": dt.date(2027, 7, 28), "press_conference": None, "sep": None},
    {"start": dt.date(2027, 9, 14), "end": dt.date(2027, 9, 15), "press_conference": None, "sep": True},
    {"start": dt.date(2027, 10, 26), "end": dt.date(2027, 10, 27), "press_conference": None, "sep": None},
    {"start": dt.date(2027, 12, 7), "end": dt.date(2027, 12, 8), "press_conference": None, "sep": True},
]

CPI_DATES = [
    dt.date(2026, 9, 11), dt.date(2026, 10, 14), dt.date(2026, 11, 10), dt.date(2026, 12, 10),
]

JOBS_REPORT_DATES = [
    dt.date(2026, 10, 2), dt.date(2026, 11, 6), dt.date(2026, 12, 4),
]

GDP_RELEASES = [
    {"date": dt.date(2026, 10, 29), "label": "GDP 속보치 (3분기)"},
    {"date": dt.date(2026, 11, 25), "label": "GDP 잠정치 (3분기)"},
    {"date": dt.date(2026, 12, 23), "label": "GDP 확정치 (3분기)"},
]

# 이 이벤트가 대시보드의 어떤 요인 카드와 이어지는지 (교육적 연결)
EVENT_DRIVER_LINK = {
    "fomc": "정책금리 카드와 직접 연결 — 회의 결과(동결/인상/인하)가 단기금리에 즉시 반영됨.",
    "cpi": "기대인플레이션 카드와 직접 연결 — 예상보다 높거나 낮으면 브레이크이븐 금리가 즉각 움직임.",
    "jobs": "안전자산수요·정책금리 카드와 연결 — 예상보다 강하면 긴축 기대, 약하면 완화 기대로 해석됨.",
    "gdp": "성장 기대와 연결 — 장기금리(텀프리미엄)에 영향을 주는 배경 지표.",
}


def build_event_list() -> list[dict]:
    """모든 이벤트를 하나의 리스트로 합쳐 날짜순으로 정렬해서 반환한다.

    각 항목: {date, end_date, kind, icon, title, detail, driver_link}
    """
    events: list[dict] = []

    for m in FOMC_MEETINGS:
        detail_parts = []
        if m["press_conference"] is True:
            detail_parts.append("기자회견 있음")
        elif m["press_conference"] is False:
            detail_parts.append("기자회견 없음")
        if m["sep"] is True:
            detail_parts.append("경제전망(SEP) 발표")
        detail = " · ".join(detail_parts) if detail_parts else "세부 일정 미확정 (연준 공식 발표 대기)"
        events.append({
            "date": m["start"], "end_date": m["end"], "kind": "fomc", "icon": "🏛️",
            "title": "FOMC 회의", "detail": detail, "driver_link": EVENT_DRIVER_LINK["fomc"],
        })

    for d in CPI_DATES:
        events.append({
            "date": d, "end_date": None, "kind": "cpi", "icon": "🔥",
            "title": "CPI (소비자물가지수) 발표", "detail": "미국 노동통계국(BLS)",
            "driver_link": EVENT_DRIVER_LINK["cpi"],
        })

    for d in JOBS_REPORT_DATES:
        events.append({
            "date": d, "end_date": None, "kind": "jobs", "icon": "💼",
            "title": "고용보고서 발표", "detail": "미국 노동통계국(BLS)",
            "driver_link": EVENT_DRIVER_LINK["jobs"],
        })

    for g in GDP_RELEASES:
        events.append({
            "date": g["date"], "end_date": None, "kind": "gdp", "icon": "📈",
            "title": g["label"], "detail": "미국 경제분석국(BEA)",
            "driver_link": EVENT_DRIVER_LINK["gdp"],
        })

    events.sort(key=lambda e: e["date"])
    return events


def upcoming_events(today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    return [e for e in build_event_list() if e["date"] >= today]
