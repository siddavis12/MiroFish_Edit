"""
EntityReader 단위 테스트
Neo4j mock으로 엔티티 필터링 및 컨텍스트 조합 로직 테스트
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.entity_reader import EntityReader, EntityNode, FilteredEntities
from app.services.graph_store import NodeData, EdgeData


class TestFilterDefinedEntities:
    """filter_defined_entities() 필터링 로직 테스트"""

    def _create_reader(self, mock_store):
        with patch("app.services.entity_reader.Neo4jGraphStore", return_value=mock_store):
            return EntityReader()

    def test_Entity만_있는_노드_필터_아웃(self, mock_neo4j_store):
        """labels가 ["Entity"]만 있으면 필터링됨"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test")

        # node-5는 labels=["Entity"]만 있으므로 필터링
        entity_names = [e.name for e in result.entities]
        assert "미분류인" not in entity_names
        assert "홍길동" in entity_names

    def test_커스텀_라벨_있는_노드_통과(self, mock_neo4j_store):
        """Entity 외 라벨이 있으면 통과"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test")

        # node-1(Student), node-2(Professor), node-3(University), node-4(Journalist) 통과
        assert result.filtered_count == 4
        assert result.total_count == 5

    def test_정의된_타입으로_필터링(self, mock_neo4j_store):
        """defined_entity_types 지정 시 해당 타입만 통과"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities(
            "graph_test",
            defined_entity_types=["Student", "Professor"]
        )

        entity_types = {e.get_entity_type() for e in result.entities}
        assert entity_types == {"Student", "Professor"}
        assert result.filtered_count == 2

    def test_엣지_enrichment_방향성(self, mock_neo4j_store):
        """관련 엣지의 방향이 올바르게 분류되는지"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test", enrich_with_edges=True)

        # 홍길동 (node-1): STUDIES_AT outgoing, REPORTS_ON incoming
        hong = next(e for e in result.entities if e.name == "홍길동")

        outgoing = [e for e in hong.related_edges if e["direction"] == "outgoing"]
        incoming = [e for e in hong.related_edges if e["direction"] == "incoming"]

        assert len(outgoing) == 1  # STUDIES_AT
        assert outgoing[0]["edge_name"] == "STUDIES_AT"
        assert len(incoming) == 1  # REPORTS_ON
        assert incoming[0]["edge_name"] == "REPORTS_ON"

    def test_엣지_enrichment_비활성화(self, mock_neo4j_store):
        """enrich_with_edges=False면 엣지 조회 안함"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test", enrich_with_edges=False)

        for entity in result.entities:
            assert entity.related_edges == []
            assert entity.related_nodes == []

    def test_관련_노드_조회(self, mock_neo4j_store):
        """관련 노드 정보가 포함되는지"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test", enrich_with_edges=True)

        # 홍길동은 서울대학교(STUDIES_AT), 이기자(REPORTS_ON) 관련
        hong = next(e for e in result.entities if e.name == "홍길동")
        related_names = {n["name"] for n in hong.related_nodes}
        assert "서울대학교" in related_names
        assert "이기자" in related_names

    def test_entity_types_집합(self, mock_neo4j_store):
        """발견된 엔티티 타입 집합 반환"""
        reader = self._create_reader(mock_neo4j_store)
        result = reader.filter_defined_entities("graph_test")

        assert result.entity_types == {"Student", "Professor", "University", "Journalist"}


class TestEntityNode:
    """EntityNode 데이터 구조 테스트"""

    def test_get_entity_type_커스텀_라벨(self):
        node = EntityNode(
            uuid="1", name="홍길동", labels=["Entity", "Student"],
            summary="", attributes={}
        )
        assert node.get_entity_type() == "Student"

    def test_get_entity_type_Entity만(self):
        node = EntityNode(
            uuid="1", name="미분류", labels=["Entity"],
            summary="", attributes={}
        )
        assert node.get_entity_type() is None

    def test_get_entity_type_Node_제외(self):
        node = EntityNode(
            uuid="1", name="테스트", labels=["Entity", "Node", "Professor"],
            summary="", attributes={}
        )
        assert node.get_entity_type() == "Professor"

    def test_to_dict(self):
        node = EntityNode(
            uuid="1", name="홍길동", labels=["Entity", "Student"],
            summary="학생", attributes={"major": "CS"},
            related_edges=[{"direction": "outgoing", "edge_name": "STUDIES_AT"}],
            related_nodes=[{"uuid": "2", "name": "서울대"}],
        )
        d = node.to_dict()
        assert d["uuid"] == "1"
        assert d["name"] == "홍길동"
        assert len(d["related_edges"]) == 1
        assert len(d["related_nodes"]) == 1


class TestGetEntityWithContext:
    """get_entity_with_context() 테스트"""

    def test_단일_엔티티_컨텍스트_조회(self, mock_neo4j_store, sample_nodes):
        with patch("app.services.entity_reader.Neo4jGraphStore", return_value=mock_neo4j_store):
            reader = EntityReader()

        entity = reader.get_entity_with_context("graph_test", "node-1")

        assert entity is not None
        assert entity.name == "홍길동"
        assert len(entity.related_edges) > 0

    def test_존재하지_않는_엔티티(self, mock_neo4j_store):
        mock_neo4j_store.get_node.return_value = None

        with patch("app.services.entity_reader.Neo4jGraphStore", return_value=mock_neo4j_store):
            reader = EntityReader()

        entity = reader.get_entity_with_context("graph_test", "nonexistent")
        assert entity is None
