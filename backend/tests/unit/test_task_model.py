"""
TaskManager 단위 테스트
외부 의존성 없는 인메모리 싱글턴 로직 테스트
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.task import TaskManager, TaskStatus, Task


class TestTaskManager:
    """TaskManager CRUD 및 상태 전이 테스트"""

    def test_싱글턴_패턴(self):
        """동일 인스턴스를 반환하는지 확인"""
        tm1 = TaskManager()
        tm2 = TaskManager()
        assert tm1 is tm2

    def test_태스크_생성(self):
        tm = TaskManager()
        task_id = tm.create_task("graph_build", {"key": "value"})

        assert task_id is not None
        task = tm.get_task(task_id)
        assert task is not None
        assert task.task_type == "graph_build"
        assert task.status == TaskStatus.PENDING
        assert task.metadata == {"key": "value"}
        assert task.progress == 0

    def test_태스크_상태_업데이트(self):
        tm = TaskManager()
        task_id = tm.create_task("test")

        tm.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=50,
            message="진행 중"
        )

        task = tm.get_task(task_id)
        assert task.status == TaskStatus.PROCESSING
        assert task.progress == 50
        assert task.message == "진행 중"

    def test_태스크_완료(self):
        tm = TaskManager()
        task_id = tm.create_task("test")

        tm.complete_task(task_id, {"graph_id": "g123"})

        task = tm.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100
        assert task.result == {"graph_id": "g123"}

    def test_태스크_실패(self):
        tm = TaskManager()
        task_id = tm.create_task("test")

        tm.fail_task(task_id, "연결 실패")

        task = tm.get_task(task_id)
        assert task.status == TaskStatus.FAILED
        assert task.error == "연결 실패"

    def test_존재하지_않는_태스크_조회(self):
        tm = TaskManager()
        assert tm.get_task("nonexistent") is None

    def test_존재하지_않는_태스크_업데이트_무시(self):
        tm = TaskManager()
        # 에러 없이 무시
        tm.update_task("nonexistent", status=TaskStatus.COMPLETED)

    def test_태스크_목록_조회(self):
        tm = TaskManager()
        tm.create_task("graph_build")
        tm.create_task("simulation")
        tm.create_task("graph_build")

        all_tasks = tm.list_tasks()
        assert len(all_tasks) == 3

        graph_tasks = tm.list_tasks(task_type="graph_build")
        assert len(graph_tasks) == 2

        sim_tasks = tm.list_tasks(task_type="simulation")
        assert len(sim_tasks) == 1

    def test_태스크_목록_역순_정렬(self):
        tm = TaskManager()
        id1 = tm.create_task("a")
        # created_at를 명시적으로 과거로 설정
        task1 = tm.get_task(id1)
        task1.created_at = datetime(2026, 1, 1, 0, 0, 0)

        id2 = tm.create_task("b")
        task2 = tm.get_task(id2)
        task2.created_at = datetime(2026, 1, 2, 0, 0, 0)

        tasks = tm.list_tasks()
        # 최신 태스크가 먼저
        assert tasks[0]["task_id"] == id2
        assert tasks[1]["task_id"] == id1

    def test_오래된_태스크_정리(self):
        tm = TaskManager()

        # 완료된 오래된 태스크 생성
        old_id = tm.create_task("old")
        tm.complete_task(old_id, {})

        # created_at을 25시간 전으로 변경
        task = tm.get_task(old_id)
        task.created_at = datetime.now() - timedelta(hours=25)

        # 진행 중인 태스크 (정리 대상 아님)
        active_id = tm.create_task("active")
        active_task = tm.get_task(active_id)
        active_task.created_at = datetime.now() - timedelta(hours=25)

        tm.cleanup_old_tasks(max_age_hours=24)

        # 완료된 오래된 태스크만 삭제
        assert tm.get_task(old_id) is None
        assert tm.get_task(active_id) is not None

    def test_to_dict_변환(self):
        tm = TaskManager()
        task_id = tm.create_task("test", {"meta": True})
        tm.update_task(task_id, progress=50, message="test msg")

        task = tm.get_task(task_id)
        d = task.to_dict()

        assert d["task_id"] == task_id
        assert d["task_type"] == "test"
        assert d["status"] == "pending"
        assert d["progress"] == 50
        assert d["message"] == "test msg"
        assert d["metadata"] == {"meta": True}
        assert "created_at" in d
        assert "updated_at" in d

    def test_progress_detail_업데이트(self):
        tm = TaskManager()
        task_id = tm.create_task("test")

        detail = {"stage": "extracting", "current_chunk": 5, "total_chunks": 10}
        tm.update_task(task_id, progress_detail=detail)

        task = tm.get_task(task_id)
        assert task.progress_detail == detail
