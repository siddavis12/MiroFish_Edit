"""
Neo4j 그래프 저장소 구현
GraphStore ABC의 Neo4j Community Edition 구현
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from neo4j import GraphDatabase

from ..config import Config
from ..utils.logger import get_logger
from .graph_store import (
    GraphStore, NodeData, EdgeData, SearchData, ExtractionResult, generate_uuid
)

logger = get_logger('mirofish.neo4j_store')


class Neo4jGraphStore(GraphStore):
    """
    Neo4j 기반 그래프 저장소

    그래프 모델:
    - (:Graph {graph_id, name, description, ontology_json, created_at})
    - (:Entity {uuid, name, graph_id, labels_json, summary, attributes_json, created_at})
    - (entity)-[:RELATION {uuid, name, fact, graph_id, attributes_json, created_at, valid_at, invalid_at, expired_at}]->(entity)
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        self._uri = uri or Config.NEO4J_URI
        self._user = user or Config.NEO4J_USER
        self._password = password or Config.NEO4J_PASSWORD
        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            notifications_disabled_categories=["UNRECOGNIZED"],
        )
        logger.info(f"Neo4jGraphStore 초기화: uri={self._uri}")
        self._ensure_indexes()

    def _ensure_indexes(self):
        """필수 인덱스/제약 조건 생성"""
        queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.uuid)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.graph_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Graph) ON (n.graph_id)",
        ]
        with self._driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    logger.warning(f"인덱스 생성 실패 (무시): {e}")

    def close(self):
        """드라이버 종료"""
        self._driver.close()

    # ========== GraphStore 구현 ==========

    def create_graph(self, graph_id: str, name: str, description: str = "") -> str:
        now = datetime.now().isoformat()
        with self._driver.session() as session:
            session.run(
                """
                MERGE (g:Graph {graph_id: $graph_id})
                SET g.name = $name,
                    g.description = $description,
                    g.created_at = $created_at
                """,
                graph_id=graph_id, name=name,
                description=description, created_at=now
            )
        logger.info(f"그래프 생성: graph_id={graph_id}, name={name}")
        return graph_id

    def delete_graph(self, graph_id: str) -> None:
        with self._driver.session() as session:
            # 해당 그래프의 엔티티와 관계 모두 삭제
            session.run(
                "MATCH (n:Entity {graph_id: $graph_id}) DETACH DELETE n",
                graph_id=graph_id
            )
            # 그래프 메타노드 삭제
            session.run(
                "MATCH (g:Graph {graph_id: $graph_id}) DELETE g",
                graph_id=graph_id
            )
        logger.info(f"그래프 삭제: graph_id={graph_id}")

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        ontology_json = json.dumps(ontology, ensure_ascii=False)
        with self._driver.session() as session:
            session.run(
                """
                MATCH (g:Graph {graph_id: $graph_id})
                SET g.ontology_json = $ontology_json
                """,
                graph_id=graph_id, ontology_json=ontology_json
            )
        logger.info(f"온톨로지 설정: graph_id={graph_id}")

    def get_ontology(self, graph_id: str) -> Optional[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (g:Graph {graph_id: $graph_id}) RETURN g.ontology_json AS ontology",
                graph_id=graph_id
            )
            record = result.single()
            if record and record["ontology"]:
                return json.loads(record["ontology"])
        return None

    def merge_extraction(self, graph_id: str, extraction: ExtractionResult) -> Dict[str, int]:
        """
        LLM 추출 결과를 Neo4j에 병합

        엔티티: name이 같으면 MERGE, 다르면 CREATE
        관계: source+target+name이 같으면 MERGE

        extraction.entities 형식:
            [{"name": "...", "type": "...", "summary": "...", "attributes": {...}}]
        extraction.relationships 형식:
            [{"source": "...", "target": "...", "name": "...", "fact": "...", "attributes": {...}}]
        """
        now = datetime.now().isoformat()
        nodes_created = 0
        nodes_updated = 0
        edges_created = 0

        with self._driver.session() as session:
            # 엔티티 MERGE
            for entity in extraction.entities:
                entity_name = entity.get("name", "").strip()
                if not entity_name:
                    continue

                entity_type = entity.get("type", "Entity")
                summary = entity.get("summary", "")
                attributes = entity.get("attributes", {})
                labels_list = ["Entity"]
                if entity_type and entity_type != "Entity":
                    labels_list.append(entity_type)

                result = session.run(
                    """
                    MERGE (n:Entity {name: $name, graph_id: $graph_id})
                    ON CREATE SET
                        n.uuid = $uuid,
                        n.labels_json = $labels_json,
                        n.summary = $summary,
                        n.attributes_json = $attributes_json,
                        n.created_at = $created_at
                    ON MATCH SET
                        n.labels_json = $labels_json,
                        n.summary = CASE WHEN $summary <> '' THEN $summary ELSE n.summary END,
                        n.attributes_json = $attributes_json
                    RETURN n.uuid AS uuid, n.created_at = $created_at AS is_new
                    """,
                    name=entity_name,
                    graph_id=graph_id,
                    uuid=generate_uuid(),
                    labels_json=json.dumps(labels_list, ensure_ascii=False),
                    summary=summary,
                    attributes_json=json.dumps(attributes, ensure_ascii=False),
                    created_at=now
                )
                record = result.single()
                if record and record["is_new"]:
                    nodes_created += 1
                else:
                    nodes_updated += 1

            # 관계 MERGE
            for rel in extraction.relationships:
                source_name = rel.get("source", "").strip()
                target_name = rel.get("target", "").strip()
                rel_name = rel.get("name", "RELATED_TO").strip()
                fact = rel.get("fact", "")
                attributes = rel.get("attributes", {})

                if not source_name or not target_name:
                    continue

                # 소스/타겟 노드가 없으면 생성
                result = session.run(
                    """
                    MERGE (s:Entity {name: $source_name, graph_id: $graph_id})
                    ON CREATE SET s.uuid = $s_uuid, s.labels_json = '["Entity"]',
                                  s.summary = '', s.attributes_json = '{}', s.created_at = $now
                    MERGE (t:Entity {name: $target_name, graph_id: $graph_id})
                    ON CREATE SET t.uuid = $t_uuid, t.labels_json = '["Entity"]',
                                  t.summary = '', t.attributes_json = '{}', t.created_at = $now
                    MERGE (s)-[r:RELATION {name: $rel_name, graph_id: $graph_id}]->(t)
                    ON CREATE SET
                        r.uuid = $r_uuid,
                        r.fact = $fact,
                        r.attributes_json = $attributes_json,
                        r.created_at = $now,
                        r.valid_at = $now
                    ON MATCH SET
                        r.fact = CASE WHEN $fact <> '' THEN $fact ELSE r.fact END,
                        r.attributes_json = $attributes_json
                    RETURN r.uuid AS uuid, r.created_at = $now AS is_new
                    """,
                    source_name=source_name,
                    target_name=target_name,
                    graph_id=graph_id,
                    s_uuid=generate_uuid(),
                    t_uuid=generate_uuid(),
                    r_uuid=generate_uuid(),
                    rel_name=rel_name,
                    fact=fact,
                    attributes_json=json.dumps(attributes, ensure_ascii=False),
                    now=now
                )
                record = result.single()
                if record and record["is_new"]:
                    edges_created += 1

        stats = {
            "nodes_created": nodes_created,
            "nodes_updated": nodes_updated,
            "edges_created": edges_created,
        }
        logger.info(f"추출 결과 병합 완료: graph_id={graph_id}, {stats}")
        return stats

    def get_nodes_by_graph(self, graph_id: str, limit: int = 2000) -> List[NodeData]:
        nodes = []
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (n:Entity {graph_id: $graph_id})
                RETURN n
                ORDER BY n.created_at
                LIMIT $limit
                """,
                graph_id=graph_id, limit=limit
            )
            for record in result:
                node = record["n"]
                nodes.append(self._to_node_data(node))
        return nodes

    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n:Entity {uuid: $uuid}) RETURN n",
                uuid=node_uuid
            )
            record = result.single()
            if record:
                return self._to_node_data(record["n"])
        return None

    def get_entity_edges(self, node_uuid: str) -> List[EdgeData]:
        edges = []
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Entity)-[r:RELATION]->(t:Entity)
                WHERE s.uuid = $uuid OR t.uuid = $uuid
                RETURN r, s.uuid AS s_uuid, s.name AS s_name, t.uuid AS t_uuid, t.name AS t_name
                """,
                uuid=node_uuid
            )
            for record in result:
                edges.append(self._to_edge_data(
                    record["r"],
                    record["s_uuid"], record["s_name"],
                    record["t_uuid"], record["t_name"]
                ))
        return edges

    def get_edges_by_graph(self, graph_id: str, limit: int = 5000) -> List[EdgeData]:
        edges = []
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Entity {graph_id: $graph_id})-[r:RELATION {graph_id: $graph_id}]->(t:Entity)
                RETURN r, s.uuid AS s_uuid, s.name AS s_name, t.uuid AS t_uuid, t.name AS t_name
                ORDER BY r.created_at
                LIMIT $limit
                """,
                graph_id=graph_id, limit=limit
            )
            for record in result:
                edges.append(self._to_edge_data(
                    record["r"],
                    record["s_uuid"], record["s_name"],
                    record["t_uuid"], record["t_name"]
                ))
        return edges

    def search(self, graph_id: str, query: str, limit: int = 10) -> SearchData:
        """로컬 키워드 매칭 검색"""
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            if not text:
                return 0
            text_lower = text.lower()
            if query_lower in text_lower:
                return 100
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    score += 10
            return score

        # 엣지 검색
        all_edges = self.get_edges_by_graph(graph_id)
        scored_edges = []
        for edge in all_edges:
            score = match_score(edge.fact) + match_score(edge.name)
            if score > 0:
                scored_edges.append((score, edge))
        scored_edges.sort(key=lambda x: x[0], reverse=True)

        facts = []
        result_edges = []
        for score, edge in scored_edges[:limit]:
            if edge.fact:
                facts.append(edge.fact)
            result_edges.append(edge)

        # 노드 검색
        all_nodes = self.get_nodes_by_graph(graph_id)
        scored_nodes = []
        for node in all_nodes:
            score = match_score(node.name) + match_score(node.summary)
            if score > 0:
                scored_nodes.append((score, node))
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        result_nodes = []
        for score, node in scored_nodes[:limit]:
            result_nodes.append(node)
            if node.summary:
                facts.append(f"[{node.name}]: {node.summary}")

        return SearchData(
            facts=facts,
            edges=result_edges,
            nodes=result_nodes,
            query=query,
            total_count=len(facts)
        )

    # ========== 내부 헬퍼 ==========

    def _to_node_data(self, node) -> NodeData:
        """Neo4j 노드 → NodeData 변환"""
        labels_json = node.get("labels_json", '["Entity"]')
        try:
            labels = json.loads(labels_json)
        except (json.JSONDecodeError, TypeError):
            labels = ["Entity"]

        attributes_json = node.get("attributes_json", '{}')
        try:
            attributes = json.loads(attributes_json)
        except (json.JSONDecodeError, TypeError):
            attributes = {}

        return NodeData(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=labels,
            summary=node.get("summary", ""),
            attributes=attributes,
            created_at=node.get("created_at"),
        )

    def _to_edge_data(
        self, rel, source_uuid: str, source_name: str,
        target_uuid: str, target_name: str
    ) -> EdgeData:
        """Neo4j 관계 → EdgeData 변환"""
        attributes_json = rel.get("attributes_json", '{}')
        try:
            attributes = json.loads(attributes_json)
        except (json.JSONDecodeError, TypeError):
            attributes = {}

        return EdgeData(
            uuid=rel.get("uuid", ""),
            name=rel.get("name", ""),
            fact=rel.get("fact", ""),
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
            source_node_name=source_name,
            target_node_name=target_name,
            attributes=attributes,
            created_at=rel.get("created_at"),
            valid_at=rel.get("valid_at"),
            invalid_at=rel.get("invalid_at"),
            expired_at=rel.get("expired_at"),
        )
