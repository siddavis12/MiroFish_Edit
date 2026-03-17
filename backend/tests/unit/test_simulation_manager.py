"""
SimulationManager 단위 테스트
파일시스템 기반 시뮬레이션 생명주기 관리 테스트
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.simulation_manager import (
    SimulationManager, SimulationState, SimulationStatus, PlatformType
)


class TestSimulationManager:
    """SimulationManager CRUD 테스트"""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """각 테스트에서 임시 디렉토리 사용"""
        self.sim_dir = str(tmp_path / "simulations")
        os.makedirs(self.sim_dir, exist_ok=True)

        with patch.object(SimulationManager, "SIMULATION_DATA_DIR", self.sim_dir):
            self.manager = SimulationManager()
            yield

    def test_시뮬레이션_생성(self):
        state = self.manager.create_simulation(
            project_id="proj_test",
            graph_id="graph_test",
            enable_twitter=True,
            enable_reddit=True
        )

        assert state.simulation_id.startswith("sim_")
        assert state.project_id == "proj_test"
        assert state.graph_id == "graph_test"
        assert state.status == SimulationStatus.CREATED

        # 파일 저장 확인
        state_file = os.path.join(self.sim_dir, state.simulation_id, "state.json")
        assert os.path.exists(state_file)

    def test_시뮬레이션_조회(self):
        state = self.manager.create_simulation("proj_1", "graph_1")

        # 메모리 캐시에서 조회
        loaded = self.manager.get_simulation(state.simulation_id)
        assert loaded is not None
        assert loaded.project_id == "proj_1"

    def test_시뮬레이션_파일에서_복원(self):
        state = self.manager.create_simulation("proj_1", "graph_1")
        sim_id = state.simulation_id

        # 메모리 캐시 초기화
        self.manager._simulations.clear()

        # 파일에서 복원
        loaded = self.manager.get_simulation(sim_id)
        assert loaded is not None
        assert loaded.project_id == "proj_1"

    def test_존재하지_않는_시뮬레이션(self):
        result = self.manager.get_simulation("nonexistent")
        # _get_simulation_dir이 디렉토리를 만들지만 state.json이 없음
        assert result is None

    def test_시뮬레이션_목록_조회(self):
        self.manager.create_simulation("proj_1", "graph_1")
        self.manager.create_simulation("proj_1", "graph_1")
        self.manager.create_simulation("proj_2", "graph_2")

        # 전체 목록
        all_sims = self.manager.list_simulations()
        assert len(all_sims) == 3

        # 프로젝트 필터
        proj1_sims = self.manager.list_simulations(project_id="proj_1")
        assert len(proj1_sims) == 2

    def test_시뮬레이션_설정_조회_없음(self):
        state = self.manager.create_simulation("proj_1", "graph_1")
        config = self.manager.get_simulation_config(state.simulation_id)
        assert config is None

    def test_시뮬레이션_설정_조회_있음(self):
        state = self.manager.create_simulation("proj_1", "graph_1")
        sim_dir = os.path.join(self.sim_dir, state.simulation_id)

        # 설정 파일 직접 생성
        config = {"time_config": {"total_simulation_hours": 72}}
        with open(os.path.join(sim_dir, "simulation_config.json"), "w") as f:
            json.dump(config, f)

        loaded_config = self.manager.get_simulation_config(state.simulation_id)
        assert loaded_config is not None
        assert loaded_config["time_config"]["total_simulation_hours"] == 72

    def test_프로필_조회_비어있음(self):
        state = self.manager.create_simulation("proj_1", "graph_1")
        profiles = self.manager.get_profiles(state.simulation_id, "reddit")
        assert profiles == []

    def test_실행_안내_생성(self):
        state = self.manager.create_simulation("proj_1", "graph_1")
        instructions = self.manager.get_run_instructions(state.simulation_id)

        assert "simulation_dir" in instructions
        assert "scripts_dir" in instructions
        assert "commands" in instructions
        assert "twitter" in instructions["commands"]
        assert "reddit" in instructions["commands"]
        assert "parallel" in instructions["commands"]


class TestSimulationState:
    """SimulationState 데이터 구조 테스트"""

    def test_to_dict(self):
        state = SimulationState(
            simulation_id="sim_test",
            project_id="proj_test",
            graph_id="graph_test",
            status=SimulationStatus.READY,
            entities_count=10,
            profiles_count=10,
        )
        d = state.to_dict()
        assert d["simulation_id"] == "sim_test"
        assert d["status"] == "ready"
        assert d["entities_count"] == 10

    def test_to_simple_dict(self):
        state = SimulationState(
            simulation_id="sim_test",
            project_id="proj_test",
            graph_id="graph_test",
        )
        d = state.to_simple_dict()
        assert "simulation_id" in d
        assert "status" in d
        # simple_dict에는 런타임 상세 필드 없음
        assert "current_round" not in d
        assert "twitter_status" not in d


class TestPrepareSimulation:
    """prepare_simulation() 전체 흐름 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.sim_dir = str(tmp_path / "simulations")
        os.makedirs(self.sim_dir, exist_ok=True)

    def test_준비_전체_흐름(self, sample_nodes, sample_edges):
        """엔티티 읽기 → 프로필 생성 → 설정 생성 전체 흐름"""
        from app.services.entity_reader import FilteredEntities, EntityNode

        # 필터링된 엔티티 mock
        entities = [
            EntityNode(uuid="n1", name="홍길동", labels=["Entity", "Student"],
                      summary="학생", attributes={}, related_edges=[], related_nodes=[]),
            EntityNode(uuid="n2", name="김교수", labels=["Entity", "Professor"],
                      summary="교수", attributes={}, related_edges=[], related_nodes=[]),
        ]
        filtered = FilteredEntities(
            entities=entities, entity_types={"Student", "Professor"},
            total_count=5, filtered_count=2
        )

        # SimulationParameters mock
        mock_sim_params = MagicMock()
        mock_sim_params.to_json.return_value = json.dumps({"time_config": {}, "platform_configs": {}})
        mock_sim_params.generation_reasoning = "테스트 설정"

        with patch.object(SimulationManager, "SIMULATION_DATA_DIR", self.sim_dir), \
             patch("app.services.simulation_manager.EntityReader") as MockReader, \
             patch("app.services.simulation_manager.OasisProfileGenerator") as MockProfileGen, \
             patch("app.services.simulation_manager.SimulationConfigGenerator") as MockConfigGen:

            # EntityReader mock
            mock_reader = MagicMock()
            mock_reader.filter_defined_entities.return_value = filtered
            MockReader.return_value = mock_reader

            # OasisProfileGenerator mock
            mock_profile_gen = MagicMock()
            mock_profile_gen.generate_profiles_from_entities.return_value = [
                MagicMock(), MagicMock()
            ]
            MockProfileGen.return_value = mock_profile_gen

            # SimulationConfigGenerator mock
            mock_config_gen = MagicMock()
            mock_config_gen.generate_config.return_value = mock_sim_params
            MockConfigGen.return_value = mock_config_gen

            manager = SimulationManager()
            state = manager.create_simulation("proj_1", "graph_1")
            result = manager.prepare_simulation(
                simulation_id=state.simulation_id,
                simulation_requirement="여론 시뮬레이션",
                document_text="테스트 문서"
            )

            assert result.status == SimulationStatus.READY
            assert result.entities_count == 2
            assert result.profiles_count == 2
            assert result.config_generated is True

    def test_준비_엔티티_없으면_실패(self):
        """필터링된 엔티티가 0개면 FAILED 상태"""
        from app.services.entity_reader import FilteredEntities

        filtered = FilteredEntities(
            entities=[], entity_types=set(),
            total_count=0, filtered_count=0
        )

        with patch.object(SimulationManager, "SIMULATION_DATA_DIR", self.sim_dir), \
             patch("app.services.simulation_manager.EntityReader") as MockReader:

            mock_reader = MagicMock()
            mock_reader.filter_defined_entities.return_value = filtered
            MockReader.return_value = mock_reader

            manager = SimulationManager()
            state = manager.create_simulation("proj_1", "graph_1")
            result = manager.prepare_simulation(
                simulation_id=state.simulation_id,
                simulation_requirement="테스트",
                document_text="테스트"
            )

            assert result.status == SimulationStatus.FAILED
            assert "엔티티를 찾지 못했습니다" in result.error

    def test_존재하지_않는_시뮬레이션_준비_실패(self):
        with patch.object(SimulationManager, "SIMULATION_DATA_DIR", self.sim_dir):
            manager = SimulationManager()
            with pytest.raises(ValueError, match="존재하지 않습니다"):
                manager.prepare_simulation("nonexistent", "req", "text")
