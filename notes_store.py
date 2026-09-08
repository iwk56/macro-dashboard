"""
기사 분석 기록 저장소 (GitHub 기반 "가벼운 DB")
=============================================

Streamlit Community Cloud는 앱이 잠들었다 깨거나 새로 배포될 때마다 로컬
파일이 초기화된다. 그래서 "계속 쌓이는 기록"을 만들려면 앱 바깥의 저장소가
필요한데, 별도 데이터베이스 서비스를 새로 계약하는 대신 이미 쓰고 있는
GitHub 저장소 안에 JSON 파일 하나(기본값: data/news_notes.json)를 두고
GitHub REST API로 그 파일을 읽고/새 항목을 덧붙여 쓰는 방식으로 구현했다.
완전히 무료이고, 필요하면 GitHub 웹사이트에서 그 파일을 직접 열어볼 수도 있다.

필요한 것: 그 저장소에 쓰기 권한이 있는 GitHub Personal Access Token (PAT).
Streamlit Secrets에 아래처럼 등록해서 사용한다 (코드에는 절대 넣지 않는다).

    GITHUB_TOKEN = "github_pat_..."
    GITHUB_REPO = "iwk56/macro-dashboard"   # 선택 사항, 안 넣으면 기본값 사용
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import uuid

import requests
import streamlit as st

DEFAULT_REPO = "iwk56/macro-dashboard"
DATA_PATH = "data/news_notes.json"
API_ROOT = "https://api.github.com"
TIMEOUT = 15


def get_config() -> tuple[str | None, str]:
    """(토큰, 저장소) 튜플을 반환한다. 토큰이 없으면 None."""
    token = None
    repo = DEFAULT_REPO
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO", DEFAULT_REPO)
    except Exception:
        pass
    token = token or st.session_state.get("github_token_input") or None
    return token, repo


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file(token: str, repo: str) -> tuple[list, str | None]:
    """(항목 리스트, sha) 를 반환한다. 파일이 아직 없으면 ([], None)."""
    url = f"{API_ROOT}/repos/{repo}/contents/{DATA_PATH}"
    resp = requests.get(url, headers=_headers(token), timeout=TIMEOUT)
    if resp.status_code == 404:
        return [], None
    resp.raise_for_status()
    payload = resp.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    entries = json.loads(content) if content.strip() else []
    return entries, payload["sha"]


def load_entries(token: str, repo: str) -> list:
    entries, _ = _get_file(token, repo)
    return entries


def _put_file(token: str, repo: str, entries: list, sha: str | None, message: str) -> None:
    new_content = json.dumps(entries, ensure_ascii=False, indent=2)
    url = f"{API_ROOT}/repos/{repo}/contents/{DATA_PATH}"
    body = {
        "message": message,
        "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
    }
    if sha:
        body["sha"] = sha
    resp = requests.put(url, headers=_headers(token), json=body, timeout=TIMEOUT)
    resp.raise_for_status()


def save_entry(token: str, repo: str, entry: dict) -> list:
    """새 항목을 목록 맨 앞에 추가하고 GitHub에 한 번의 커밋으로 반영한다."""
    entries, sha = _get_file(token, repo)
    entries.insert(0, entry)
    _put_file(token, repo, entries, sha, f"기록 추가: {entry.get('title', entry.get('id', ''))}")
    return entries


def delete_entry(token: str, repo: str, entry_id: str) -> list:
    entries, sha = _get_file(token, repo)
    entries = [e for e in entries if e.get("id") != entry_id]
    _put_file(token, repo, entries, sha, f"기록 삭제: {entry_id}")
    return entries


def new_entry_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")
