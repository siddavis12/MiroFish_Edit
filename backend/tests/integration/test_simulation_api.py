"""
Simulation API 통합 테스트
Flask 테스트 클라이언트로 시뮬레이션 API 엔드포인트 테스트
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.simulation_manager import SimulationStatus


class TestSimulationCreateAPI:
    """시뮬레이션 생성/조회 API 테스트"""

    def test_시뮬레이션_생성(self, client):
        """POST /api/simulation/create"""
        with patch("app.api.simulation.ProjectManager") as MockPM, \
             patch("app.api.simulation.SimulationManager") as MockSM:

            mock_project = MagicMock()
            mock_project.graph_id = "graph_1"
            MockPM.get_project.return_value = mock_project

            mock_state = MagicMock()
            mock_state.to_dict.return_value = {
                "simulation_id": "sim_test", "status": "created",
                "project_id": "proj_1", "graph_id": "graph_1",
            }
            mock_manager = MagicMock()
            mock_manager.create_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            response = client.post(
                "/api/simulation/create",
                json={
                    "project_id": "proj_1",
                    "graph_id": "graph_1",
                    "enable_twitter": True,
                    "enable_reddit": True
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

    def test_시뮬레이션_생성_필수파라미터_누락(self, client):
        """POST /api/simulation/create - project_id 누락"""
        response = client.post(
            "/api/simulation/create",
            json={"graph_id": "graph_1"}
        )
        assert response.status_code == 400

    def test_시뮬레이션_생성_프로젝트_없음(self, client):
        """POST /api/simulation/create - 프로젝트 미존재"""
        with patch("app.api.simulation.ProjectManager") as MockPM:
            MockPM.get_project.return_value = None

            response = client.post(
                "/api/simulation/create",
                json={"project_id": "nonexistent", "graph_id": "graph_1"}
            )
            assert response.status_code == 404


class TestSimulationPrepareAPI:
    """시뮬레이션 준비 API 테스트"""

    def test_시뮬레이션_준비_시작(self, client):
        """POST /api/simulation/prepare"""
        with patch("app.api.simulation.SimulationManager") as MockSM, \
             patch("app.api.simulation.ProjectManager") as MockPM:

            mock_state = MagicMock()
            mock_state.simulation_id = "sim_test"
            mock_state.project_id = "proj_1"
            mock_state.graph_id = "graph_1"
            mock_state.status = SimulationStatus.CREATED
            mock_state.to_simple_dict.return_value = {"simulation_id": "sim_test", "status": "preparing"}

            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            mock_project = MagicMock()
            mock_project.simulation_requirement = "여론 시뮬레이션"
            MockPM.get_project.return_value = mock_project
            MockPM.get_extracted_text.return_value = "문서 텍스트"

            response = client.post(
                "/api/simulation/prepare",
                json={
                    "simulation_id": "sim_test",
                    "simulation_requirement": "여론 시뮬레이션"
                }
            )

            assert response.status_code == 200


class TestSimulationStartAPI:
    """시뮬레이션 시작/중지 API 테스트"""

    def test_시뮬레이션_시작_존재하지_않음(self, client):
        """POST /api/simulation/start - 존재하지 않는 시뮬레이션"""
        with patch("app.api.simulation.SimulationManager") as MockSM:
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = None
            MockSM.return_value = mock_manager

            response = client.post(
                "/api/simulation/start",
                json={"simulation_id": "nonexistent"}
            )
            assert response.status_code == 404

    def test_시뮬레이션_시작_simulation_id_누락(self, client):
        """POST /api/simulation/start - simulation_id 누락"""
        response = client.post(
            "/api/simulation/start",
            json={}
        )
        assert response.status_code == 400

    def test_시뮬레이션_시작_유효하지_않은_플랫폼(self, client):
        """POST /api/simulation/start - 유효하지 않은 플랫폼"""
        response = client.post(
            "/api/simulation/start",
            json={
                "simulation_id": "sim_test",
                "platform": "invalid_platform"
            }
        )
        assert response.status_code == 400

    def test_시뮬레이션_상태_조회(self, client):
        """GET /api/simulation/<id>"""
        with patch("app.api.simulation.SimulationManager") as MockSM:
            mock_state = MagicMock()
            mock_state.status = SimulationStatus.RUNNING
            mock_state.to_dict.return_value = {"simulation_id": "sim_test", "status": "running"}

            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = mock_state
            MockSM.return_value = mock_manager

            response = client.get("/api/simulation/sim_test")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


class TestSimulationConfigAPI:
    """시뮬레이션 설정 API 테스트"""

    def test_시뮬레이션_설정_조회(self, client):
        """GET /api/simulation/<id>/config"""
        with patch("app.api.simulation.SimulationManager") as MockSM:
            mock_manager = MagicMock()
            mock_manager.get_simulation.return_value = MagicMock()
            mock_manager.get_simulation_config.return_value = {
                "time_config": {"total_simulation_hours": 72}
            }
            MockSM.return_value = mock_manager

            response = client.get("/api/simulation/sim_test/config")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

    def test_시뮬레이션_목록_조회(self, client):
        """GET /api/simulation/list"""
        with patch("app.api.simulation.SimulationManager") as MockSM:
            mock_s1 = MagicMock()
            mock_s1.to_dict.return_value = {"simulation_id": "sim_1", "status": "ready"}
            mock_s2 = MagicMock()
            mock_s2.to_dict.return_value = {"simulation_id": "sim_2", "status": "completed"}

            mock_manager = MagicMock()
            mock_manager.list_simulations.return_value = [mock_s1, mock_s2]
            MockSM.return_value = mock_manager

            response = client.get("/api/simulation/list")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["count"] == 2
