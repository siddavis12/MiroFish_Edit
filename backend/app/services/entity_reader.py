"""
엔티티 읽기 및 필터링 서비스
그래프에서 노드를 읽고 사전 정의된 엔티티 타입에 따라 필터링
(기존 zep_entity_reader.py 대체)
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger
from .neo4j_store import Neo4jGraphStore
from .graph_store import NodeData, EdgeData

logger = get_logger('mirofish.entity_reader')

T = TypeVar('T')


@dataclass
class EntityNode:
    """엔티티 노드 데이터 구조"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # 관련 엣지 정보
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # 관련 노드 정보
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """엔티티 타입 조회 (기본 Entity 라벨 제외)"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """필터링된 엔티티 집합"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class EntityReader:
    """
    엔티티 읽기 및 필터링 서비스

    주요 기능:
    1. 그래프에서 모든 노드 읽기
    2. 사전 정의된 엔티티 타입에 맞는 노드만 필터링
    3. 각 엔티티의 관련 엣지 및 연관 노드 정보 조회
    """

    def __init__(self):
        self.store = Neo4jGraphStore()

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """그래프의 모든 노드 조회"""
        logger.info(f"그래프 {graph_id}의 모든 노드 조회 중...")
        nodes = self.store.get_nodes_by_graph(graph_id)
        nodes_data = [n.to_dict() for n in nodes]
        logger.info(f"총 {len(nodes_data)}개 노드 조회 완료")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """그래프의 모든 엣지 조회"""
        logger.info(f"그래프 {graph_id}의 모든 엣지 조회 중...")
        edges = self.store.get_edges_by_graph(graph_id)
        edges_data = [e.to_dict() for e in edges]
        logger.info(f"총 {len(edges_data)}개 엣지 조회 완료")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """특정 노드의 모든 관련 엣지 조회"""
        try:
            edges = self.store.get_entity_edges(node_uuid)
            return [e.to_dict() for e in edges]
        except Exception as e:
            logger.warning(f"노드 {node_uuid}의 엣지 조회 실패: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        사전 정의된 엔티티 타입에 맞는 노드만 필터링

        필터링 로직:
        - 노드의 Labels가 "Entity"만 있으면 → 사전 정의 타입에 해당하지 않으므로 스킵
        - "Entity", "Node" 외의 라벨이 있으면 → 사전 정의 타입에 해당하므로 유지

        Args:
            graph_id: 그래프 ID
            defined_entity_types: 사전 정의된 엔티티 타입 목록 (제공 시 해당 타입만 유지)
            enrich_with_edges: 각 엔티티의 관련 엣지 정보 포함 여부

        Returns:
            FilteredEntities: 필터링된 엔티티 집합
        """
        logger.info(f"그래프 {graph_id}의 엔티티 필터링 시작...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []

        # 노드 UUID → 노드 데이터 맵
        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            labels = node.get("labels", [])

            # 필터링: "Entity", "Node" 외의 라벨이 있어야 함
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]

            if not custom_labels:
                continue

            # 사전 정의 타입이 지정된 경우 매칭 확인
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            # 관련 엣지 및 노드 조회
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"필터링 완료: 전체 노드 {total_count}, 필터 통과 {len(filtered_entities)}, "
                   f"엔티티 타입: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        단일 엔티티 및 완전한 컨텍스트 조회 (엣지 + 연관 노드)

        Args:
            graph_id: 그래프 ID
            entity_uuid: 엔티티 UUID

        Returns:
            EntityNode 또는 None
        """
        try:
            node_data = self.store.get_node(entity_uuid)
            if not node_data:
                return None

            # 노드의 엣지 조회
            edges_data = [e.to_dict() for e in self.store.get_entity_edges(entity_uuid)]

            # 모든 노드 조회 (관련 노드 참조용)
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids = set()

            for edge in edges_data:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=node_data.uuid,
                name=node_data.name,
                labels=node_data.labels,
                summary=node_data.summary,
                attributes=node_data.attributes,
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"엔티티 {entity_uuid} 조회 실패: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """지정된 타입의 모든 엔티티 조회"""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
