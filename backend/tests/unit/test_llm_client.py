"""
LLMClient 단위 테스트
OpenAI API mock으로 클라이언트 로직 테스트
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.utils.llm_client import LLMClient


class TestLLMClientInit:
    """초기화 및 모델 감지 테스트"""

    @patch("app.utils.llm_client.OpenAI")
    def test_기본_초기화(self, mock_openai):
        client = LLMClient(api_key="sk-test")
        assert client.api_key == "sk-test"

    @patch("app.utils.llm_client.OpenAI")
    def test_API_키_없으면_에러(self, mock_openai):
        with patch("app.utils.llm_client.Config.LLM_API_KEY", None):
            with pytest.raises(ValueError, match="LLM_API_KEY"):
                LLMClient(api_key=None)

    @patch("app.utils.llm_client.OpenAI")
    def test_reasoning_모델_감지_gpt5(self, mock_openai):
        client = LLMClient(api_key="sk-test", model="gpt-5-mini")
        assert client._reasoning is True

    @patch("app.utils.llm_client.OpenAI")
    def test_reasoning_모델_감지_o1(self, mock_openai):
        client = LLMClient(api_key="sk-test", model="o1-preview")
        assert client._reasoning is True

    @patch("app.utils.llm_client.OpenAI")
    def test_일반_모델_감지(self, mock_openai):
        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        assert client._reasoning is False


class TestAdaptMessages:
    """메시지 변환 테스트"""

    @patch("app.utils.llm_client.OpenAI")
    def test_reasoning_모델_system_to_developer(self, mock_openai):
        client = LLMClient(api_key="sk-test", model="gpt-5-mini")
        messages = [
            {"role": "system", "content": "시스템 프롬프트"},
            {"role": "user", "content": "사용자 메시지"},
        ]
        adapted = client._adapt_messages(messages)
        assert adapted[0]["role"] == "developer"
        assert adapted[1]["role"] == "user"

    @patch("app.utils.llm_client.OpenAI")
    def test_일반_모델_변환_없음(self, mock_openai):
        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        messages = [{"role": "system", "content": "test"}]
        adapted = client._adapt_messages(messages)
        assert adapted[0]["role"] == "system"


class TestChat:
    """chat() 메서드 테스트"""

    @patch("app.utils.llm_client.OpenAI")
    def test_일반_모델_호출(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="응답입니다"))]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.chat([{"role": "user", "content": "test"}])

        assert result == "응답입니다"

    @patch("app.utils.llm_client.OpenAI")
    def test_think_태그_제거(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(
            content="<think>사고 중...</think>실제 응답"
        ))]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.chat([{"role": "user", "content": "test"}])

        assert "<think>" not in result
        assert result == "실제 응답"

    @patch("app.utils.llm_client.OpenAI")
    def test_reasoning_모델_파라미터(self, mock_openai):
        """reasoning 모델은 max_completion_tokens 사용, temperature 미사용"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_create = mock_openai.return_value.chat.completions.create
        mock_create.return_value = mock_response

        client = LLMClient(api_key="sk-test", model="gpt-5-mini")
        client.chat([{"role": "user", "content": "test"}], temperature=0.7, max_tokens=1000)

        call_kwargs = mock_create.call_args[1]
        assert "max_completion_tokens" in call_kwargs
        assert "temperature" not in call_kwargs


class TestChatJson:
    """chat_json() JSON 파싱 테스트"""

    @patch("app.utils.llm_client.OpenAI")
    def test_정상_JSON_파싱(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(
            content='{"key": "value"}'
        ))]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.chat_json([{"role": "user", "content": "test"}])

        assert result == {"key": "value"}

    @patch("app.utils.llm_client.OpenAI")
    def test_마크다운_코드블록_제거(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(
            content='```json\n{"key": "value"}\n```'
        ))]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.chat_json([{"role": "user", "content": "test"}])

        assert result == {"key": "value"}

    @patch("app.utils.llm_client.OpenAI")
    def test_JSON_파싱_실패_재시도(self, mock_openai):
        """첫 번째 호출 실패, 두 번째 성공"""
        mock_response_bad = MagicMock()
        mock_response_bad.choices = [MagicMock(message=MagicMock(content="not json"))]
        mock_response_good = MagicMock()
        mock_response_good.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]

        mock_create = mock_openai.return_value.chat.completions.create
        mock_create.side_effect = [mock_response_bad, mock_response_good]

        client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
        result = client.chat_json(
            [{"role": "user", "content": "test"}],
            max_attempts=2
        )

        assert result == {"ok": True}
        assert mock_create.call_count == 2
