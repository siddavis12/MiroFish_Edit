"""
OntologyGenerator 단위 테스트
LLM 호출을 mock하여 온톨로지 생성 및 검증 로직 테스트
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.ontology_generator import OntologyGenerator


class TestValidateAndProcess:
    """_validate_and_process() 검증 로직 테스트"""

    def setup_method(self):
        with patch("app.utils.llm_client.OpenAI"):
            self.gen = OntologyGenerator(llm_client=MagicMock())

    def test_폴백_유형_자동_추가(self):
        """Person, Organization 없으면 자동 추가"""
        result = {
            "entity_types": [
                {"name": "Student", "description": "A student"},
                {"name": "Professor", "description": "A professor"},
            ],
            "edge_types": [],
        }

        processed = self.gen._validate_and_process(result)
        names = [e["name"] for e in processed["entity_types"]]

        assert "Person" in names
        assert "Organization" in names

    def test_폴백_유형_이미_있으면_추가_안함(self):
        """이미 Person, Organization이 있으면 중복 추가 안함"""
        result = {
            "entity_types": [
                {"name": "Student", "description": "A student"},
                {"name": "Person", "description": "Any person"},
                {"name": "Organization", "description": "Any org"},
            ],
            "edge_types": [],
        }

        processed = self.gen._validate_and_process(result)
        person_count = sum(1 for e in processed["entity_types"] if e["name"] == "Person")
        org_count = sum(1 for e in processed["entity_types"] if e["name"] == "Organization")

        assert person_count == 1
        assert org_count == 1

    def test_엔티티_유형_10개_초과시_절단(self):
        """10개 초과하면 절단"""
        result = {
            "entity_types": [{"name": f"Type{i}", "description": f"Type {i}"} for i in range(12)],
            "edge_types": [],
        }

        processed = self.gen._validate_and_process(result)
        assert len(processed["entity_types"]) <= 10

    def test_폴백_추가시_기존_유형_제거(self):
        """폴백 추가로 10개 초과 시 기존 유형 끝에서 제거"""
        result = {
            "entity_types": [{"name": f"Type{i}", "description": f"Type {i}"} for i in range(10)],
            "edge_types": [],
        }

        processed = self.gen._validate_and_process(result)

        # Person, Organization 추가되면서 기존 유형 2개 제거
        names = [e["name"] for e in processed["entity_types"]]
        assert "Person" in names
        assert "Organization" in names
        assert len(processed["entity_types"]) <= 10

    def test_description_100자_초과_절단(self):
        """description이 100자 초과하면 절단"""
        long_desc = "a" * 150
        result = {
            "entity_types": [{"name": "Test", "description": long_desc}],
            "edge_types": [{"name": "REL", "description": long_desc}],
        }

        processed = self.gen._validate_and_process(result)
        assert len(processed["entity_types"][0]["description"]) <= 100
        assert processed["entity_types"][0]["description"].endswith("...")
        assert len(processed["edge_types"][0]["description"]) <= 100

    def test_누락_필드_자동_보충(self):
        """attributes, examples 등 누락 필드 자동 보충"""
        result = {
            "entity_types": [{"name": "Test"}],
            "edge_types": [{"name": "REL"}],
        }

        processed = self.gen._validate_and_process(result)
        assert "attributes" in processed["entity_types"][0]
        assert "examples" in processed["entity_types"][0]
        assert "source_targets" in processed["edge_types"][0]
        assert "analysis_summary" in processed

    def test_엣지_유형_10개_초과시_절단(self):
        """엣지 유형 10개 초과 시 절단"""
        result = {
            "entity_types": [],
            "edge_types": [{"name": f"REL_{i}", "description": f"Rel {i}"} for i in range(15)],
        }

        processed = self.gen._validate_and_process(result)
        assert len(processed["edge_types"]) <= 10


class TestBuildUserMessage:
    """_build_user_message() 테스트"""

    def setup_method(self):
        with patch("app.utils.llm_client.OpenAI"):
            self.gen = OntologyGenerator(llm_client=MagicMock())

    def test_기본_메시지_구성(self):
        msg = self.gen._build_user_message(
            ["문서 내용입니다."],
            "여론 시뮬레이션",
            None
        )
        assert "여론 시뮬레이션" in msg
        assert "문서 내용입니다." in msg

    def test_5만자_초과_절단(self):
        long_text = "가" * 60000
        msg = self.gen._build_user_message(
            [long_text],
            "테스트",
            None
        )
        # 메시지에 원문 길이 안내가 포함
        assert "60000" in msg
        assert f"{OntologyGenerator.MAX_TEXT_LENGTH_FOR_LLM}" in msg

    def test_추가_컨텍스트_포함(self):
        msg = self.gen._build_user_message(
            ["문서"],
            "요구사항",
            "추가 설명 내용"
        )
        assert "추가 설명 내용" in msg


class TestGenerate:
    """generate() 통합 흐름 테스트"""

    def test_LLM_호출_및_후처리(self):
        mock_llm = MagicMock()
        mock_llm.chat_json.return_value = {
            "entity_types": [
                {"name": "Student", "description": "A student"},
                {"name": "Person", "description": "Any person"},
                {"name": "Organization", "description": "Any org"},
            ],
            "edge_types": [
                {"name": "STUDIES_AT", "description": "Studies at"},
            ],
            "analysis_summary": "테스트 분석"
        }

        with patch("app.utils.llm_client.OpenAI"):
            gen = OntologyGenerator(llm_client=mock_llm)

        result = gen.generate(["테스트 문서"], "여론 시뮬레이션")

        # LLM 호출 확인
        mock_llm.chat_json.assert_called_once()

        # 결과 검증
        assert "entity_types" in result
        assert "edge_types" in result
        names = [e["name"] for e in result["entity_types"]]
        assert "Person" in names
        assert "Organization" in names


class TestGeneratePythonCode:
    """generate_python_code() 코드 생성 테스트"""

    def test_코드_생성(self, sample_ontology):
        with patch("app.utils.llm_client.OpenAI"):
            gen = OntologyGenerator(llm_client=MagicMock())

        code = gen.generate_python_code(sample_ontology)

        assert "class Student(EntityModel):" in code
        assert "class Person(EntityModel):" in code
        assert "ENTITY_TYPES" in code
        assert "EDGE_TYPES" in code
        assert "EDGE_SOURCE_TARGETS" in code
