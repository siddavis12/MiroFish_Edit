"""
5단계 파이프라인 흐름 테스트
전체 워크플로우를 mock으로 처음부터 끝까지 시뮬레이션
"""

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from app.services.graph_store import NodeData, EdgeData, ExtractionResult
from app.services.entity_reader import EntityNode, FilteredEntities
from app.models.task import TaskManager, TaskStatus


class TestPipelineFlow:
    """5단계 파이프라인 전체 흐름 테스트"""

    def test_step1_온톨로지_생성(self, client, sample_ontology):
        """Step1: 파일 업로드 + 온톨로지 생성"""
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph.OntologyGenerator") as MockOG, \
             patch("app.api.graph.FileParser") as MockFP, \
             patch("app.api.graph.TextProcessor") as MockTP:

            # ProjectManager mock
            mock_project = MagicMock()
            mock_project.project_id = "proj_pipeline"
            mock_project.name = "pipeline test"
            mock_project.files = []
            mock_project.total_text_length = 0
            mock_project.ontology = None
            mock_project.analysis_summary = ""
            mock_project.status = MagicMock()
            mock_project.to_dict.return_value = {"project_id": "proj_pipeline"}
            MockPM.create_project.return_value = mock_project
            MockPM.save_file_to_project.return_value = {
                "original_filename": "doc.txt", "saved_filename": "a.txt",
                "path": "/tmp/a.txt", "size": 500
            }

            # FileParser, TextProcessor mock
            MockFP.extract_text.return_value = "추출된 문서 텍스트"
            MockTP.preprocess_text.return_value = "추출된 문서 텍스트"

            # OntologyGenerator mock
            mock_gen = MagicMock()
            mock_gen.generate.return_value = sample_ontology
            MockOG.return_value = mock_gen

            resp = client.post(
                "/api/graph/ontology/generate",
                data={
                    "files": (BytesIO(b"content"), "doc.txt"),
                    "simulation_requirement": "학술 부정 여론",
                    "project_name": "pipeline test"
                },
                content_type="multipart/form-data"
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert "ontology" in data["data"]

    def test_step1_그래프_구축(self, client, sample_ontology):
        """Step1: 그래프 구축 시작"""
        with patch("app.api.graph.ProjectManager") as MockPM, \
             patch("app.api.graph._get_builder") as mock_get_builder:

            from app.models.project import ProjectStatus

            mock_project = MagicMock()
            mock_project.project_id = "proj_pipeline"
            mock_project.status = ProjectStatus.ONTOLOGY_GENERATED
            mock_project.ontology = sample_ontology
            mock_project.chunk_size = 500
            mock_project.chunk_overlap = 50
            mock_project.name = "pipeline test"
            mock_project.graph_build_task_id = None
            MockPM.get_project.return_value = mock_project
            MockPM.get_extracted_text.return_value = "텍스트"

            mock_builder = MagicMock()
            mock_builder.build_graph_async.return_value = "task_build_1"
            mock_get_builder.return_value = mock_builder

            resp = client.post("/api/graph/build", json={"project_id": "proj_pipeline"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            assert "task_id" in data["data"]

    def test_step2_시뮬레이션_생성(self, client):
        """Step2: 시뮬레이션 생성"""
        with patch("app.api.simulation.ProjectManager") as MockPM, \
             patch("app.api.simulation.SimulationManager") as MockSM:

            mock_project = MagicMock()
            mock_project.graph_id = "graph_pipeline"
            MockPM.get_project.return_value = mock_project

            mock_state = MagicMock()
            mock_state.to_dict.return_value = {
                "simulation_id": "sim_pipeline", "status": "created",
                "project_id": "proj_pipeline", "graph_id": "graph_pipeline"
            }
            mock_manager = MagicMock()
            mock_manager.create_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            resp = client.post(
                "/api/simulation/create",
                json={"project_id": "proj_pipeline", "graph_id": "graph_pipeline"}
            )
            assert resp.status_code == 200

    def test_step3_시뮬레이션_시작(self, client):
        """Step3: 시뮬레이션 시작"""
        from app.services.simulation_manager import SimulationStatus

        with patch("app.api.simulation.SimulationManager") as MockSM, \
             patch("app.api.simulation.SimulationRunner") as MockSR, \
             patch("app.api.simulation._check_simulation_prepared") as mock_check, \
             patch("app.api.simulation.ProjectManager") as MockPM:

            mock_state = MagicMock()
            mock_state.simulation_id = "sim_pipeline"
            mock_state.status = SimulationStatus.READY
            mock_state.graph_id = "graph_pipeline"
            mock_state.project_id = "proj_pipeline"

            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            mock_run_state = MagicMock()
            mock_run_state.to_dict.return_value = {
                "runner_status": "running", "simulation_id": "sim_pipeline"
            }
            MockSR.start_simulation.return_value = mock_run_state

            resp = client.post(
                "/api/simulation/start",
                json={"simulation_id": "sim_pipeline", "platform": "parallel", "max_rounds": 10}
            )
            assert resp.status_code == 200

    def test_step5_ReportAgent_대화(self, client):
        """Step5: ReportAgent와 대화"""
        with patch("app.api.report.SimulationManager") as MockSM, \
             patch("app.api.report.ProjectManager") as MockPM, \
             patch("app.api.report.ReportAgent") as MockRA:

            mock_state = MagicMock()
            mock_state.graph_id = "graph_pipeline"
            mock_state.project_id = "proj_pipeline"
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            mock_project = MagicMock()
            mock_project.simulation_requirement = "학술 부정 여론"
            MockPM.get_project.return_value = mock_project

            mock_agent = MagicMock()
            mock_agent.chat.return_value = {
                "response": "시뮬레이션 결과에 따르면...",
                "tool_calls": [],
                "sources": []
            }
            MockRA.return_value = mock_agent

            resp = client.post(
                "/api/report/chat",
                json={
                    "simulation_id": "sim_pipeline",
                    "message": "시뮬레이션 결과를 요약해줘"
                }
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True


class TestSimulationRunnerForceRestart:
    """시뮬레이션 force 재시작 테스트 (이전 버그 수정 검증)"""

    def test_force_재시작_시_기존_프로세스_정리(self, tmp_path):
        """force=True일 때 기존 실행 중인 시뮬레이션이 정리되는지"""
        from app.services.simulation_runner import SimulationRunner, RunnerStatus

        tmp_dir = str(tmp_path)

        with patch.object(SimulationRunner, "RUN_STATE_DIR", tmp_dir), \
             patch.object(SimulationRunner, "SCRIPTS_DIR", tmp_dir):

            sim_id = "sim_force_test"
            sim_dir = os.path.join(tmp_dir, sim_id)
            os.makedirs(sim_dir, exist_ok=True)

            # 설정 파일 생성
            config = {
                "time_config": {"total_simulation_hours": 24, "minutes_per_round": 30},
                "platform_configs": {}
            }
            with open(os.path.join(sim_dir, "simulation_config.json"), "w") as f:
                json.dump(config, f)

            # 기존 run_state 생성 (RUNNING 상태)
            run_state = {
                "simulation_id": sim_id,
                "runner_status": "running",
                "total_rounds": 48,
            }
            with open(os.path.join(sim_dir, "run_state.json"), "w") as f:
                json.dump(run_state, f)

            # 스크립트 파일 mock
            script_path = os.path.join(tmp_dir, "run_parallel_simulation.py")
            with open(script_path, "w") as f:
                f.write("# mock script")

            # force=True로 start_simulation 호출
            # builtins.open도 mock하여 simulation.log 파일 핸들 문제 방지 (Windows)
            original_open = open
            mock_log_file = MagicMock()

            def patched_open(path, *args, **kwargs):
                if isinstance(path, str) and "simulation.log" in path:
                    return mock_log_file
                return original_open(path, *args, **kwargs)

            with patch.object(SimulationRunner, "_processes", {}), \
                 patch.object(SimulationRunner, "_graph_memory_enabled", {}), \
                 patch.object(SimulationRunner, "_stdout_files", {}), \
                 patch.object(SimulationRunner, "_stderr_files", {}), \
                 patch("app.services.simulation_runner.GraphMemoryManager") as MockGMM, \
                 patch("subprocess.Popen") as MockPopen, \
                 patch.object(SimulationRunner, "cleanup_simulation_logs", return_value={"success": True}), \
                 patch("builtins.open", side_effect=patched_open):

                mock_proc = MagicMock()
                mock_proc.pid = 12345
                mock_proc.poll.return_value = None
                MockPopen.return_value = mock_proc

                result = SimulationRunner.start_simulation(
                    simulation_id=sim_id,
                    platform="parallel",
                    max_rounds=10,
                    force=True
                )

                assert result is not None
                assert result.simulation_id == sim_id
                # cleanup_simulation_logs가 호출되었는지 확인
                SimulationRunner.cleanup_simulation_logs.assert_called_once_with(sim_id)

    def test_force_없이_이미_실행중이면_에러(self):
        """force=False인데 이미 실행 중이면 ValueError"""
        from app.services.simulation_runner import SimulationRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(SimulationRunner, "RUN_STATE_DIR", tmp_dir):
                sim_id = "sim_dup_test"
                sim_dir = os.path.join(tmp_dir, sim_id)
                os.makedirs(sim_dir, exist_ok=True)

                config = {"time_config": {"total_simulation_hours": 24, "minutes_per_round": 30}}
                with open(os.path.join(sim_dir, "simulation_config.json"), "w") as f:
                    json.dump(config, f)

                run_state = {"simulation_id": sim_id, "runner_status": "running", "total_rounds": 48}
                with open(os.path.join(sim_dir, "run_state.json"), "w") as f:
                    json.dump(run_state, f)

                with pytest.raises(ValueError, match="이미 실행 중"):
                    SimulationRunner.start_simulation(
                        simulation_id=sim_id,
                        platform="parallel",
                        force=False
                    )
