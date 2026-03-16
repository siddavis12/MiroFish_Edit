"""
그래프 저장소 추상 인터페이스
Zep Cloud를 대체하는 로컬 그래프 저장소의 ABC 정의
"""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NodeData:
    """노드 데이터 (기존 Zep 노드 객체와 동일 속성)"""
    uuid: str
    name: str
    labels: List[str] = field(default_factory=list)
    summary: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }


@dataclass
class EdgeData:
    """엣지 데이터 (기존 Zep 엣지 객체와 동일 속성)"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str = ""
    target_node_name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
        }


@dataclass
class SearchData:
    """검색 결과 데이터"""
    facts: List[str] = field(default_factory=list)
    edges: List[EdgeData] = field(default_factory=list)
    nodes: List[NodeData] = field(default_factory=list)
    query: str = ""
    total_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": [e.to_dict() for e in self.edges],
            "nodes": [n.to_dict() for n in self.nodes],
            "query": self.query,
            "total_count": self.total_count,
        }


@dataclass
class ExtractionResult:
    """LLM 엔티티/관계 추출 결과"""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": self.entities,
            "relationships": self.relationships,
        }


def generate_uuid() -> str:
    """UUID 생성 헬퍼"""
    return str(uuid.uuid4())


class GraphStore(ABC):
    """그래프 저장소 추상 클래스"""

    @abstractmethod
    def create_graph(self, graph_id: str, name: str, description: str = "") -> str:
        """그래프 생성. 반환: graph_id"""
        ...

    @abstractmethod
    def delete_graph(self, graph_id: str) -> None:
        """그래프 및 모든 하위 노드/엣지 삭제"""
        ...

    @abstractmethod
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        """그래프에 온톨로지 정의 저장"""
        ...

    @abstractmethod
    def get_ontology(self, graph_id: str) -> Optional[Dict[str, Any]]:
        """그래프의 온톨로지 정의 조회"""
        ...

    @abstractmethod
    def merge_extraction(self, graph_id: str, extraction: ExtractionResult) -> Dict[str, int]:
        """LLM 추출 결과를 그래프에 병합 (MERGE 시맨틱). 반환: {nodes_created, edges_created, ...}"""
        ...

    @abstractmethod
    def get_nodes_by_graph(self, graph_id: str, limit: int = 2000) -> List[NodeData]:
        """그래프의 모든 노드 조회 (페이징)"""
        ...

    @abstractmethod
    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        """단일 노드 조회"""
        ...

    @abstractmethod
    def get_entity_edges(self, node_uuid: str) -> List[EdgeData]:
        """특정 노드의 모든 연결 엣지 조회"""
        ...

    @abstractmethod
    def get_edges_by_graph(self, graph_id: str, limit: int = 5000) -> List[EdgeData]:
        """그래프의 모든 엣지 조회"""
        ...

    @abstractmethod
    def search(self, graph_id: str, query: str, limit: int = 10) -> SearchData:
        """그래프 내 키워드 검색 (로컬 매칭)"""
        ...
