"""
TextProcessor 단위 테스트
순수 텍스트 처리 로직 테스트 (외부 의존성 없음)
"""

from app.services.text_processor import TextProcessor


class TestPreprocessText:
    """텍스트 전처리 테스트"""

    def test_줄바꿈_표준화_crlf(self):
        text = "줄1\r\n줄2\r\n줄3"
        result = TextProcessor.preprocess_text(text)
        assert "\r" not in result
        assert "줄1\n줄2\n줄3" == result

    def test_줄바꿈_표준화_cr(self):
        text = "줄1\r줄2\r줄3"
        result = TextProcessor.preprocess_text(text)
        assert "줄1\n줄2\n줄3" == result

    def test_연속_빈줄_제거(self):
        text = "줄1\n\n\n\n\n줄2"
        result = TextProcessor.preprocess_text(text)
        assert result == "줄1\n\n줄2"

    def test_줄_앞뒤_공백_제거(self):
        text = "  줄1  \n  줄2  "
        result = TextProcessor.preprocess_text(text)
        assert result == "줄1\n줄2"

    def test_빈_텍스트(self):
        assert TextProcessor.preprocess_text("") == ""
        assert TextProcessor.preprocess_text("   ") == ""


class TestGetTextStats:
    """텍스트 통계 테스트"""

    def test_기본_통계(self):
        text = "hello world\nsecond line"
        stats = TextProcessor.get_text_stats(text)

        assert stats["total_chars"] == len(text)
        assert stats["total_lines"] == 2
        assert stats["total_words"] == 4

    def test_빈_텍스트_통계(self):
        stats = TextProcessor.get_text_stats("")
        assert stats["total_chars"] == 0
        assert stats["total_lines"] == 1  # 빈 문자열도 1줄
        assert stats["total_words"] == 0

    def test_한국어_텍스트(self):
        text = "안녕하세요 반갑습니다"
        stats = TextProcessor.get_text_stats(text)
        assert stats["total_chars"] == len(text)
        assert stats["total_words"] == 2


class TestSplitText:
    """텍스트 분할 테스트"""

    def test_기본_분할(self):
        text = "a" * 1000
        chunks = TextProcessor.split_text(text, chunk_size=300, overlap=50)

        assert len(chunks) > 1
        # 각 청크가 chunk_size 이하인지 확인
        for chunk in chunks:
            assert len(chunk) <= 300 + 50  # 오버랩 허용 오차

    def test_짧은_텍스트_분할_안함(self):
        text = "짧은 텍스트"
        chunks = TextProcessor.split_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_빈_텍스트(self):
        chunks = TextProcessor.split_text("", chunk_size=500, overlap=50)
        # 빈 텍스트는 빈 리스트 또는 빈 문자열 1개
        assert len(chunks) <= 1
