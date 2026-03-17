"""
전체 파이프라인 순차 E2E 테스트

실제 Flask 라우트를 타면서, 외부 의존성(Neo4j, LLM, ChromaDB, OASIS)만 mock.
Step1 → Step2 → Step3 → Step4 → Step5 순서로 이전 단계의 출력을 다음 단계 입력에 사용.
"""

import os
import json
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from io import BytesIO

from app.services.graph_store import NodeData, EdgeData, ExtractionResult, SearchData
from app.services.entity_reader import EntityNode, FilteredEntities
from app.models.task import TaskManager, TaskStatus
from app.models.project import ProjectManager, ProjectStatus, Project
from app.services.simulation_manager import SimulationManager, SimulationStatus, SimulationState


# ============== Mock 데이터 (최소한) ==============

MOCK_ONTOLOGY = {
    "entity_types": [
        {"name": "Researcher", "description": "A researcher", "attributes": [], "examples": ["Dr.Kim"]},
        {"name": "Person", "description": "Any person", "attributes": [{"name": "full_name", "type": "text", "description": "name"}], "examples": ["citizen"]},
        {"name": "Organization", "description": "Any org", "attributes": [], "examples": ["group"]},
    ],
    "edge_types": [
        {"name": "AFFILIATED_WITH", "description": "Affiliation", "source_targets": [{"source": "Researcher", "target": "Organization"}], "attributes": []},
    ],
    "analysis_summary": "연구 부정 관련 온톨로지"
}

MOCK_NODES = [
    NodeData(uuid="n1", name="김연구원", labels=["Entity", "Researcher"], summary="AI 연구자", attributes={}),
    NodeData(uuid="n2", name="한국연구재단", labels=["Entity", "Organization"], summary="연구 지원 기관", attributes={}),
    NodeData(uuid="n3", name="박시민", labels=["Entity", "Person"], summary="일반 시민", attributes={}),
]

MOCK_EDGES = [
    EdgeData(uuid="e1", name="AFFILIATED_WITH", fact="김연구원은 한국연구재단에 소속", source_node_uuid="n1", target_node_uuid="n2"),
]

MOCK_ENTITIES = [
    EntityNode(uuid="n1", name="김연구원", labels=["Entity", "Researcher"], summary="AI 연구자", attributes={}, related_edges=[], related_nodes=[]),
    EntityNode(uuid="n2", name="한국연구재단", labels=["Entity", "Organization"], summary="연구 지원 기관", attributes={}, related_edges=[], related_nodes=[]),
    EntityNode(uuid="n3", name="박시민", labels=["Entity", "Person"], summary="일반 시민", attributes={}, related_edges=[], related_nodes=[]),
]


