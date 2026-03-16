"""
그래프 메모리 업데이트 서비스
시뮬레이션 중 Agent 활동을 그래프에 동적 업데이트
(기존 zep_graph_memory_updater.py 대체)
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from ..config import Config
from ..utils.logger import get_logger
from .neo4j_store import Neo4jGraphStore
from .llm_extractor import LLMEntityExtractor
from .chroma_store import ChromaSearchService

logger = get_logger('mirofish.graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent 활동 기록"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """
        활동을 텍스트 설명으로 변환 (LLM 추출용)
        시뮬레이션 관련 접두사를 추가하지 않아 그래프 업데이트 오도 방지
        """
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()

        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"게시물을 작성했습니다: 「{content}」"
        return "게시물을 작성했습니다"

    def _describe_like_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"{post_author}의 게시물에 좋아요를 눌렀습니다: 「{post_content}」"
        elif post_content:
            return f"게시물에 좋아요를 눌렀습니다: 「{post_content}」"
        elif post_author:
            return f"{post_author}의 게시물에 좋아요를 눌렀습니다"
        return "게시물에 좋아요를 눌렀습니다"

    def _describe_dislike_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"{post_author}의 게시물에 싫어요를 눌렀습니다: 「{post_content}」"
        elif post_content:
            return f"게시물에 싫어요를 눌렀습니다: 「{post_content}」"
        elif post_author:
            return f"{post_author}의 게시물에 싫어요를 눌렀습니다"
        return "게시물에 싫어요를 눌렀습니다"

    def _describe_repost(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        if original_content and original_author:
            return f"{original_author}의 게시물을 리포스트했습니다: 「{original_content}」"
        elif original_content:
            return f"게시물을 리포스트했습니다: 「{original_content}」"
        elif original_author:
            return f"{original_author}의 게시물을 리포스트했습니다"
        return "게시물을 리포스트했습니다"

    def _describe_quote_post(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        base = ""
        if original_content and original_author:
            base = f"{original_author}의 게시물을 인용했습니다 「{original_content}」"
        elif original_content:
            base = f"게시물을 인용했습니다 「{original_content}」"
        elif original_author:
            base = f"{original_author}의 게시물을 인용했습니다"
        else:
            base = "게시물을 인용했습니다"
        if quote_content:
            base += f", 코멘트: 「{quote_content}」"
        return base

    def _describe_follow(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"사용자를 팔로우했습니다 「{target_user_name}」"
        return "사용자를 팔로우했습니다"

    def _describe_create_comment(self) -> str:
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if content:
            if post_content and post_author:
                return f"{post_author}의 게시물 「{post_content}」에 댓글을 남겼습니다: 「{content}」"
            elif post_content:
                return f"게시물 「{post_content}」에 댓글을 남겼습니다: 「{content}」"
            elif post_author:
                return f"{post_author}의 게시물에 댓글을 남겼습니다: 「{content}」"
            return f"댓글을 남겼습니다: 「{content}」"
        return "댓글을 남겼습니다"

    def _describe_like_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"{comment_author}의 댓글에 좋아요를 눌렀습니다: 「{comment_content}」"
        elif comment_content:
            return f"댓글에 좋아요를 눌렀습니다: 「{comment_content}」"
        elif comment_author:
            return f"{comment_author}의 댓글에 좋아요를 눌렀습니다"
        return "댓글에 좋아요를 눌렀습니다"

    def _describe_dislike_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"{comment_author}의 댓글에 싫어요를 눌렀습니다: 「{comment_content}」"
        elif comment_content:
            return f"댓글에 싫어요를 눌렀습니다: 「{comment_content}」"
        elif comment_author:
            return f"{comment_author}의 댓글에 싫어요를 눌렀습니다"
        return "댓글에 싫어요를 눌렀습니다"

    def _describe_search(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"검색했습니다 「{query}」" if query else "검색을 수행했습니다"

    def _describe_search_user(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"사용자를 검색했습니다 「{query}」" if query else "사용자를 검색했습니다"

    def _describe_mute(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"사용자를 차단했습니다 「{target_user_name}」"
        return "사용자를 차단했습니다"

    def _describe_generic(self) -> str:
        return f"{self.action_type} 작업을 수행했습니다"


class GraphMemoryUpdater:
    """
    그래프 메모리 업데이터

    시뮬레이션의 actions 로그를 모니터링하고
    에이전트 활동을 LLM 추출 후 Neo4j 그래프에 실시간 업데이트.
    플랫폼별로 그룹화하여 BATCH_SIZE 도달 시 배치 발송.
    """

    BATCH_SIZE = 5
    PLATFORM_DISPLAY_NAMES = {
        'twitter': '세계1',
        'reddit': '세계2',
    }
    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.store = Neo4jGraphStore()
        self.extractor = LLMEntityExtractor()
        self.chroma = ChromaSearchService()

        # 활동 큐
        self._activity_queue: Queue = Queue()

        # 플랫폼별 활동 버퍼
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()

        # 기존 엔티티 캐시 (중복 방지)
        self._existing_entities: List[str] = []
        self._entities_loaded = False

        # 제어 플래그
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # 통계
        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

        logger.info(f"GraphMemoryUpdater 초기화 완료: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _load_existing_entities(self):
        """기존 엔티티 이름 목록 로드 (초기 1회)"""
        if self._entities_loaded:
            return
        try:
            nodes = self.store.get_nodes_by_graph(self.graph_id)
            self._existing_entities = [n.name for n in nodes if n.name]
            self._entities_loaded = True
            logger.info(f"기존 엔티티 {len(self._existing_entities)}개 로드 완료")
        except Exception as e:
            logger.warning(f"기존 엔티티 로드 실패: {e}")

    def _get_platform_display_name(self, platform: str) -> str:
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"GraphMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"GraphMemoryUpdater 시작: graph_id={self.graph_id}")

    def stop(self):
        self._running = False
        self._flush_remaining()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        logger.info(f"GraphMemoryUpdater 중지: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")

    def add_activity(self, activity: AgentActivity):
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"활동 추가: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        if "event_type" in data:
            return
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        self.add_activity(activity)

    def _worker_loop(self):
        # 첫 실행 시 기존 엔티티 로드
        self._load_existing_entities()

        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)

                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            self._send_batch_activities(batch, platform)
                            time.sleep(self.SEND_INTERVAL)
                except Empty:
                    pass
            except Exception as e:
                logger.error(f"워커 루프 오류: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """배치 활동을 LLM 추출 후 Neo4j에 저장"""
        if not activities:
            return

        # 활동 텍스트 결합
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)

        for attempt in range(self.MAX_RETRIES):
            try:
                # LLM으로 엔티티/관계 추출
                extraction = self.extractor.extract_from_activity(
                    activity_text=combined_text,
                    existing_entities=self._existing_entities[:50]
                )

                if extraction.entities or extraction.relationships:
                    # Neo4j에 병합
                    self.store.merge_extraction(self.graph_id, extraction)

                    # ChromaDB에도 인덱싱 (새로 생성된 엣지)
                    new_edges = self.store.get_edges_by_graph(self.graph_id)
                    if new_edges:
                        self.chroma.index_edges_batch(self.graph_id, new_edges[-len(extraction.relationships):])

                    # 기존 엔티티 캐시 업데이트
                    for e in extraction.entities:
                        name = e.get("name", "")
                        if name and name not in self._existing_entities:
                            self._existing_entities.append(name)

                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"배치 전송 성공: {len(activities)}개 {display_name} 활동 → 그래프 {self.graph_id}")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"배치 전송 실패 (시도 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"배치 전송 실패, {self.MAX_RETRIES}회 재시도 후 포기: {e}")
                    self._failed_count += 1

    def _flush_remaining(self):
        """큐와 버퍼에 남은 활동 발송"""
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"{display_name} 플랫폼 잔여 {len(buffer)}개 활동 발송")
                    self._send_batch_activities(buffer, platform)
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class GraphMemoryManager:
    """
    다중 시뮬레이션의 그래프 메모리 업데이터 관리
    """

    _updaters: Dict[str, GraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> GraphMemoryUpdater:
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            updater = GraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            logger.info(f"그래프 메모리 업데이터 생성: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[GraphMemoryUpdater]:
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"그래프 메모리 업데이터 중지: simulation_id={simulation_id}")

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"업데이터 중지 실패: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("모든 그래프 메모리 업데이터 중지 완료")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {
            sim_id: updater.get_stats()
            for sim_id, updater in cls._updaters.items()
        }
