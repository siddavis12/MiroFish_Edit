"""
ProjectManager 단위 테스트
파일시스템 기반 프로젝트 CRUD 테스트
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from app.models.project import Project, ProjectManager, ProjectStatus


class TestProject:
    """Project 데이터 모델 테스트"""

    def test_to_dict(self):
        p = Project(
            project_id="proj_1", name="테스트",
            status=ProjectStatus.CREATED,
            created_at="2026-03-17T00:00:00",
            updated_at="2026-03-17T00:00:00",
        )
        d = p.to_dict()
        assert d["project_id"] == "proj_1"
        assert d["status"] == "created"
        assert d["chunk_size"] == 500

    def test_from_dict_왕복변환(self):
        original = Project(
            project_id="proj_1", name="테스트",
            status=ProjectStatus.ONTOLOGY_GENERATED,
            created_at="2026-03-17T00:00:00",
            updated_at="2026-03-17T00:00:00",
            graph_id="graph_1",
            total_text_length=5000,
            chunk_size=300,
            chunk_overlap=30,
        )

        d = original.to_dict()
        restored = Project.from_dict(d)

        assert restored.project_id == original.project_id
        assert restored.status == original.status
        assert restored.graph_id == original.graph_id
        assert restored.chunk_size == 300

    def test_from_dict_상태_문자열_변환(self):
        d = {
            "project_id": "proj_1", "name": "test",
            "status": "graph_completed",
            "created_at": "", "updated_at": "",
        }
        p = Project.from_dict(d)
        assert p.status == ProjectStatus.GRAPH_COMPLETED


class TestProjectManager:
    """ProjectManager CRUD 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """임시 디렉토리로 PROJECTS_DIR 교체"""
        self.projects_dir = str(tmp_path / "projects")
        with patch.object(ProjectManager, "PROJECTS_DIR", self.projects_dir):
            yield

    def test_프로젝트_생성(self):
        p = ProjectManager.create_project("테스트 프로젝트")
        assert p.project_id.startswith("proj_")
        assert p.name == "테스트 프로젝트"
        assert p.status == ProjectStatus.CREATED

        # 디렉토리 구조 확인
        assert os.path.exists(os.path.join(self.projects_dir, p.project_id))
        assert os.path.exists(os.path.join(self.projects_dir, p.project_id, "files"))

    def test_프로젝트_조회(self):
        p = ProjectManager.create_project("테스트")
        loaded = ProjectManager.get_project(p.project_id)
        assert loaded is not None
        assert loaded.name == "테스트"

    def test_존재하지_않는_프로젝트_조회(self):
        assert ProjectManager.get_project("nonexistent") is None

    def test_프로젝트_저장_업데이트(self):
        p = ProjectManager.create_project("테스트")
        p.status = ProjectStatus.ONTOLOGY_GENERATED
        p.ontology = {"entity_types": []}
        ProjectManager.save_project(p)

        loaded = ProjectManager.get_project(p.project_id)
        assert loaded.status == ProjectStatus.ONTOLOGY_GENERATED
        assert loaded.ontology is not None

    def test_프로젝트_삭제(self):
        p = ProjectManager.create_project("삭제 테스트")
        pid = p.project_id

        assert ProjectManager.delete_project(pid) is True
        assert ProjectManager.get_project(pid) is None
        assert not os.path.exists(os.path.join(self.projects_dir, pid))

    def test_존재하지_않는_프로젝트_삭제(self):
        assert ProjectManager.delete_project("nonexistent") is False

    def test_프로젝트_목록_조회(self):
        ProjectManager.create_project("프로젝트 1")
        ProjectManager.create_project("프로젝트 2")
        ProjectManager.create_project("프로젝트 3")

        projects = ProjectManager.list_projects()
        assert len(projects) == 3

    def test_프로젝트_목록_제한(self):
        for i in range(5):
            ProjectManager.create_project(f"프로젝트 {i}")

        projects = ProjectManager.list_projects(limit=3)
        assert len(projects) == 3

    def test_추출_텍스트_저장_조회(self):
        p = ProjectManager.create_project("텍스트 테스트")

        ProjectManager.save_extracted_text(p.project_id, "추출된 텍스트 내용")
        text = ProjectManager.get_extracted_text(p.project_id)
        assert text == "추출된 텍스트 내용"

    def test_추출_텍스트_없는_경우(self):
        p = ProjectManager.create_project("빈 프로젝트")
        assert ProjectManager.get_extracted_text(p.project_id) is None

    def test_프로젝트_파일_목록(self):
        p = ProjectManager.create_project("파일 테스트")
        # 빈 프로젝트
        files = ProjectManager.get_project_files(p.project_id)
        assert files == []
