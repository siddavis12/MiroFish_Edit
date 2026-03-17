"""
실전 E2E 파이프라인 테스트

실제 서비스 연동: Neo4j, ChromaDB, LLM API
OASIS 시뮬레이션만 mock (서브프로세스)
최소한의 데이터로 전체 사이클 1회전

실행: uv run pytest tests/test_real_e2e.py -v -s --timeout=300
"""

import os
import sys
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

# 타임아웃 설정 (LLM 호출 포함이므로 충분히)
pytestmark = pytest.mark.timeout(300)

# ============== 최소 테스트 데이터 ==============

# 3문장짜리 초소형 문서
MINI_DOCUMENT = """김연구원은 한국AI연구소 소속 인공지능 연구자이다.
그는 최근 발표한 논문의 데이터 조작 의혹으로 학계의 주목을 받고 있다.
한국AI연구소 측은 내부 조사위원회를 구성하여 사실관계를 확인 중이라고 밝혔다."""

MINI_REQUIREMENT = "AI 연구 부정 의혹에 대한 소셜 미디어 여론 시뮬레이션"


class TestRealE2E:
    """
    실전 E2E 테스트 — LLM 실제 호출, Neo4j/ChromaDB 실제 사용

    비용 최소화:
    - 문서 3문장 (청크 1개)
    - 시뮬레이션은 mock (OASIS 미사용)
    - 리포트 생성은 mock (장시간 방지)
    """

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """테스트 환경 설정"""
        self.tmp_path = tmp_path

        # 프로젝트/시뮬레이션 저장소를 임시 디렉토리로
        self.upload_dir = str(tmp_path / "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)

        # 테스트용 텍스트 파일 생성
        self.test_file = str(tmp_path / "test_doc.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(MINI_DOCUMENT)

    def _create_app(self):
        """테스트용 Flask 앱 생성 (실제 Neo4j/ChromaDB 연결)"""
        from app.config import Config

        # 업로드/시뮬레이션 경로만 임시로 변경
        original_upload = Config.UPLOAD_FOLDER
        original_sim_dir = Config.OASIS_SIMULATION_DATA_DIR
        Config.UPLOAD_FOLDER = self.upload_dir
        Config.OASIS_SIMULATION_DATA_DIR = str(self.tmp_path / "simulations")
        os.makedirs(Config.OASIS_SIMULATION_DATA_DIR, exist_ok=True)

        # SimulationRunner cleanup만 mock (atexit 등록 방지)
        with patch("app.services.simulation_runner.SimulationRunner.register_cleanup"):
            from app import create_app
            app = create_app()
            app.config["TESTING"] = True

        # ProjectManager, SimulationManager 경로도 임시로
        from app.models.project import ProjectManager
        ProjectManager.PROJECTS_DIR = os.path.join(self.upload_dir, "projects")
        os.makedirs(ProjectManager.PROJECTS_DIR, exist_ok=True)

        from app.services.simulation_manager import SimulationManager
        SimulationManager.SIMULATION_DATA_DIR = str(self.tmp_path / "simulations")

        self._original_upload = original_upload
        self._original_sim_dir = original_sim_dir

        return app

    def _cleanup_graph(self, graph_id):
        """테스트 후 생성된 그래프 정리"""
        try:
            from app.services.neo4j_store import Neo4jGraphStore
            from app.services.chroma_store import ChromaSearchService
            store = Neo4jGraphStore()
            store.delete_graph(graph_id)
            chroma = ChromaSearchService()
            chroma.delete_graph_data(graph_id)
            print(f"  [정리] 그래프 삭제 완료: {graph_id}")
        except Exception as e:
            print(f"  [정리] 그래프 삭제 실패 (무시): {e}")

    def test_real_pipeline(self):
        """실전 E2E: 온톨로지 → 그래프 구축 → 시뮬레이션 → 리포트 → 대화"""
        app = self._create_app()
        client = app.test_client()

        graph_id = None  # 정리용

        try:
            # ==========================================
            # Step1-1: 파일 업로드 + 온톨로지 생성 (실제 LLM 호출)
            # ==========================================
            print("\n  [Step1-1] 온톨로지 생성 중 (LLM 실제 호출)...")
            t0 = time.time()

            resp = client.post(
                "/api/graph/ontology/generate",
                data={
                    "files": (BytesIO(MINI_DOCUMENT.encode("utf-8")), "test_doc.txt"),
                    "simulation_requirement": MINI_REQUIREMENT,
                    "project_name": "E2E 실전 테스트"
                },
                content_type="multipart/form-data"
            )

            assert resp.status_code == 200, f"온톨로지 생성 실패: {resp.get_json()}"
            data = resp.get_json()["data"]
            project_id = data["project_id"]
            ontology = data["ontology"]
            entity_count = len(ontology.get("entity_types", []))
            edge_count = len(ontology.get("edge_types", []))
            print(f"  [Step1-1] 완료 ({time.time()-t0:.1f}s) — project_id={project_id}")
            print(f"            엔티티 유형 {entity_count}개, 관계 유형 {edge_count}개")
            print(f"            분석: {data.get('analysis_summary', '')[:80]}")

            assert entity_count > 0, "엔티티 유형이 0개"
            assert edge_count > 0, "관계 유형이 0개"

            # ==========================================
            # Step1-2: 그래프 구축 (실제 LLM + Neo4j + ChromaDB)
            # ==========================================
            print(f"\n  [Step1-2] 그래프 구축 시작 (LLM 추출 + Neo4j 저장)...")
            t0 = time.time()

            # _builder_instance 초기화 (이전 테스트 잔여 방지)
            import app.api.graph as graph_module
            graph_module._builder_instance = None

            resp = client.post(
                "/api/graph/build",
                json={"project_id": project_id, "chunk_size": 500, "chunk_overlap": 50}
            )

            assert resp.status_code == 200, f"그래프 구축 시작 실패: {resp.get_json()}"
            task_id = resp.get_json()["data"]["task_id"]
            print(f"            task_id={task_id}")

            # 태스크 완료 대기 (최대 120초)
            for i in range(60):
                time.sleep(2)
                resp = client.get(f"/api/graph/task/{task_id}")
                assert resp.status_code == 200
                task = resp.get_json()["data"]

                if task["status"] == "completed":
                    graph_id = task["result"]["graph_id"]
                    print(f"  [Step1-2] 완료 ({time.time()-t0:.1f}s) — graph_id={graph_id}")
                    print(f"            노드 {task['result']['node_count']}개, 엣지 {task['result']['edge_count']}개")
                    break
                elif task["status"] == "failed":
                    pytest.fail(f"그래프 구축 실패: {task.get('error', '')[:200]}")
                else:
                    if i % 5 == 0:
                        print(f"            ... {task['status']} {task['progress']}% — {task['message']}")
            else:
                pytest.fail("그래프 구축 타임아웃 (120초)")

            # ==========================================
            # Step1-3: 그래프 데이터 확인
            # ==========================================
            resp = client.get(f"/api/graph/data/{graph_id}")
            assert resp.status_code == 200, f"그래프 조회 실패: {resp.get_json()}"
            gdata = resp.get_json()["data"]
            print(f"  [Step1-3] 그래프 조회 OK — 노드 {gdata['node_count']}, 엣지 {gdata['edge_count']}")
            assert gdata["node_count"] > 0, "노드가 0개"

            # ==========================================
            # Step2-1: 시뮬레이션 생성
            # ==========================================
            print(f"\n  [Step2-1] 시뮬레이션 생성...")

            resp = client.post(
                "/api/simulation/create",
                json={"project_id": project_id}
            )

            assert resp.status_code == 200, f"시뮬레이션 생성 실패: {resp.get_json()}"
            sim_id = resp.get_json()["data"]["simulation_id"]
            print(f"  [Step2-1] 완료 — simulation_id={sim_id}")

            # ==========================================
            # Step2-2: 시뮬레이션 준비 (실제 LLM으로 설정 생성)
            # ==========================================
            print(f"\n  [Step2-2] 시뮬레이션 준비 중 (LLM 프로필+설정 생성)...")
            t0 = time.time()

            resp = client.post(
                "/api/simulation/prepare",
                json={
                    "simulation_id": sim_id,
                    "use_llm_for_profiles": True,
                    "parallel_profile_count": 2  # 병렬 수 최소화
                }
            )

            assert resp.status_code == 200, f"시뮬레이션 준비 시작 실패: {resp.get_json()}"
            prep_data = resp.get_json()["data"]

            # 이미 준비 완료 상태일 수 있음
            if prep_data.get("already_prepared"):
                print(f"  [Step2-2] 이미 준비 완료 ({time.time()-t0:.1f}s)")
            else:
                prep_task_id = prep_data.get("task_id")
                print(f"            task_id={prep_task_id}")

                # 준비 완료 대기 (최대 180초)
                for i in range(90):
                    time.sleep(2)
                    resp = client.post(
                        "/api/simulation/prepare/status",
                        json={"simulation_id": sim_id, "task_id": prep_task_id}
                    )
                    if resp.status_code != 200:
                        continue

                    status_data = resp.get_json().get("data", {})
                    task_status = status_data.get("task_status", "")
                    sim_status = status_data.get("status", "")
                    already = status_data.get("already_prepared", False)

                    # 완료 조건: task_status가 completed이거나, 시뮬레이션이 이미 ready 상태
                    if task_status == "completed" or sim_status == "ready" or already:
                        print(f"  [Step2-2] 완료 ({time.time()-t0:.1f}s)")
                        print(f"            엔티티 {status_data.get('entities_count', '?')}개, 프로필 {status_data.get('profiles_count', '?')}개")
                        break
                    elif task_status == "failed":
                        pytest.fail(f"시뮬레이션 준비 실패: {status_data.get('error', '')[:200]}")
                    else:
                        if i % 5 == 0:
                            msg = status_data.get("message", "")
                            progress = status_data.get("progress", 0)
                            print(f"            ... {task_status} {progress}% — {msg[:60]}")
                else:
                    pytest.fail("시뮬레이션 준비 타임아웃 (180초)")

            # ==========================================
            # Step3: 시뮬레이션 시작 (OASIS mock)
            # ==========================================
            print(f"\n  [Step3] 시뮬레이션 시작 (OASIS mock)...")

            from app.services.simulation_runner import SimulationRunner, RunnerStatus, SimulationRunState

            # OASIS 서브프로세스만 mock
            mock_run_state = SimulationRunState(
                simulation_id=sim_id,
                runner_status=RunnerStatus.RUNNING,
                total_rounds=3,
                started_at="2026-03-17T14:00:00",
            )
            mock_run_state.twitter_running = True
            mock_run_state.reddit_running = True

            with patch.object(SimulationRunner, "start_simulation", return_value=mock_run_state):
                resp = client.post(
                    "/api/simulation/start",
                    json={
                        "simulation_id": sim_id,
                        "platform": "parallel",
                        "max_rounds": 3,
                        "force": True
                    }
                )

            assert resp.status_code == 200, f"시뮬레이션 시작 실패: {resp.get_json()}"
            print(f"  [Step3] 완료 — 시뮬레이션 시작됨 (mock, 3라운드)")

            # ==========================================
            # Step4: ReportAgent 대화 (실제 LLM + 그래프 도구)
            # ==========================================
            print(f"\n  [Step4] ReportAgent 대화 (LLM 실제 호출 + 그래프 검색)...")
            t0 = time.time()

            resp = client.post(
                "/api/report/chat",
                json={
                    "simulation_id": sim_id,
                    "message": "이 시뮬레이션 주제의 핵심 이해관계자는 누구이며, 예상되는 여론 흐름은?"
                }
            )

            assert resp.status_code == 200, f"ReportAgent 대화 실패: {resp.get_json()}"
            chat_data = resp.get_json()["data"]
            response_text = chat_data.get("response", "")
            tool_calls = chat_data.get("tool_calls", [])
            print(f"  [Step4] 완료 ({time.time()-t0:.1f}s)")
            print(f"            응답 길이: {len(response_text)}자")
            print(f"            도구 호출: {len(tool_calls)}회")
            print(f"            응답 미리보기: {response_text[:120]}...")

            assert len(response_text) > 0, "ReportAgent 응답이 비어있음"

            # ==========================================
            # 결과 요약
            # ==========================================
            print(f"\n  {'='*50}")
            print(f"  실전 E2E 파이프라인 테스트 완료")
            print(f"  {'='*50}")
            print(f"  project_id   : {project_id}")
            print(f"  graph_id     : {graph_id}")
            print(f"  simulation_id: {sim_id}")
            print(f"  온톨로지     : 엔티티 {entity_count}유형, 관계 {edge_count}유형")
            print(f"  그래프       : 노드 {gdata['node_count']}, 엣지 {gdata['edge_count']}")
            print(f"  Agent 대화   : {len(response_text)}자 응답, {len(tool_calls)}회 도구 호출")
            print(f"  결과: 전체 파이프라인 정상 동작")

        finally:
            # 테스트 후 Neo4j/ChromaDB 정리
            if graph_id:
                self._cleanup_graph(graph_id)

            # _builder_instance 초기화
            try:
                import app.api.graph as gm
                gm._builder_instance = None
            except Exception:
                pass
