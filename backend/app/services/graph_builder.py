"""
그래프 구축 서비스
Neo4j + LLM 추출 + ChromaDB 기반으로 재작성
(기존 Zep SDK 기반 graph_builder.py 대체)
"""

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from .text_processor import TextProcessor
from .graph_store import NodeData, EdgeData, ExtractionResult
from .neo4j_store import Neo4jGraphStore
from .llm_extractor import LLMEntityExtractor
from .chroma_store import ChromaSearchService

logger = get_logger('mirofish.graph_builder')


def _extract_chunk(chunk: str, ontology, existing_entities: list) -> ExtractionResult:
    """스레드별 독립 LLM 클라이언트로 추출 (스레드 안전)"""
    extractor = LLMEntityExtractor(llm_client=LLMClient())
    return extractor.extract_from_text(
        text=chunk,
        ontology=ontology,
        existing_entities=existing_entities
    )


@dataclass
class GraphInfo:
    """그래프 정보"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    그래프 구축 서비스
    Neo4j + LLM 추출 + ChromaDB로 지식 그래프 구축
    """

    def __init__(self):
        self.store = Neo4jGraphStore()
        self.extractor = LLMEntityExtractor()
        self.chroma = ChromaSearchService()
        self.task_manager = TaskManager()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        비동기 그래프 구축

        Args:
            text: 입력 텍스트
            ontology: 온톨로지 정의
            graph_name: 그래프 이름
            chunk_size: 텍스트 청크 크기
            chunk_overlap: 청크 오버랩
            batch_size: LLM 배치 크기

        Returns:
            태스크 ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int
    ):
        """그래프 구축 워커 스레드"""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="그래프 구축 시작..."
            )

            # 1. 그래프 생성
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id, progress=10,
                message=f"그래프 생성 완료: {graph_id}"
            )

            # 2. 온톨로지 설정
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id, progress=15,
                message="온톨로지 설정 완료"
            )

            # 3. 텍스트 분할
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id, progress=20,
                message=f"텍스트를 {total_chunks}개 청크로 분할 완료"
            )

            # 4. 각 청크에서 LLM으로 엔티티/관계 추출 후 Neo4j에 저장
            existing_entities = []
            for i in range(0, total_chunks, batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_chunks + batch_size - 1) // batch_size

                progress = 20 + int((i + len(batch_chunks)) / total_chunks * 70)  # 20-90%
                self.task_manager.update_task(
                    task_id,
                    progress=progress,
                    message=f"청크 추출 중... 배치 {batch_num}/{total_batches}"
                )

                # 배치 내 청크를 병렬로 LLM 추출 (스레드별 독립 클라이언트)
                snapshot = existing_entities[:100]
                with ThreadPoolExecutor(max_workers=batch_size) as pool:
                    futures = {
                        pool.submit(_extract_chunk, chunk, ontology, snapshot): chunk
                        for chunk in batch_chunks
                    }
                    for future in as_completed(futures):
                        extraction = future.result()
                        if extraction.entities or extraction.relationships:
                            self.store.merge_extraction(graph_id, extraction)
                            for e in extraction.entities:
                                name = e.get("name", "")
                                if name and name not in existing_entities:
                                    existing_entities.append(name)

            # 5. ChromaDB에 벡터 인덱스 구축
            self.task_manager.update_task(
                task_id, progress=90,
                message="벡터 인덱스 구축 중..."
            )
            self._build_chroma_index(graph_id)

            # 6. 그래프 정보 조회
            graph_info = self._get_graph_info(graph_id)

            # 완료
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """그래프 생성"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.store.create_graph(
            graph_id=graph_id,
            name=name,
            description="MiroFish Social Simulation Graph"
        )
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """그래프에 온톨로지 정의 설정"""
        self.store.set_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> None:
        """
        텍스트 청크를 LLM으로 추출 후 Neo4j에 저장 (공개 메서드)

        API 레이어에서 직접 호출 가능.
        기존 Zep의 add_text_batches와 동일한 인터페이스.

        Args:
            graph_id: 그래프 ID
            chunks: 텍스트 청크 목록
            batch_size: 배치 크기
            progress_callback: 진행 콜백 (message, progress_ratio)
        """
        total_chunks = len(chunks)
        ontology = self.store.get_ontology(graph_id)
        existing_entities = []

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    f"LLM 추출 중... 배치 {batch_num}/{total_batches} ({len(batch_chunks)}개 청크)",
                    progress
                )

            snapshot = existing_entities[:100]
            with ThreadPoolExecutor(max_workers=batch_size) as pool:
                futures = {
                    pool.submit(_extract_chunk, chunk, ontology, snapshot): chunk
                    for chunk in batch_chunks
                }
                for future in as_completed(futures):
                    chunk = futures[future]
                    extraction = future.result()
                    if extraction.entities or extraction.relationships:
                        logger.info(f"추출 결과: 엔티티 {len(extraction.entities)}개, 관계 {len(extraction.relationships)}개 → Neo4j 저장 시도")
                        self.store.merge_extraction(graph_id, extraction)
                        for e in extraction.entities:
                            name = e.get("name", "")
                            if name and name not in existing_entities:
                                existing_entities.append(name)
                    else:
                        logger.warning(f"청크에서 추출 결과 없음 (청크 길이: {len(chunk)})")

        # 추출 완료 후 ChromaDB 인덱스 구축
        self._build_chroma_index(graph_id)

    def _build_chroma_index(self, graph_id: str):
        """Neo4j 데이터를 ChromaDB에 인덱싱"""
        nodes = self.store.get_nodes_by_graph(graph_id)
        edges = self.store.get_edges_by_graph(graph_id)

        indexed_nodes = self.chroma.index_nodes_batch(graph_id, nodes)
        indexed_edges = self.chroma.index_edges_batch(graph_id, edges)

        logger.info(f"ChromaDB 인덱싱 완료: 노드 {indexed_nodes}개, 엣지 {indexed_edges}개")

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """그래프 정보 조회"""
        nodes = self.store.get_nodes_by_graph(graph_id)
        edges = self.store.get_edges_by_graph(graph_id)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        완전한 그래프 데이터 조회 (상세 정보 포함)

        Args:
            graph_id: 그래프 ID

        Returns:
            노드와 엣지를 포함한 딕셔너리
        """
        nodes = self.store.get_nodes_by_graph(graph_id)
        edges = self.store.get_edges_by_graph(graph_id)

        # 노드 맵 생성 (이름 참조용)
        node_map = {}
        for node in nodes:
            node_map[node.uuid] = node.name

        nodes_data = [n.to_dict() for n in nodes]

        edges_data = []
        for edge in edges:
            edge_dict = edge.to_dict()
            # 소스/타겟 노드 이름 보충
            if not edge_dict.get("source_node_name"):
                edge_dict["source_node_name"] = node_map.get(edge.source_node_uuid, "")
            if not edge_dict.get("target_node_name"):
                edge_dict["target_node_name"] = node_map.get(edge.target_node_uuid, "")
            edge_dict["episodes"] = []  # 호환성 유지
            edges_data.append(edge_dict)

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        """그래프 삭제 (Neo4j + ChromaDB)"""
        self.store.delete_graph(graph_id)
        self.chroma.delete_graph_data(graph_id)
        logger.info(f"그래프 완전 삭제: {graph_id}")
