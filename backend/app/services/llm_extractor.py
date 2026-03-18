"""
LLM 엔티티/관계 추출기
텍스트에서 엔티티와 관계를 추출하는 서비스
"""

import json
from typing import Dict, Any, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .graph_store import ExtractionResult

logger = get_logger('mirofish.llm_extractor')


class LLMEntityExtractor:
    """
    LLM 기반 엔티티/관계 추출기

    Zep Cloud의 자동 추출을 대체하여
    LLM에게 텍스트를 분석하도록 요청하고 JSON 결과를 반환
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client

    @property
    def llm(self) -> LLMClient:
        """지연 초기화 LLM 클라이언트"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def extract_from_text(
        self,
        text: str,
        ontology: Optional[Dict[str, Any]] = None,
        existing_entities: Optional[List[str]] = None
    ) -> ExtractionResult:
        """
        텍스트에서 엔티티와 관계를 추출

        Args:
            text: 분석할 텍스트
            ontology: 온톨로지 정의 (entity_types, edge_types)
            existing_entities: 이미 존재하는 엔티티 이름 목록

        Returns:
            ExtractionResult: 추출된 엔티티와 관계
        """
        prompt = self._build_extraction_prompt(text, ontology, existing_entities)

        try:
            result = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": "당신은 전문 지식 그래프 구축 어시스턴트입니다. 텍스트에서 엔티티와 관계를 추출하고, 지정된 형식에 따라 엄격하게 JSON을 반환하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=16384
            )

            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            # 엔티티 이름 맵 (id → name 매핑용)
            entity_name_map = {}
            for e in entities:
                if isinstance(e, dict):
                    eid = e.get("id", "")
                    ename = e.get("name", "")
                    if eid and ename:
                        entity_name_map[eid] = ename

            # 엔티티 유효성 검증
            valid_entities = []
            for e in entities:
                if isinstance(e, dict) and e.get("name"):
                    valid_entities.append({
                        "name": e["name"].strip(),
                        "type": e.get("type", "Entity"),
                        "summary": e.get("summary", e.get("description", "")),
                        "attributes": e.get("attributes", {}),
                    })

            # 관계 유효성 검증 (다양한 키 이름 지원)
            valid_relationships = []
            for r in relationships:
                if not isinstance(r, dict):
                    continue
                # source: source, subject, from, head 등
                source = r.get("source") or r.get("subject") or r.get("from") or r.get("head") or ""
                # target: target, object, to, tail 등
                target = r.get("target") or r.get("object") or r.get("to") or r.get("tail") or ""
                # id 참조인 경우 이름으로 변환
                source = entity_name_map.get(source, source)
                target = entity_name_map.get(target, target)

                if source and target:
                    rel_name = r.get("name") or r.get("predicate") or r.get("relation") or r.get("type") or "RELATED_TO"
                    fact = r.get("fact") or r.get("evidence") or r.get("description") or ""
                    valid_relationships.append({
                        "source": str(source).strip(),
                        "target": str(target).strip(),
                        "name": str(rel_name).strip(),
                        "fact": str(fact),
                        "attributes": r.get("attributes", {}),
                    })

            logger.info(f"텍스트 추출 완료: 엔티티 {len(valid_entities)}개, 관계 {len(valid_relationships)}개")
            return ExtractionResult(
                entities=valid_entities,
                relationships=valid_relationships
            )

        except Exception as e:
            logger.error(f"LLM 추출 실패: {e}")
            logger.debug(f"추출 실패 텍스트 (앞 200자): {text[:200]}")
            return ExtractionResult()

    def extract_from_activity(
        self,
        activity_text: str,
        existing_entities: Optional[List[str]] = None
    ) -> ExtractionResult:
        """
        시뮬레이션 활동 텍스트에서 엔티티/관계 추출 (간소화 버전)

        Args:
            activity_text: 시뮬레이션 에이전트 활동 텍스트
            existing_entities: 이미 존재하는 엔티티 이름 목록

        Returns:
            ExtractionResult: 추출된 엔티티와 관계
        """
        existing_str = ""
        if existing_entities:
            existing_str = f"\n\n알려진 엔티티 목록 (이 엔티티 이름을 우선 사용하여 중복 엔티티 생성을 방지하세요):\n{', '.join(existing_entities[:50])}"

        prompt = f"""다음 소셜 미디어 활동 기록에서 엔티티와 관계를 추출하세요.

활동 기록:
{activity_text}
{existing_str}

추출 대상:
1. 활동에 참여한 엔티티 (인물, 조직, 주제 등)
2. 엔티티 간의 관계 (상호작용, 토론, 팔로우 등)

언어 규칙: name/summary/fact는 한국어, type은 영어 PascalCase, 관계 name은 영어 UPPER_SNAKE_CASE

엄격하게 JSON 형식으로 반환:
{{
  "entities": [
    {{"name": "엔티티명 (한국어)", "type": "엔티티 유형 (영어)", "summary": "간략 설명 (한국어)"}}
  ],
  "relationships": [
    {{"source": "출발 엔티티명 (한국어)", "target": "대상 엔티티명 (한국어)", "name": "관계 유형 (영어)", "fact": "관계 사실 설명 (한국어)"}}
  ]
}}"""

        try:
            result = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": "당신은 지식 그래프 구축 어시스턴트입니다. 활동 기록에서 엔티티와 관계를 추출하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=8192
            )

            entities = [
                {"name": e["name"].strip(), "type": e.get("type", "Entity"), "summary": e.get("summary", "")}
                for e in result.get("entities", [])
                if isinstance(e, dict) and e.get("name")
            ]
            relationships = [
                {
                    "source": r["source"].strip(), "target": r["target"].strip(),
                    "name": r.get("name", "RELATED_TO"), "fact": r.get("fact", "")
                }
                for r in result.get("relationships", [])
                if isinstance(r, dict) and r.get("source") and r.get("target")
            ]

            return ExtractionResult(entities=entities, relationships=relationships)

        except Exception as e:
            logger.error(f"활동 추출 실패: {e}")
            return ExtractionResult()

    def _build_extraction_prompt(
        self,
        text: str,
        ontology: Optional[Dict[str, Any]] = None,
        existing_entities: Optional[List[str]] = None
    ) -> str:
        """추출 프롬프트 생성"""
        ontology_section = ""
        if ontology:
            entity_types = ontology.get("entity_types", [])
            edge_types = ontology.get("edge_types", [])

            if entity_types:
                type_descriptions = []
                for et in entity_types:
                    attrs = [a["name"] for a in et.get("attributes", [])]
                    attr_str = f" (속성: {', '.join(attrs)})" if attrs else ""
                    type_descriptions.append(f"  - {et['name']}: {et.get('description', '')}{attr_str}")
                ontology_section += "### 사전 정의된 엔티티 유형:\n" + "\n".join(type_descriptions) + "\n\n"

            if edge_types:
                rel_descriptions = []
                for rt in edge_types:
                    sources_targets = rt.get("source_targets", [])
                    st_str = ""
                    if sources_targets:
                        st_parts = [f"{st['source']}->{st['target']}" for st in sources_targets]
                        st_str = f" ({', '.join(st_parts)})"
                    rel_descriptions.append(f"  - {rt['name']}: {rt.get('description', '')}{st_str}")
                ontology_section += "### 사전 정의된 관계 유형:\n" + "\n".join(rel_descriptions) + "\n\n"

        existing_section = ""
        if existing_entities:
            existing_section = f"\n### 알려진 엔티티 목록 (이 이름들을 우선 사용하여 중복 생성을 방지하세요):\n{', '.join(existing_entities[:100])}\n"

        return f"""다음 텍스트에서 엔티티와 관계를 추출하여 지식 그래프를 구축하세요.

{ontology_section}{existing_section}

### 분석 대상 텍스트:
{text}

### 요구사항:
1. 텍스트에서 모든 중요한 엔티티 추출 (인물, 조직, 장소, 이벤트, 개념 등)
2. 엔티티 간의 관계 추출
3. 사전 정의된 엔티티 유형이 있으면 우선 사용
4. 알려진 엔티티가 있으면 동일한 이름을 사용하여 중복 방지

### 언어 규칙 (매우 중요!):
- "name" (엔티티 이름): 반드시 한국어 (예: "김철수", "서울대학교")
- "summary": 반드시 한국어
- "type": 영어 PascalCase (예: "Person", "University")
- 관계 "name": 영어 UPPER_SNAKE_CASE (예: "WORKS_FOR")
- "fact": 반드시 한국어

다음 JSON 형식을 엄격하게 반환 (다른 내용을 포함하지 마세요):
{{
  "entities": [
    {{
      "name": "엔티티 이름 (한국어)",
      "type": "엔티티 유형 (영어 PascalCase)",
      "summary": "엔티티 소개 (한국어)",
      "attributes": {{}}
    }}
  ],
  "relationships": [
    {{
      "source": "출발 엔티티 이름 (한국어)",
      "target": "대상 엔티티 이름 (한국어)",
      "name": "관계 유형 (영어 UPPER_SNAKE_CASE)",
      "fact": "관계의 사실 설명 (한국어)"
    }}
  ]
}}"""
