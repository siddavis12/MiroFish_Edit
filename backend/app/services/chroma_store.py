"""
ChromaDB 벡터 검색 서비스
그래프 데이터의 시맨틱 검색을 위한 ChromaDB 래퍼
"""

import os
from typing import Dict, Any, List, Optional

import chromadb
from chromadb.config import Settings

from ..config import Config
from ..utils.logger import get_logger
from .graph_store import NodeData, EdgeData, SearchData

logger = get_logger('mirofish.chroma_store')


class ChromaSearchService:
    """
    ChromaDB 기반 벡터 검색 서비스

    그래프별 컬렉션:
    - {graph_id}_edges: 엣지(fact) 임베딩
    - {graph_id}_nodes: 노드(name + summary) 임베딩

    임베딩: ChromaDB 기본 모델 (all-MiniLM-L6-v2) 사용
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self._persist_dir = persist_dir or Config.CHROMA_PERSIST_DIR
        os.makedirs(self._persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        logger.info(f"ChromaSearchService 초기화: persist_dir={self._persist_dir}")

    def _get_edge_collection(self, graph_id: str):
        """엣지 컬렉션 가져오기 (없으면 생성)"""
        name = f"{graph_id}_edges".replace("-", "_")[:63]
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def _get_node_collection(self, graph_id: str):
        """노드 컬렉션 가져오기 (없으면 생성)"""
        name = f"{graph_id}_nodes".replace("-", "_")[:63]
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def index_edge(self, graph_id: str, edge: EdgeData) -> None:
        """엣지를 벡터 인덱스에 추가"""
        collection = self._get_edge_collection(graph_id)
        # fact가 비어 있으면 name 사용
        document = edge.fact or edge.name or ""
        if not document.strip():
            return

        metadata = {
            "name": edge.name or "",
            "source_name": edge.source_node_name or "",
            "target_name": edge.target_node_name or "",
            "source_uuid": edge.source_node_uuid or "",
            "target_uuid": edge.target_node_uuid or "",
        }

        collection.upsert(
            ids=[edge.uuid],
            documents=[document],
            metadatas=[metadata]
        )

    def index_node(self, graph_id: str, node: NodeData) -> None:
        """노드를 벡터 인덱스에 추가"""
        collection = self._get_node_collection(graph_id)
        document = f"{node.name}: {node.summary}" if node.summary else node.name
        if not document.strip():
            return

        labels = node.labels or []
        metadata = {
            "name": node.name or "",
            "labels": ",".join(labels),
            "has_summary": bool(node.summary),
        }

        collection.upsert(
            ids=[node.uuid],
            documents=[document],
            metadatas=[metadata]
        )

    def index_edges_batch(self, graph_id: str, edges: List[EdgeData]) -> int:
        """엣지 배치 인덱싱"""
        collection = self._get_edge_collection(graph_id)
        ids = []
        documents = []
        metadatas = []

        for edge in edges:
            document = edge.fact or edge.name or ""
            if not document.strip():
                continue
            ids.append(edge.uuid)
            documents.append(document)
            metadatas.append({
                "name": edge.name or "",
                "source_name": edge.source_node_name or "",
                "target_name": edge.target_node_name or "",
                "source_uuid": edge.source_node_uuid or "",
                "target_uuid": edge.target_node_uuid or "",
            })

        if ids:
            # ChromaDB upsert는 배치 크기 제한이 있으므로 5000개씩 분할
            batch_size = 5000
            for i in range(0, len(ids), batch_size):
                collection.upsert(
                    ids=ids[i:i + batch_size],
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size]
                )

        return len(ids)

    def index_nodes_batch(self, graph_id: str, nodes: List[NodeData]) -> int:
        """노드 배치 인덱싱"""
        collection = self._get_node_collection(graph_id)
        ids = []
        documents = []
        metadatas = []

        for node in nodes:
            document = f"{node.name}: {node.summary}" if node.summary else node.name
            if not document.strip():
                continue
            labels = node.labels or []
            ids.append(node.uuid)
            documents.append(document)
            metadatas.append({
                "name": node.name or "",
                "labels": ",".join(labels),
                "has_summary": bool(node.summary),
            })

        if ids:
            batch_size = 5000
            for i in range(0, len(ids), batch_size):
                collection.upsert(
                    ids=ids[i:i + batch_size],
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size]
                )

        return len(ids)

    def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchData:
        """
        시맨틱 검색

        Args:
            graph_id: 그래프 ID
            query: 검색 쿼리
            limit: 결과 수 제한
            scope: 검색 범위 ("edges", "nodes", "both")

        Returns:
            SearchData: 검색 결과
        """
        facts = []
        result_edges = []
        result_nodes = []

        if scope in ("edges", "both"):
            try:
                collection = self._get_edge_collection(graph_id)
                if collection.count() > 0:
                    results = collection.query(
                        query_texts=[query],
                        n_results=min(limit, collection.count())
                    )
                    if results and results["documents"]:
                        for i, doc in enumerate(results["documents"][0]):
                            facts.append(doc)
                            meta = results["metadatas"][0][i] if results["metadatas"] else {}
                            result_edges.append(EdgeData(
                                uuid=results["ids"][0][i] if results["ids"] else "",
                                name=meta.get("name", ""),
                                fact=doc,
                                source_node_uuid=meta.get("source_uuid", ""),
                                target_node_uuid=meta.get("target_uuid", ""),
                                source_node_name=meta.get("source_name", ""),
                                target_node_name=meta.get("target_name", ""),
                            ))
            except Exception as e:
                logger.warning(f"엣지 검색 실패: {e}")

        if scope in ("nodes", "both"):
            try:
                collection = self._get_node_collection(graph_id)
                if collection.count() > 0:
                    results = collection.query(
                        query_texts=[query],
                        n_results=min(limit, collection.count())
                    )
                    if results and results["documents"]:
                        for i, doc in enumerate(results["documents"][0]):
                            meta = results["metadatas"][0][i] if results["metadatas"] else {}
                            labels_str = meta.get("labels", "")
                            labels = labels_str.split(",") if labels_str else []
                            node = NodeData(
                                uuid=results["ids"][0][i] if results["ids"] else "",
                                name=meta.get("name", ""),
                                labels=labels,
                                summary=doc,
                            )
                            result_nodes.append(node)
                            facts.append(f"[{node.name}]: {doc}")
            except Exception as e:
                logger.warning(f"노드 검색 실패: {e}")

        return SearchData(
            facts=facts,
            edges=result_edges,
            nodes=result_nodes,
            query=query,
            total_count=len(facts)
        )

    def delete_graph_data(self, graph_id: str) -> None:
        """그래프의 모든 벡터 데이터 삭제"""
        for suffix in ("_edges", "_nodes"):
            name = f"{graph_id}{suffix}".replace("-", "_")[:63]
            try:
                self._client.delete_collection(name)
                logger.info(f"컬렉션 삭제: {name}")
            except Exception:
                pass  # 컬렉션이 없을 수 있음
