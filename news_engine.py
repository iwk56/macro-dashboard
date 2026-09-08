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
