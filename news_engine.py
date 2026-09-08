"""
레이어 1 : 현재 설명 - 뉴스 기반 요약 엔진
==========================================

Anthropic Claude API의 내장 웹 검색 도구(web_search)를 이용해, 선택한 요인과
관련된 최근 뉴스를 찾아 "왜 지금 이렇게 움직였는지"를 요약한다.

비용 안내 (2026년 9월 기준, 반드시 console.anthropic.com에서 최신 가격 확인)
---------------------------------------------------------------------
- 모델 토큰 비용: Claude Haiku 4.5 = 100만 토큰당 입력 $1 / 출력 $5 (가장 저렴)
                  Claude Sonnet 5 = 100만 토큰당 입력 $2 / 출력 $10
- 웹 검색 비용: 검색 1,000회당 $10 (검색 1회 = 약 1센트) + 검색 결과 토큰 비용
- 개인 사용 규모(하루 몇 번)에서는 한 달에 몇 달러 수준으로 예상됨.

API 키는 절대 코드에 하드코딩하지 않는다. Streamlit Cloud의 "Secrets" 기능이나
화면의 임시 입력창(세션에만 저장, 새로고침하면 사라짐)을 통해서만 사용한다.
"""

from __future__ import annotations

import json

import streamlit as st

# 웹 검색을 지원하는 것으로 확인된 모델 후보 (비용 낮은 순).
# 계정/시점에 따라 지원 모델이 달라질 수 있어 사용자가 화면에서 직접 고를 수 있게 한다.
MODEL_OPTIONS = {
    "Claude Haiku 4.5 (가장 저렴, 추천)": "claude-haiku-4-5",
    "Claude Sonnet 5 (더 똑똑하지만 비쌈)": "claude-sonnet-5",
}


def get_stored_api_key() -> str | None:
    """Streamlit secrets에 등록된 키를 우선 사용하고, 없으면 이번 세션에 직접
    입력한 키를 사용한다. 둘 다 없으면 None."""
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return st.session_state.get("anthropic_api_key_input") or None


def summarize_recent_news(topic: str, model: str, api_key: str) -> tuple[str, list[dict]]:
    """웹 검색으로 최근 뉴스를 찾아 요약한다.

    반환값: (요약 텍스트, 인용 출처 리스트[{title, url}])
    실패하면 예외를 그대로 위로 던진다 - 화면에서 st.error로 잡아서 보여준다.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        f"'{topic}'와 관련된 최근 2주 이내의 뉴스를 웹 검색으로 찾아서, "
        f"최근 왜 {topic}가 이렇게 움직였는지 한국어로 4~6문장으로 요약해줘. "
        "추측하지 말고 실제로 검색된 기사 내용에 근거해서 답하고, 어떤 기사를 "
        "참고했는지도 알 수 있게 해줘."
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts: list[str] = []
    sources: list[dict] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                title = getattr(citation, "title", None)
                if url:
                    sources.append({"title": title or url, "url": url})

    summary = "\n\n".join(text_parts) if text_parts else "요약을 생성하지 못했습니다."
    # 중복 출처 제거 (URL 기준)
    seen = set()
    unique_sources = []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique_sources.append(s)
    return summary, unique_sources


ANALYSIS_SCHEMA_KEYS = ["summary", "terms", "why_it_matters", "impact_on_target", "future_scenarios"]


def analyze_article(
    article_text: str,
    target_name: str,
    model: str,
    api_key: str,
    use_web_search: bool = False,
) -> dict:
    """사용자가 붙여넣은 기사(글) 원문을 분석해 구조화된 결과를 반환한다.

    반환 딕셔너리 키: summary, terms(list[{term, definition}]),
    why_it_matters, impact_on_target, future_scenarios.
    파싱에 실패하면 "_parse_error": True 와 함께 원문 텍스트를 summary에 담아 반환한다
    (요약 자체는 항상 사용자에게 보여줄 수 있게).
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    json_template = """{
  "summary": "3~5문장 한국어 요약",
  "terms": [{"term": "기사에 나온 전문용어", "definition": "이 문맥에서의 뜻을 쉬운 말로"}],
  "why_it_matters": "이 이슈가 왜 중요한지 2~4문장",
  "impact_on_target": "이 글의 내용이 '__TARGET__'에 어떤 영향을 주는지, 가능하면 교과서적 이론(방향/메커니즘)까지 포함해서 설명",
  "future_scenarios": "이 글을 바탕으로 앞으로 주목해야 할 이벤트나 가능한 시나리오 2~3가지"
}"""
    json_template = json_template.replace("__TARGET__", target_name)

    prompt = (
        "다음은 사용자가 읽은 뉴스 기사(또는 글)의 원문이야. 이 글을 분석해서 "
        "아래 형식의 JSON 객체 하나만 출력해줘. 코드블록 표시나 다른 설명 문장 "
        "없이 순수 JSON만 출력해야 해.\n\n"
        f"{json_template}\n\n"
        f'기사 원문:\n"""\n{article_text}\n"""'
    )

    kwargs = dict(model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]

    response = client.messages.create(**kwargs)

    raw = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()

    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        for key in ANALYSIS_SCHEMA_KEYS:
            result.setdefault(key, "" if key != "terms" else [])
        return result
    except Exception:
        return {
            "summary": raw or "분석 결과를 해석하지 못했습니다.",
            "terms": [],
            "why_it_matters": "",
            "impact_on_target": "",
            "future_scenarios": "",
            "_parse_error": True,
        }
