"""
LLM 클라이언트 래퍼
OpenAI API 통합 호출, reasoning 모델 자동 감지 및 파라미터 조정
"""

import json
import re
import time
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI

from ..config import Config


class LLMClient:
    """LLM 클라이언트 (reasoning 모델 자동 지원)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_boost: bool = False
    ):
        # Boost 모드: 병렬 시뮬레이션 시 두 번째 API로 동시성 향상
        if use_boost and Config.LLM_BOOST_API_KEY:
            self.api_key = Config.LLM_BOOST_API_KEY
            self.model = Config.LLM_BOOST_MODEL_NAME or Config.LLM_MODEL_NAME
        else:
            self.api_key = api_key or Config.LLM_API_KEY
            self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다")

        self.client = OpenAI(api_key=self.api_key, timeout=120.0)

        # 모델 특성 캐싱
        self._reasoning = self._is_reasoning_model()

    def _is_reasoning_model(self) -> bool:
        """reasoning 모델 여부 자동 감지"""
        model = self.model.lower()
        # o1, o3, o4 계열은 모두 reasoning 모델
        reasoning_prefixes = ("o1", "o3", "o4")
        if any(model.startswith(p) or f"-{p}" in model for p in reasoning_prefixes):
            return True
        # gpt-5, gpt-5-mini, gpt-5-nano 모두 reasoning
        if "gpt-5" in model:
            return True
        return False

    def _adapt_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """reasoning 모델용 메시지 role 변환 (system → developer)"""
        if not self._reasoning:
            return messages
        return [
            {**msg, "role": "developer"} if msg["role"] == "system" else msg
            for msg in messages
        ]

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 요청을 전송합니다

        Args:
            messages: 메시지 목록
            temperature: 온도 매개변수 (reasoning 모델에서는 무시됨)
            max_tokens: 최대 토큰 수
            response_format: 응답 형식 (예: JSON 모드)

        Returns:
            모델 응답 텍스트
        """
        adapted_messages = self._adapt_messages(messages)

        kwargs = {
            "model": self.model,
            "messages": adapted_messages,
        }

        if self._reasoning:
            # reasoning 모델: temperature 제거, max_completion_tokens 사용
            # 추론(thinking) 토큰도 이 예산에 포함되므로 최소 3배 여유분 확보
            reasoning_budget = max(max_tokens * 3, 16384)
            kwargs["max_completion_tokens"] = reasoning_budget
        else:
            # 일반 모델: 기존 방식
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        # 일부 모델은 content에 <think> 사고 내용을 포함하므로 제거
        # 단, <think> 밖에 실제 콘텐츠가 있을 때만 제거 (전부 <think> 안에 있으면 보존)
        stripped = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        if stripped:
            content = stripped
        else:
            # <think> 태그 안에만 콘텐츠가 있는 경우 → 태그만 제거하고 내용 보존
            content = re.sub(r'</?think>', '', content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        채팅 요청을 전송하고 JSON을 반환합니다

        Args:
            messages: 메시지 목록
            temperature: 온도 매개변수
            max_tokens: 최대 토큰 수
            max_attempts: JSON 파싱 실패 시 최대 재시도 횟수

        Returns:
            파싱된 JSON 객체
        """
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = self.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )
            except Exception as e:
                last_error = e
                wait = 2 * (attempt + 1)
                time.sleep(wait)
                continue

            # markdown 코드 블록 마커 제거
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()

            # 빈 응답인 경우 재시도
            if not cleaned_response:
                last_error = ValueError(f"LLM이 빈 응답을 반환했습니다 (원본 길이: {len(response)}, 원본 앞 100자: {response[:100]})")
                wait = 2 * (attempt + 1)
                time.sleep(wait)
                continue

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                last_error = ValueError(f"LLM이 반환한 JSON 형식이 유효하지 않습니다: {cleaned_response[:200]}")
                wait = 2 * (attempt + 1)
                time.sleep(wait)

        raise last_error

    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_attempts: int = 3,
        response_format: Optional[Dict] = None
    ) -> Tuple[str, str]:
        """
        재시도 기능이 있는 채팅 요청

        Args:
            messages: 메시지 목록
            temperature: 온도 매개변수
            max_tokens: 최대 토큰 수 (None이면 LLM 자유 생성)
            max_attempts: 최대 재시도 횟수
            response_format: 응답 형식

        Returns:
            (content, finish_reason) 튜플
        """
        adapted_messages = self._adapt_messages(messages)
        last_error = None

        for attempt in range(max_attempts):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": adapted_messages,
                }

                if self._reasoning:
                    # reasoning 모델: temperature 제거, max_completion_tokens 사용
                    # 추론 토큰도 이 예산에 포함되므로 최소 3배 여유분 확보
                    if max_tokens:
                        kwargs["max_completion_tokens"] = max(max_tokens * 3, 16384)
                else:
                    # 일반 모델: 재시도마다 temperature 감소
                    kwargs["temperature"] = temperature - (attempt * 0.1)
                    if max_tokens:
                        kwargs["max_tokens"] = max_tokens

                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                finish_reason = response.choices[0].finish_reason
                return content, finish_reason

            except Exception as e:
                last_error = e
                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM 호출 실패")
