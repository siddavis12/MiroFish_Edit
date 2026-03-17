"""
Graph API 통합 테스트
Flask 테스트 클라이언트로 그래프 API 엔드포인트 테스트
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from app.services.graph_store import NodeData, EdgeData


class TestGraphProjectAPI:
    """프로젝트 관리 API 테스트"""

    def test_프로젝트_조회(self, client):
        """GET /api/graph/project/<id>"""
        with patch("app.api.graph.ProjectManager") as MockPM:
            mock_project = MagicMock()
            mock_project.to_dict.return_value = {
                "project_id": "proj_1", "name": "test", "status": "created"
            }
            MockPM.get_project.return_value = mock_project

            response = client.get("/api/graph/project/proj_1")
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

    def test_존재하지_않는_프로젝트_조회(self, client):
        """GET /api/graph/project/<id> - 404"""
        with patch("app.api.graph.ProjectManager") as MockPM:
            MockPM.get_project.return_value = None
            response = client.get("/api/graph/project/nonexistent")
            assert response.status_code == 404

    def test_프로젝트_삭제(self, client):
        """DELETE /api/graph/project/<id>"""
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph._get_builder") as mock_get_builder:

            mock_project = MagicMock()
            mock_project.graph_id = "graph_1"
            MockPM.get_project.return_value = mock_project
            MockPM.delete_project.return_value = True

            mock_builder = MagicMock()
            mock_get_builder.return_value = mock_builder

            response = client.delete("/api/graph/project/proj_1")
            assert response.status_code == 200
            result = response.get_json()
            assert result["success"] is True

    def test_프로젝트_목록_조회(self, client):
        """GET /api/graph/project/list"""
        with patch("app.api.graph.ProjectManager") as MockPM:
            mock_p1 = MagicMock()
            mock_p1.to_dict.return_value = {"project_id": "proj_1", "name": "p1"}
            mock_p2 = MagicMock()
            mock_p2.to_dict.return_value = {"project_id": "proj_2", "name": "p2"}
            MockPM.list_projects.return_value = [mock_p1, mock_p2]

            response = client.get("/api/graph/project/list")
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]) == 2


class TestOntologyAPI:
    """온톨로지 생성 API 테스트 (multipart/form-data)"""

    def test_온톨로지_생성_요구사항_누락(self, client):
        """POST /api/graph/ontology/generate - simulation_requirement 누락 시 400"""
        response = client.post(
            "/api/graph/ontology/generate",
            data={"project_name": "test"},
            content_type="multipart/form-data"
        )
        assert response.status_code == 400

    def test_온톨로지_생성_파일_없이(self, client):
        """POST /api/graph/ontology/generate - 파일 없이 요청 시 400"""
        response = client.post(
            "/api/graph/ontology/generate",
            data={"simulation_requirement": "여론 시뮬레이션"},
            content_type="multipart/form-data"
        )
        assert response.status_code == 400

    def test_온톨로지_생성_정상(self, client, sample_ontology):
        """POST /api/graph/ontology/generate - 정상 흐름"""
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph.OntologyGenerator") as MockOG, \
             patch("app.api.graph.FileParser") as MockFP, \
             patch("app.api.graph.TextProcessor") as MockTP:

            mock_project = MagicMock()
            mock_project.project_id = "proj_test"
            mock_project.name = "테스트"
            mock_project.files = []
            mock_project.total_text_length = 0
            mock_project.ontology = None
            mock_project.analysis_summary = ""
            MockPM.create_project.return_value = mock_project
            MockPM.save_file_to_project.return_value = {
                "original_filename": "test.txt",
                "saved_filename": "a.txt",
                "path": "/tmp/a.txt",
                "size": 100
            }

            MockFP.extract_text.return_value = "추출된 텍스트"
            MockTP.preprocess_text.return_value = "추출된 텍스트"

            mock_gen = MagicMock()
            mock_gen.generate.return_value = sample_ontology
            MockOG.return_value = mock_gen

            response = client.post(
                "/api/graph/ontology/generate",
                data={
                    "files": (BytesIO(b"test content"), "test.txt"),
                    "simulation_requirement": "여론 시뮬레이션",
                    "project_name": "테스트"
                },
                content_type="multipart/form-data"
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "ontology" in data["data"]


class TestGraphBuildAPI:
    """그래프 구축 API 테스트"""

    def test_그래프_구축_시작(self, client, sample_ontology):
        """POST /api/graph/build"""
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph._get_builder") as mock_get_builder:

            mock_project = MagicMock()
            mock_project.project_id = "proj_1"
            mock_project.status = MagicMock(value="ontology_generated")
            mock_project.ontology = sample_ontology
            mock_project.chunk_size = 500
            mock_project.chunk_overlap = 50
            mock_project.name = "test"
            MockPM.get_project.return_value = mock_project
            MockPM.get_extracted_text.return_value = "텍스트 내용"

            mock_builder = MagicMock()
            mock_builder.build_graph_async.return_value = "task_123"
            mock_get_builder.return_value = mock_builder

            response = client.post(
                "/api/graph/build",
                json={"project_id": "proj_1"}
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "task_id" in data["data"]

    def test_그래프_데이터_조회(self, client, sample_nodes, sample_edges):
        """GET /api/graph/data/<graph_id>"""
        with patch("app.api.graph._get_builder") as mock_get_builder:
            mock_builder = MagicMock()
            mock_builder.get_graph_data.return_value = {
                "graph_id": "graph_1",
                "nodes": [n.to_dict() for n in sample_nodes],
                "edges": [e.to_dict() for e in sample_edges],
                "node_count": len(sample_nodes),
                "edge_count": len(sample_edges),
            }
            mock_get_builder.return_value = mock_builder

            response = client.get("/api/graph/data/graph_1")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["node_count"] == len(sample_nodes)

    def test_태스크_상태_조회(self, client):
        """GET /api/graph/task/<task_id>"""
        from app.models.task import TaskManager, TaskStatus

        tm = TaskManager()
        task_id = tm.create_task("graph_build")
        tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=50)

        response = client.get(f"/api/graph/task/{task_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["progress"] == 50

    def test_그래프_삭제(self, client):
        """DELETE /api/graph/delete/<graph_id>"""
        with patch("app.api.graph._get_builder") as mock_get_builder:
            mock_builder = MagicMock()
            mock_get_builder.return_value = mock_builder

            response = client.delete("/api/graph/delete/graph_1")
            assert response.status_code == 200
            mock_builder.delete_graph.assert_called_once_with("graph_1")
