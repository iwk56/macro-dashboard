"""
채권·금리 요인(driver) 메타데이터
================================

각 요인을 "이론-실증-괴리" 3단 카드로 다루기 위한 표준 스키마.
새 요인을 추가하고 싶으면 DRIVERS 리스트에 항목 하나만 더 넣으면 된다.
(나중에 자산을 확장할 때도 이 스키마를 그대로 재사용하면 된다.)

각 요인 값의 의미
------------------
key            : 코드 내부에서 쓰는 식별자
name           : 화면에 표시할 한글 이름
fred_ticker    : FRED 시리즈 코드 (없으면 None, 별도 조사 필요라는 뜻)
vs_ticker      : 이 요인과 비교할 상대 시계열의 FRED 코드 (기본은 10년물 금리 DGS10)
expected_sign  : 이론상 예상되는 상관관계 부호. +1(같은 방향), -1(반대 방향)
theory_text    : 교과서적 설명
deviation_note : 최근 왜 이론과 어긋났는지에 대해 조사해둔 설명(비어있으면 추후 보강)
source_note    : 데이터 출처 설명
"""

DRIVERS = [
    {
        "key": "fed_funds",
        "name": "정책금리 (Fed Funds Rate)",
        "fred_ticker": "FEDFUNDS",
        "vs_ticker": "DGS10",
        "expected_sign": +1,
        "theory_text": (
            "FOMC가 직접 결정하는 값이라, 정책금리가 오르면 단기금리는 거의 "
            "기계적으로 따라 오른다. 장기금리(10년물)는 '미래 평균 단기금리 기대'를 "
            "반영하므로, 정책금리 인상 사이클에서는 이론상 10년물 금리도 같은 "
            "방향으로 움직이는 경우가 많다."
        ),
        "deviation_note": (
            "다만 정책금리 인상 후반부에는 '이 정도면 긴축이 경기를 눌러 곧 인하로 "
            "돌아설 것'이라는 기대가 커지면서, 정책금리는 계속 오르는데 10년물은 "
            "오히려 하락(장단기 역전 심화)하는 경우가 흔하다. 즉 관계가 인상 "
            "사이클의 '초반이냐 후반이냐'에 따라 달라진다."
        ),
        "source_note": "FRED 공식 데이터 (연준)",
    },
    {
        "key": "breakeven_inflation",
        "name": "기대인플레이션 (10Y 브레이크이븐)",
        "fred_ticker": "T10YIE",
        "vs_ticker": "DGS10",
        "expected_sign": +1,
        "theory_text": (
            "피셔 방정식(명목금리 = 실질금리 + 기대인플레이션)에 따르면, 시장의 "
            "기대인플레이션이 오르면 명목 장기금리도 같이 오르는 게 이론적으로 "
            "자연스럽다. 채권 투자자가 인플레이션으로 인한 구매력 손실을 보상받으려 "
            "하기 때문이다."
        ),
        "deviation_note": "",
        "source_note": "FRED 공식 데이터 (연준, 물가연동국채 스프레드로 산출)",
    },
    {
        "key": "real_yield",
        "name": "실질금리 (10Y TIPS)",
        "fred_ticker": "DFII10",
        "vs_ticker": "DGS10",
        "expected_sign": +1,
        "theory_text": (
            "명목금리에서 기대인플레이션을 뺀 값으로, 명목금리 변동의 상당 부분을 "
            "설명하는 핵심 축이다. 실질금리가 오르면 명목금리도 대체로 같이 오른다."
        ),
        "deviation_note": "",
        "source_note": "FRED 공식 데이터 (연준, 물가연동국채 수익률)",
    },
    {
        "key": "gov_debt",
        "name": "재정정책 / 정부부채 총액",
        "fred_ticker": "GFDEBTN",
        "vs_ticker": "DGS10",
        "expected_sign": +1,
        "theory_text": (
            "정부가 빚을 늘려 국채 발행을 늘릴수록, 이론상 채권 공급이 늘어나 "
            "가격은 떨어지고(금리는 오르고), 투자자들은 재정 건전성 리스크에 대한 "
            "보상(텀프리미엄)을 더 요구하게 된다."
        ),
        "deviation_note": (
            "2020~2021년처럼 연준이 대규모로 국채를 사들이는(양적완화) 시기에는 "
            "부채가 급증해도 금리가 오히려 낮게 유지됐다. 즉 '공급'만으로는 "
            "설명이 안 되고, 그 공급을 누가 흡수하는지(연준 vs 민간)가 함께 "
            "작용한다."
        ),
        "source_note": "미국 재무부 공식 데이터 (FRED 경유)",
    },
    {
        "key": "safe_haven",
        "name": "안전자산 수요 (VIX)",
        "fred_ticker": "VIXCLS",
        "vs_ticker": "DGS10",
        "expected_sign": -1,
        "theory_text": (
            "VIX(변동성지수)로 대표되는 시장 불안이 커지면, 투자자들이 위험자산을 "
            "팔고 안전자산인 국채로 몰리는 '플라이트 투 퀄리티' 현상이 나타난다. "
            "채권 수요가 늘면 가격이 오르고 금리는 떨어지므로, 이론상 VIX와 "
            "금리는 반대로 움직인다."
        ),
        "deviation_note": (
            "2022년처럼 '인플레이션 충격'이 위기의 원인일 때는 주식도 떨어지고 "
            "채권도 같이 떨어지는(금리는 오히려 오르는) 경우가 있었다. 위기의 "
            "성격(성장 충격 vs 인플레이션 충격)에 따라 관계의 방향이 달라진다."
        ),
        "source_note": "FRED 공식 데이터 (CBOE VIX)",
    },
    {
        "key": "foreign_demand",
        "name": "해외 수요 (일본/중국 등 보유국)",
        "fred_ticker": None,
        "vs_ticker": "DGS10",
        "expected_sign": -1,
        "theory_text": (
            "일본, 중국 같은 주요 보유국이 미국 국채를 많이 사들이면 수요가 "
            "늘어 가격이 오르고 금리는 떨어진다. 반대로 이들이 보유량을 줄이거나, "
            "일본은행처럼 자국 통화정책을 정상화(금리 인상)하면 자금이 자국으로 "
            "돌아가면서 미국 국채 수요가 줄어 금리 상승 압력이 된다."
        ),
        "deviation_note": "",
        "source_note": (
            "미국 재무부 TIC(Treasury International Capital) 통계 - 별도 조사 필요, "
            "아직 이 스크립트에 자동 수집 미구현"
        ),
    },
]


def get_driver(key):
    for d in DRIVERS:
        if d["key"] == key:
            return d
    raise KeyError(f"unknown driver key: {key}")