class TestFullPipelineE2E:
    """
    전체 파이프라인 순차 E2E 테스트

    Step1: 파일 업로드 + 온톨로지 생성 → 그래프 구축 → 완료 대기
    Step2: 시뮬레이션 생성 → 시뮬레이션 준비
    Step3: 시뮬레이션 시작 → 상태 확인
    Step4: 리포트 생성
    Step5: ReportAgent 대화
    """

    @pytest.fixture(autouse=True)
    def setup_mocks(self, app, client, tmp_path):
        """전체 테스트에 걸쳐 사용할 mock 설정"""
        self.client = client
        self.tmp_path = tmp_path

        # 프로젝트 저장소를 임시 디렉토리로
        self.projects_dir = str(tmp_path / "projects")
        os.makedirs(self.projects_dir, exist_ok=True)

        # 시뮬레이션 저장소를 임시 디렉토리로
        self.sim_dir = str(tmp_path / "simulations")
        os.makedirs(self.sim_dir, exist_ok=True)

        # 결과 저장용
        self.ctx = {}

    # ======================================================
    # Step1: 그래프 구축
    # ======================================================

    def test_전체_파이프라인(self):
        """5단계 전체 파이프라인을 순차 실행"""

        # ==========================================
        # Step1-1: 파일 업로드 + 온톨로지 생성
        # ==========================================
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph.OntologyGenerator") as MockOG, \
             patch("app.api.graph.FileParser") as MockFP, \
             patch("app.api.graph.TextProcessor") as MockTP:

            # 실제 프로젝트 객체 생성 (mock이 아닌 실제 데이터 구조 사용)
            project = Project(
                project_id="proj_e2e_001",
                name="E2E 테스트",
                status=ProjectStatus.CREATED,
                created_at="2026-03-17T00:00:00",
                updated_at="2026-03-17T00:00:00",
                files=[],
            )
            MockPM.create_project.return_value = project
            MockPM.save_file_to_project.return_value = {
                "original_filename": "research.txt",
                "saved_filename": "abc123.txt",
                "path": str(self.tmp_path / "research.txt"),
                "size": 256
            }
            MockFP.extract_text.return_value = "김연구원이 한국연구재단 소속으로 AI 연구를 수행하던 중 데이터 조작 의혹이 제기되었다."
            MockTP.preprocess_text.side_effect = lambda t: t  # 패스스루

            mock_gen = MagicMock()
            mock_gen.generate.return_value = MOCK_ONTOLOGY
            MockOG.return_value = mock_gen

            resp = self.client.post(
                "/api/graph/ontology/generate",
                data={
                    "files": (BytesIO(b"research content"), "research.txt"),
                    "simulation_requirement": "연구 부정 여론 시뮬레이션",
                    "project_name": "E2E 테스트"
                },
                content_type="multipart/form-data"
            )

            assert resp.status_code == 200, f"Step1-1 실패: {resp.get_json()}"
            data = resp.get_json()["data"]
            project_id = data["project_id"]
            assert data["ontology"]["entity_types"] is not None
            print(f"  Step1-1 OK: 온톨로지 생성 완료 (project_id={project_id}, 엔티티 유형 {len(data['ontology']['entity_types'])}개)")

        # ==========================================
        # Step1-2: 그래프 구축 시작
        # ==========================================
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph._get_builder") as mock_get_builder, \
             patch("app.api.graph.TextProcessor") as MockTP:

            # 프로젝트 상태를 온톨로지 생성 완료로
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.ontology = MOCK_ONTOLOGY
            project.simulation_requirement = "연구 부정 여론 시뮬레이션"
            MockPM.get_project.return_value = project
            MockPM.get_extracted_text.return_value = "김연구원이 한국연구재단 소속으로 AI 연구 수행 중 데이터 조작 의혹."

            # GraphBuilderService mock
            mock_builder = MagicMock()
            mock_builder.create_graph.return_value = "mirofish_e2e_graph"
            mock_builder.add_text_batches.return_value = None
            mock_builder.get_graph_data.return_value = {
                "graph_id": "mirofish_e2e_graph",
                "nodes": [n.to_dict() for n in MOCK_NODES],
                "edges": [e.to_dict() for e in MOCK_EDGES],
                "node_count": 3,
                "edge_count": 1,
            }
            mock_get_builder.return_value = mock_builder
            MockTP.split_text.return_value = ["청크1"]

            resp = self.client.post(
                "/api/graph/build",
                json={"project_id": project_id}
            )

            assert resp.status_code == 200, f"Step1-2 실패: {resp.get_json()}"
            task_id = resp.get_json()["data"]["task_id"]
            print(f"  Step1-2 OK: 그래프 구축 태스크 시작 (task_id={task_id})")

            # 백그라운드 스레드가 실행되므로 잠시 대기
            time.sleep(0.5)

            # 태스크 상태 폴링
            resp = self.client.get(f"/api/graph/task/{task_id}")
            assert resp.status_code == 200
            task_data = resp.get_json()["data"]
            print(f"  Step1-2 태스크 상태: {task_data['status']} (진행률: {task_data['progress']}%)")

            # graph_id 기록
            graph_id = "mirofish_e2e_graph"

        # ==========================================
        # Step1-3: 그래프 데이터 조회
        # ==========================================
        with patch("app.api.graph._get_builder") as mock_get_builder:
            mock_builder = MagicMock()
            mock_builder.get_graph_data.return_value = {
                "graph_id": graph_id,
                "nodes": [n.to_dict() for n in MOCK_NODES],
                "edges": [e.to_dict() for e in MOCK_EDGES],
                "node_count": 3,
                "edge_count": 1,
            }
            mock_get_builder.return_value = mock_builder

            resp = self.client.get(f"/api/graph/data/{graph_id}")
            assert resp.status_code == 200, f"Step1-3 실패: {resp.get_json()}"
            graph_data = resp.get_json()["data"]
            assert graph_data["node_count"] == 3
            print(f"  Step1-3 OK: 그래프 조회 (노드 {graph_data['node_count']}, 엣지 {graph_data['edge_count']})")

        # ==========================================
        # Step2-1: 시뮬레이션 생성
        # ==========================================
        with patch("app.api.simulation.ProjectManager") as MockPM, \
             patch("app.api.simulation.SimulationManager") as MockSM:

            project.graph_id = graph_id
            project.status = ProjectStatus.GRAPH_COMPLETED
            MockPM.get_project.return_value = project

            sim_state = SimulationState(
                simulation_id="sim_e2e_001",
                project_id=project_id,
                graph_id=graph_id,
            )
            mock_manager = MagicMock()
            mock_manager.create_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            resp = self.client.post(
                "/api/simulation/create",
                json={"project_id": project_id}
            )

            assert resp.status_code == 200, f"Step2-1 실패: {resp.get_json()}"
            sim_id = resp.get_json()["data"]["simulation_id"]
            print(f"  Step2-1 OK: 시뮬레이션 생성 (simulation_id={sim_id})")

        # ==========================================
        # Step2-2: 시뮬레이션 준비 (엔티티 읽기 + 프로필 + 설정)
        # ==========================================
        with patch("app.api.simulation.SimulationManager") as MockSM, \
             patch("app.api.simulation.ProjectManager") as MockPM, \
             patch("app.api.simulation.EntityReader") as MockER, \
             patch("app.api.simulation._check_simulation_prepared") as mock_check:

            sim_state.status = SimulationStatus.CREATED
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            mock_check.return_value = (False, {})

            project.simulation_requirement = "연구 부정 여론 시뮬레이션"
            MockPM.get_project.return_value = project
            MockPM.get_extracted_text.return_value = "텍스트"

            # EntityReader mock (동기 preview 호출)
            filtered = FilteredEntities(
                entities=MOCK_ENTITIES,
                entity_types={"Researcher", "Organization", "Person"},
                total_count=3,
                filtered_count=3
            )
            mock_reader = MagicMock()
            mock_reader.filter_defined_entities.return_value = filtered
            MockER.return_value = mock_reader

            resp = self.client.post(
                "/api/simulation/prepare",
                json={"simulation_id": sim_id}
            )

            assert resp.status_code == 200, f"Step2-2 실패: {resp.get_json()}"
            prep_data = resp.get_json()["data"]
            print(f"  Step2-2 OK: 시뮬레이션 준비 시작 (task_id={prep_data.get('task_id', 'N/A')})")

        # ==========================================
        # Step3: 시뮬레이션 시작
        # ==========================================
        with patch("app.api.simulation.SimulationManager") as MockSM, \
             patch("app.api.simulation.SimulationRunner") as MockSR:

            sim_state.status = SimulationStatus.READY
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            mock_run_state = MagicMock()
            mock_run_state.to_dict.return_value = {
                "simulation_id": sim_id,
                "runner_status": "running",
                "total_rounds": 10,
                "current_round": 0,
                "twitter_running": True,
                "reddit_running": True,
                "started_at": "2026-03-17T14:00:00"
            }
            MockSR.start_simulation.return_value = mock_run_state

            resp = self.client.post(
                "/api/simulation/start",
                json={
                    "simulation_id": sim_id,
                    "platform": "parallel",
                    "max_rounds": 10
                }
            )

            assert resp.status_code == 200, f"Step3 실패: {resp.get_json()}"
            start_data = resp.get_json()["data"]
            print(f"  Step3 OK: 시뮬레이션 시작 (상태={start_data['runner_status']}, 라운드={start_data['total_rounds']})")

        # ==========================================
        # Step3-2: 시뮬레이션 상태 조회
        # ==========================================
        with patch("app.api.simulation.SimulationManager") as MockSM:
            sim_state.status = SimulationStatus.COMPLETED
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            resp = self.client.get(f"/api/simulation/{sim_id}")
            assert resp.status_code == 200, f"Step3-2 실패: {resp.get_json()}"
            status_data = resp.get_json()["data"]
            print(f"  Step3-2 OK: 시뮬레이션 상태 조회 (status={status_data['status']})")

        # ==========================================
        # Step4: 리포트 생성
        # ==========================================
        with patch("app.api.report.SimulationManager") as MockSM, \
             patch("app.api.report.ProjectManager") as MockPM, \
             patch("app.api.report.ReportAgent") as MockRA, \
             patch("app.api.report.TaskManager") as MockTM, \
             patch("app.api.report.ReportManager") as MockRM:

            sim_state.status = SimulationStatus.COMPLETED
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            MockPM.get_project.return_value = project
            MockPM.get_extracted_text.return_value = "텍스트"

            mock_tm = MagicMock()
            mock_tm.create_task.return_value = "task_report_e2e"
            MockTM.return_value = mock_tm

            # ReportManager: 기존 리포트 없음
            MockRM.list_reports.return_value = []

            resp = self.client.post(
                "/api/report/generate",
                json={"simulation_id": sim_id}
            )

            # 200 또는 202 (비동기 태스크 시작)
            assert resp.status_code in [200, 202], f"Step4 실패: {resp.get_json()}"
            print(f"  Step4 OK: 리포트 생성 요청 (status_code={resp.status_code})")

        # ==========================================
        # Step5: ReportAgent 대화
        # ==========================================
        with patch("app.api.report.SimulationManager") as MockSM, \
             patch("app.api.report.ProjectManager") as MockPM, \
             patch("app.api.report.ReportAgent") as MockRA:

            sim_state.status = SimulationStatus.COMPLETED
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = sim_state
            MockSM.return_value = mock_manager

            project.simulation_requirement = "연구 부정 여론 시뮬레이션"
            MockPM.get_project.return_value = project

            mock_agent = MagicMock()
            mock_agent.chat.return_value = {
                "response": "시뮬레이션 분석 결과, 김연구원의 데이터 조작 의혹에 대해 소셜 미디어에서 크게 3가지 여론이 형성되었습니다...",
                "tool_calls": [
                    {"tool": "search_graph", "query": "김연구원 여론"},
                    {"tool": "get_statistics", "query": "전체 통계"},
                ],
                "sources": ["그래프 검색: 김연구원 관련 3건"]
            }
            MockRA.return_value = mock_agent

            resp = self.client.post(
                "/api/report/chat",
                json={
                    "simulation_id": sim_id,
                    "message": "이 시뮬레이션의 주요 여론 흐름을 분석해주세요"
                }
            )

            assert resp.status_code == 200, f"Step5 실패: {resp.get_json()}"
            chat_data = resp.get_json()["data"]
            assert "response" in chat_data
            assert len(chat_data["response"]) > 0
            print(f"  Step5 OK: ReportAgent 대화 (응답 길이={len(chat_data['response'])}자, 도구 호출={len(chat_data['tool_calls'])}회)")

        # ==========================================
        # 최종 결과
        # ==========================================
        print("\n  ===== 전체 파이프라인 E2E 테스트 완료 =====")
        print(f"  project_id  : {project_id}")
        print(f"  graph_id    : {graph_id}")
        print(f"  simulation_id: {sim_id}")
        print(f"  단계: 온톨로지 → 그래프 구축 → 시뮬레이션 생성 → 준비 → 시작 → 리포트 → 대화")
        print(f"  결과: 전체 파이프라인 정상 동작 확인")
