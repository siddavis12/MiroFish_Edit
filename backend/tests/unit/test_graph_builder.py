"""
GraphBuilderService 단위 테스트
Neo4j, LLM, ChromaDB를 mock하여 그래프 구축 로직 테스트
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from app.services.graph_builder import GraphBuilderService, GraphInfo
from app.services.graph_store import NodeData, EdgeData, ExtractionResult


class TestGraphBuilderService:
    """GraphBuilderService 테스트"""

    def _create_builder(self, mock_store, mock_chroma, mock_extractor=None):
        """mock이 주입된 GraphBuilderService 생성"""
        with patch("app.services.graph_builder.Neo4jGraphStore", return_value=mock_store), \
             patch("app.services.graph_builder.ChromaSearchService", return_value=mock_chroma), \
             patch("app.services.graph_builder.LLMEntityExtractor", return_value=mock_extractor or MagicMock()):
            builder = GraphBuilderService()
        return builder

    def test_create_graph(self, mock_neo4j_store, mock_chroma_store):
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        graph_id = builder.create_graph("테스트 그래프")

        assert graph_id.startswith("mirofish_")
        mock_neo4j_store.create_graph.assert_called_once()

    def test_set_ontology(self, mock_neo4j_store, mock_chroma_store, sample_ontology):
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        builder.set_ontology("graph_123", sample_ontology)

        mock_neo4j_store.set_ontology.assert_called_once_with("graph_123", sample_ontology)

    def test_get_graph_data(self, mock_neo4j_store, mock_chroma_store, sample_nodes, sample_edges):
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        data = builder.get_graph_data("graph_test")

        assert data["graph_id"] == "graph_test"
        assert data["node_count"] == len(sample_nodes)
        assert data["edge_count"] == len(sample_edges)
        assert "nodes" in data
        assert "edges" in data

    def test_get_graph_data_엣지_노드이름_보충(self, mock_neo4j_store, mock_chroma_store):
        """source/target 노드 이름이 비어있으면 보충"""
        edge_no_names = EdgeData(
            uuid="e1", name="REL", fact="fact",
            source_node_uuid="node-1", target_node_uuid="node-2",
            source_node_name="", target_node_name=""
        )
        mock_neo4j_store.get_edges_by_graph.return_value = [edge_no_names]

        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        data = builder.get_graph_data("graph_test")

        # node_map에서 이름 보충
        edge = data["edges"][0]
        assert edge["source_node_name"] == "홍길동"  # node-1
        assert edge["target_node_name"] == "김교수"  # node-2

    def test_delete_graph(self, mock_neo4j_store, mock_chroma_store):
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        builder.delete_graph("graph_123")

        mock_neo4j_store.delete_graph.assert_called_once_with("graph_123")
        mock_chroma_store.delete_graph_data.assert_called_once_with("graph_123")

    def test_build_graph_async_태스크_생성(self, mock_neo4j_store, mock_chroma_store, sample_ontology):
        """비동기 빌드가 태스크를 생성하는지 확인"""
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        task_id = builder.build_graph_async(
            text="테스트 텍스트" * 100,
            ontology=sample_ontology,
            graph_name="테스트"
        )

        assert task_id is not None
        # 태스크가 생성되었는지 확인
        task = builder.task_manager.get_task(task_id)
        assert task is not None
        assert task.task_type == "graph_build"

    def test_build_chroma_index(self, mock_neo4j_store, mock_chroma_store, sample_nodes, sample_edges):
        """ChromaDB 인덱싱 호출 확인"""
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        builder._build_chroma_index("graph_test")

        mock_chroma_store.index_nodes_batch.assert_called_once()
        mock_chroma_store.index_edges_batch.assert_called_once()

    def test_get_graph_info(self, mock_neo4j_store, mock_chroma_store):
        """그래프 정보 조회"""
        builder = self._create_builder(mock_neo4j_store, mock_chroma_store)
        info = builder._get_graph_info("graph_test")

        assert isinstance(info, GraphInfo)
        assert info.graph_id == "graph_test"
        assert info.node_count == 5
        assert info.edge_count == 3
        # Entity, Node 제외한 타입만
        assert "Student" in info.entity_types
        assert "Professor" in info.entity_types


class TestGraphInfo:
    """GraphInfo 데이터클래스 테스트"""

    def test_to_dict(self):
        info = GraphInfo(
            graph_id="g1",
            node_count=10,
            edge_count=5,
            entity_types=["Student", "Professor"]
        )
        d = info.to_dict()
        assert d["graph_id"] == "g1"
        assert d["node_count"] == 10
        assert d["edge_count"] == 5
        assert len(d["entity_types"]) == 2
