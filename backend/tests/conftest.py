"""
MiroFish 백엔드 테스트 공통 Fixture
"""

import os
import sys
import json
import shutil
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

# 백엔드 루트를 sys.path에 추가
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)


# ============== 환경변수 설정 (import 전에 설정) ==============
os.environ.setdefault("LLM_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("LLM_MODEL_NAME", "gpt-4o-mini")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")


# ============== Flask 앱 Fixture ==============

@pytest.fixture
def app(tmp_path, monkeypatch):
    """테스트용 Flask 앱 생성"""
    # 파일시스템 경로를 임시 디렉토리로 리다이렉트
    monkeypatch.setattr("app.config.Config.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.config.Config.CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr("app.config.Config.DEBUG", False)

    # Neo4j 연결 mock (앱 초기화 시 연결 방지)
    with patch("app.services.neo4j_store.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        # SimulationRunner.register_cleanup mock
        with patch("app.services.simulation_runner.SimulationRunner.register_cleanup"):
            from app import create_app
            test_app = create_app()
            test_app.config["TESTING"] = True
            yield test_app


@pytest.fixture
def client(app):
    """Flask 테스트 클라이언트"""
    return app.test_client()


# ============== TaskManager 격리 Fixture ==============

@pytest.fixture(autouse=True)
def reset_singletons():
    """매 테스트 후 싱글턴 초기화"""
    yield
    from app.models.task import TaskManager
    TaskManager._instance = None

    # GraphBuilderService 전역 싱글턴 초기화
    try:
        import app.api.graph as graph_module
        graph_module._builder_instance = None
    except Exception:
        pass


# ============== Mock 데이터 ==============

@pytest.fixture
def sample_ontology():
    """테스트용 온톨로지"""
    return {
        "entity_types": [
            {"name": "Student", "description": "A university student", "attributes": [{"name": "major", "type": "text", "description": "Major field"}], "examples": ["Kim", "Lee"]},
            {"name": "Professor", "description": "A university professor", "attributes": [{"name": "department", "type": "text", "description": "Department"}], "examples": ["Dr. Park"]},
            {"name": "University", "description": "A university or college", "attributes": [{"name": "org_name", "type": "text", "description": "Name"}], "examples": ["Seoul Univ"]},
            {"name": "Company", "description": "A business corporation", "attributes": [], "examples": ["TechCorp"]},
            {"name": "Journalist", "description": "A reporter or journalist", "attributes": [], "examples": ["Reporter Kim"]},
            {"name": "MediaOutlet", "description": "A news organization", "attributes": [], "examples": ["KBS"]},
            {"name": "GovernmentAgency", "description": "A government body", "attributes": [], "examples": ["Ministry"]},
            {"name": "NGO", "description": "A non-governmental organization", "attributes": [], "examples": ["Greenpeace"]},
            {"name": "Person", "description": "Any individual person not fitting other specific types.", "attributes": [{"name": "full_name", "type": "text", "description": "Full name"}], "examples": ["citizen"]},
            {"name": "Organization", "description": "Any organization not fitting other specific types.", "attributes": [{"name": "org_name", "type": "text", "description": "Name"}], "examples": ["group"]},
        ],
        "edge_types": [
            {"name": "WORKS_FOR", "description": "Employment relationship", "source_targets": [{"source": "Person", "target": "Company"}], "attributes": []},
            {"name": "STUDIES_AT", "description": "Studies at institution", "source_targets": [{"source": "Student", "target": "University"}], "attributes": []},
            {"name": "REPORTS_ON", "description": "Reports on topic", "source_targets": [{"source": "Journalist", "target": "Person"}], "attributes": []},
        ],
        "analysis_summary": "학술 관련 이벤트 분석 온톨로지"
    }


@pytest.fixture
def sample_nodes():
    """테스트용 NodeData 목록"""
    from app.services.graph_store import NodeData
    return [
        NodeData(uuid="node-1", name="홍길동", labels=["Entity", "Student"], summary="서울대 학생", attributes={"major": "컴퓨터공학"}),
        NodeData(uuid="node-2", name="김교수", labels=["Entity", "Professor"], summary="서울대 교수", attributes={"department": "CS"}),
        NodeData(uuid="node-3", name="서울대학교", labels=["Entity", "University"], summary="서울 소재 대학교", attributes={"org_name": "서울대학교"}),
        NodeData(uuid="node-4", name="이기자", labels=["Entity", "Journalist"], summary="한국일보 기자", attributes={}),
        NodeData(uuid="node-5", name="미분류인", labels=["Entity"], summary="라벨 없는 엔티티", attributes={}),
    ]


@pytest.fixture
def sample_edges():
    """테스트용 EdgeData 목록"""
    from app.services.graph_store import EdgeData
    return [
        EdgeData(uuid="edge-1", name="STUDIES_AT", fact="홍길동은 서울대학교에서 공부한다", source_node_uuid="node-1", target_node_uuid="node-3", source_node_name="홍길동", target_node_name="서울대학교"),
        EdgeData(uuid="edge-2", name="WORKS_FOR", fact="김교수는 서울대학교에서 일한다", source_node_uuid="node-2", target_node_uuid="node-3", source_node_name="김교수", target_node_name="서울대학교"),
        EdgeData(uuid="edge-3", name="REPORTS_ON", fact="이기자가 홍길동에 대해 보도한다", source_node_uuid="node-4", target_node_uuid="node-1", source_node_name="이기자", target_node_name="홍길동"),
    ]


@pytest.fixture
def sample_extraction_result():
    """테스트용 ExtractionResult"""
    from app.services.graph_store import ExtractionResult
    return ExtractionResult(
        entities=[
            {"name": "홍길동", "labels": ["Student"], "summary": "서울대 학생", "attributes": {"major": "컴퓨터공학"}},
            {"name": "서울대학교", "labels": ["University"], "summary": "서울 소재 대학교", "attributes": {}},
        ],
        relationships=[
            {"source": "홍길동", "target": "서울대학교", "name": "STUDIES_AT", "fact": "홍길동은 서울대학교에서 공부한다"},
        ]
    )


@pytest.fixture
def sample_project_data():
    """테스트용 프로젝트 데이터"""
    return {
        "project_id": "proj_test12345678",
        "name": "테스트 프로젝트",
        "status": "created",
        "created_at": "2026-03-17T00:00:00",
        "updated_at": "2026-03-17T00:00:00",
        "files": [],
        "total_text_length": 1000,
    }


@pytest.fixture
def sample_document_text():
    """테스트용 문서 텍스트"""
    return """서울대학교에서 학술 부정 사건이 발생했다. 홍길동 학생이 김교수의 논문을 표절한 혐의로 조사를 받고 있다.
이기자는 이 사건에 대해 한국일보에 기사를 작성했다. 서울대학교 측은 조사위원회를 구성하여 사실관계를 확인 중이다.
학생회는 공정한 조사를 촉구하는 성명을 발표했으며, 교육부도 관심을 가지고 상황을 주시하고 있다.
NGO 단체인 학술청렴위원회도 독립적인 조사를 요구했다."""


# ============== Mock 서비스 Fixture ==============

@pytest.fixture
def mock_neo4j_store(sample_nodes, sample_edges):
    """Neo4jGraphStore mock"""
    store = MagicMock()
    store.get_nodes_by_graph.return_value = sample_nodes
    store.get_edges_by_graph.return_value = sample_edges
    store.get_node.side_effect = lambda uuid: next((n for n in sample_nodes if n.uuid == uuid), None)
    store.get_entity_edges.side_effect = lambda uuid: [e for e in sample_edges if e.source_node_uuid == uuid or e.target_node_uuid == uuid]
    store.create_graph.return_value = "mirofish_test123"
    store.merge_extraction.return_value = {"nodes_created": 2, "edges_created": 1}
    store.get_ontology.return_value = None
    store.search.return_value = MagicMock(facts=[], edges=[], nodes=[], total_count=0)
    return store


@pytest.fixture
def mock_chroma_store():
    """ChromaSearchService mock"""
    chroma = MagicMock()
    chroma.index_nodes_batch.return_value = 5
    chroma.index_edges_batch.return_value = 3
    chroma.search.return_value = MagicMock(facts=["테스트 팩트"], edges=[], nodes=[], total_count=1)
    chroma.delete_graph_data.return_value = None
    return chroma


@pytest.fixture
def mock_llm_client():
    """LLMClient mock"""
    client = MagicMock()
    client.chat.return_value = "테스트 응답"
    client.chat_json.return_value = {}
    client.chat_with_retry.return_value = ("테스트 응답", "stop")
    client._reasoning = False
    return client
