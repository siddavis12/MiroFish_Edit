"""
OASIS Agent Profile 생성기
Zep 그래프의 엔티티를 OASIS 시뮬레이션 플랫폼에 필요한 Agent Profile 형식으로 변환

최적화 개선:
1. Zep 검색 기능을 호출하여 노드 정보를 2차적으로 풍부하게 보강
2. 프롬프트를 최적화하여 매우 상세한 페르소나 생성
3. 개인 엔티티와 추상 그룹 엔티티 구분
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


def _normalize_topics(value) -> list:
    """LLM이 문자열로 반환한 토픽 배열을 list로 정규화"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        v = value.strip()
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        # 대괄호 제거 후 쉼표 분리 (e.g. "[a, b, c]" → ["a", "b", "c"])
        v = v.strip("[]")
        return [t.strip().strip('"\'') for t in v.split(",") if t.strip()]
    return []

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .entity_reader import EntityNode, EntityReader
from .neo4j_store import Neo4jGraphStore
from .chroma_store import ChromaSearchService

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile 데이터 구조"""
    # 공통 필드
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 선택 필드 - Reddit 스타일
    karma: int = 1000
    
    # 선택 필드 - Twitter 스타일
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 추가 페르소나 정보
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # 출처 엔티티 정보
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None

    # 입장/감정 정합성 (시뮬레이션 설정과 공유)
    stance: Optional[str] = None           # supportive, opposing, neutral, observer
    sentiment_bias: Optional[float] = None  # -1.0 ~ 1.0
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """Reddit 플랫폼 형식으로 변환"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리가 요구하는 필드명은 username (밑줄 없음)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 추가 페르소나 정보 추가 (있는 경우)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        if self.source_entity_type:
            profile["entity_type"] = self.source_entity_type
        if self.stance:
            profile["stance"] = self.stance
        if self.sentiment_bias is not None:
            profile["sentiment_bias"] = self.sentiment_bias

        return profile

    def to_twitter_format(self) -> Dict[str, Any]:
        """Twitter 플랫폼 형식으로 변환"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리가 요구하는 필드명은 username (밑줄 없음)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 추가 페르소나 정보 추가
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        if self.stance:
            profile["stance"] = self.stance
        if self.sentiment_bias is not None:
            profile["sentiment_bias"] = self.sentiment_bias

        return profile

    def to_dict(self) -> Dict[str, Any]:
        """전체 딕셔너리 형식으로 변환"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "stance": self.stance,
            "sentiment_bias": self.sentiment_bias,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile 생성기
    
    Zep 그래프의 엔티티를 OASIS 시뮬레이션에 필요한 Agent Profile로 변환
    
    최적화 특성:
    1. Zep 그래프 검색 기능을 호출하여 더 풍부한 컨텍스트 획득
    2. 매우 상세한 페르소나 생성 (기본 정보, 직업 경력, 성격 특성, 소셜 미디어 행동 등 포함)
    3. 개인 엔티티와 추상 그룹 엔티티 구분
    """
    
    # MBTI 유형 목록
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 일반적인 국가 목록 (한국어)
    COUNTRIES = [
        "중국", "미국", "영국", "일본", "독일", "프랑스",
        "캐나다", "호주", "브라질", "인도", "한국"
    ]

    # 기관 적합 MBTI 유형 (다양성 확보)
    INSTITUTION_MBTI_TYPES = ["ISTJ", "ESTJ", "ENTJ", "INTJ", "ENFJ", "INFJ"]
    
    # 개인 유형 엔티티 (구체적인 페르소나 생성 필요)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # 그룹/기관 유형 엔티티 (그룹 대표 페르소나 생성 필요)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.model_name = model_name or Config.LLM_MODEL_NAME
        self.llm = LLMClient(api_key=api_key, model=model_name)

        # 로컬 검색 서비스 (Zep 대체)
        self.graph_id = graph_id
        self.store = Neo4jGraphStore()
        self.chroma = ChromaSearchService()
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Zep 엔티티에서 OASIS Agent Profile 생성
        
        Args:
            entity: Zep 엔티티 노드
            user_id: 사용자 ID (OASIS용)
            use_llm: LLM을 사용하여 상세 페르소나 생성 여부
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # 기본 정보
        name = entity.name
        user_name = self._generate_username(name)
        
        # 컨텍스트 정보 구성
        context = self._build_entity_context(entity)
        
        if use_llm:
            # LLM을 사용하여 상세 페르소나 생성
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 규칙 기반으로 기본 페르소나 생성
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=_normalize_topics(profile_data.get("interested_topics", [])),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
            stance=profile_data.get("stance"),
            sentiment_bias=profile_data.get("sentiment_bias"),
        )
    
    def _generate_username(self, name: str) -> str:
        """사용자명 생성"""
        # 특수 문자 제거, 소문자로 변환
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 중복 방지를 위해 랜덤 접미사 추가
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Chroma 벡터 검색을 사용하여 엔티티 관련 풍부한 정보 획득 (기존 Zep 검색 대체)

        edges와 nodes를 각각 검색한 후 결과를 병합합니다.

        Args:
            entity: 엔티티 노드 객체

        Returns:
            facts, node_summaries, context를 포함하는 딕셔너리
        """
        import concurrent.futures

        entity_name = entity.name

        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }

        # graph_id가 있어야 검색 가능
        if not self.graph_id:
            logger.debug(f"검색 건너뛰기: graph_id 미설정")
            return results

        comprehensive_query = f"{entity_name}에 대한 모든 정보, 활동, 사건, 관계 및 배경"

        def search_edges():
            """엣지(사실/관계) 검색 - 재시도 메커니즘 포함"""
            max_retries = 3
            delay = 2.0

            for attempt in range(max_retries):
                try:
                    return self.chroma.search(
                        graph_id=self.graph_id,
                        query=comprehensive_query,
                        limit=30,
                        scope="edges"
                    )
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"엣지 검색 {attempt + 1}번째 실패: {str(e)[:80]}, 재시도 중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"엣지 검색이 {max_retries}회 시도 후에도 실패: {e}")
            return None

        def search_nodes():
            """노드(엔티티 요약) 검색 - 재시도 메커니즘 포함"""
            max_retries = 3
            delay = 2.0

            for attempt in range(max_retries):
                try:
                    return self.chroma.search(
                        graph_id=self.graph_id,
                        query=comprehensive_query,
                        limit=20,
                        scope="nodes"
                    )
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"노드 검색 {attempt + 1}번째 실패: {str(e)[:80]}, 재시도 중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"노드 검색이 {max_retries}회 시도 후에도 실패: {e}")
            return None

        try:
            # edges와 nodes 검색을 병렬 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)

                # 결과 가져오기
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)

            # 엣지 검색 결과 처리 (SearchData 객체)
            all_facts = set()
            if edge_result and edge_result.facts:
                for fact in edge_result.facts:
                    if fact:
                        all_facts.add(fact)
            results["facts"] = list(all_facts)

            # 노드 검색 결과 처리 (SearchData 객체)
            all_summaries = set()
            if node_result and node_result.nodes:
                for node in node_result.nodes:
                    if node.summary:
                        all_summaries.add(node.summary)
                    if node.name and node.name != entity_name:
                        all_summaries.add(f"관련 엔티티: {node.name}")
            results["node_summaries"] = list(all_summaries)

            # 종합 컨텍스트 구성
            context_parts = []
            if results["facts"]:
                context_parts.append("사실 정보:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("관련 엔티티:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)

            logger.info(f"하이브리드 검색 완료: {entity_name}, {len(results['facts'])}건 사실, {len(results['node_summaries'])}개 관련 노드 획득")

        except concurrent.futures.TimeoutError:
            logger.warning(f"검색 타임아웃 ({entity_name})")
        except Exception as e:
            logger.warning(f"검색 실패 ({entity_name}): {e}")

        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        엔티티의 완전한 컨텍스트 정보 구성
        
        포함:
        1. 엔티티 자체의 엣지 정보 (사실)
        2. 관련 노드의 상세 정보
        3. Zep 하이브리드 검색으로 획득한 풍부한 정보
        """
        context_parts = []
        
        # 1. 엔티티 속성 정보 추가
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### 엔티티 속성\n" + "\n".join(attrs))
        
        # 2. 관련 엣지 정보 추가 (사실/관계)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 수량 제한 없음
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (관련 엔티티)")
                    else:
                        relationships.append(f"- (관련 엔티티) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 관련 사실 및 관계\n" + "\n".join(relationships))
        
        # 3. 관련 노드의 상세 정보 추가
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 수량 제한 없음
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 기본 라벨 필터링
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 관련 엔티티 정보\n" + "\n".join(related_info))
        
        # 4. Zep 하이브리드 검색으로 더 풍부한 정보 획득
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 중복 제거: 이미 존재하는 사실 제외
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep 검색으로 획득한 사실 정보\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep 검색으로 획득한 관련 노드\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """개인 유형 엔티티인지 판단"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """그룹/기관 유형 엔티티인지 판단"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _extract_country_hint(self, entity_attributes: Dict[str, Any]) -> Optional[str]:
        """엔티티 속성에서 국가/지역 힌트 추출"""
        country_keys = ["country", "국가", "headquarters", "본사", "location", "소재지", "region", "지역"]
        if not entity_attributes:
            return None
        for key in country_keys:
            for attr_key, attr_value in entity_attributes.items():
                if key in attr_key.lower() and attr_value:
                    return str(attr_value).strip()
        return None

    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        LLM을 사용하여 매우 상세한 페르소나 생성

        엔티티 유형에 따라 구분:
        - 개인 엔티티: 구체적인 인물 설정 생성
        - 그룹/기관 엔티티: 대표 계정 설정 생성
        """

        is_individual = self._is_individual_entity(entity_type)

        # 엔티티 속성에서 국가 힌트 추출
        country_hint = self._extract_country_hint(entity_attributes)

        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context,
                country_hint=country_hint
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context,
                country_hint=country_hint
            )

        # LLMClient의 chat_with_retry를 사용하여 재시도 + reasoning 모델 자동 지원
        messages = [
            {"role": "system", "content": self._get_system_prompt(is_individual)},
            {"role": "user", "content": prompt}
        ]

        try:
            content, finish_reason = self.llm.chat_with_retry(
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            # 잘림 여부 확인
            if finish_reason == 'length':
                logger.warning("LLM 출력 잘림, 수정 시도...")
                content = self._fix_truncated_json(content)

            # JSON 파싱 시도
            try:
                result = json.loads(content)

                # 필수 필드 검증
                if "bio" not in result or not result["bio"]:
                    result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                if "persona" not in result or not result["persona"]:
                    result["persona"] = entity_summary or f"{entity_name}은(는) {entity_type}입니다."

                return result

            except json.JSONDecodeError as je:
                logger.warning(f"JSON 파싱 실패: {str(je)[:80]}")

                # JSON 수정 시도
                result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                if result.get("_fixed"):
                    del result["_fixed"]
                    return result

                raise

        except Exception as e:
            logger.warning(f"LLM 페르소나 생성 실패: {e}, 규칙 기반 생성 사용")
            return self._generate_profile_rule_based(
                entity_name, entity_type, entity_summary, entity_attributes
            )
    
    def _fix_truncated_json(self, content: str) -> str:
        """잘린 JSON 수정 (출력이 max_tokens 제한으로 잘림)"""
        import re
        
        # JSON이 잘리면 닫기 시도
        content = content.strip()
        
        # 닫히지 않은 괄호 계산
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # 닫히지 않은 문자열 확인
        # 단순 확인: 마지막 따옴표 뒤에 쉼표나 닫는 괄호가 없으면 문자열이 잘렸을 수 있음
        if content and content[-1] not in '",}]':
            # 문자열 닫기 시도
            content += '"'
        
        # 괄호 닫기
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """손상된 JSON 수정 시도"""
        import re
        
        # 1. 먼저 잘린 경우 수정 시도
        content = self._fix_truncated_json(content)
        
        # 2. JSON 부분 추출 시도
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. 문자열의 줄바꿈 문제 처리
            # 모든 문자열 값을 찾아 줄바꿈을 교체
            def fix_string_newlines(match):
                s = match.group(0)
                # 문자열 내 실제 줄바꿈을 공백으로 교체
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 불필요한 공백 교체
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # JSON 문자열 값 매칭
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 파싱 시도
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. 여전히 실패하면 더 적극적인 수정 시도
                try:
                    # 모든 제어 문자 제거
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 모든 연속 공백 교체
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 내용에서 부분 정보 추출 시도
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 잘렸을 수 있음
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}은(는) {entity_type}입니다.")
        
        # 의미 있는 내용을 추출했으면 수정됨으로 표시
        if bio_match or persona_match:
            logger.info(f"손상된 JSON에서 부분 정보 추출됨")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. 완전히 실패, 기본 구조 반환
        logger.warning(f"JSON 수정 실패, 기본 구조 반환")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}은(는) {entity_type}입니다."
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """시스템 프롬프트 가져오기"""
        base_prompt = "당신은 소셜 미디어 사용자 프로필 생성 전문가입니다. 여론 시뮬레이션용 상세하고 현실적인 페르소나를 생성하며, 기존 현실 상황을 최대한 재현합니다. 유효한 JSON 형식을 반환해야 하며, 모든 문자열 값에 이스케이프되지 않은 줄바꿈을 포함할 수 없습니다. 한국어를 사용하세요. stance와 sentiment_bias는 persona 텍스트의 입장/태도와 반드시 일관성을 유지하세요. 비판적 톤이면 stance는 'opposing', sentiment_bias는 음수여야 합니다. 지지적 톤이면 stance는 'supportive', sentiment_bias는 양수여야 합니다."
        return base_prompt
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
        country_hint: Optional[str] = None
    ) -> str:
        """개인 엔티티의 상세 페르소나 프롬프트 구성"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "추가 컨텍스트 없음"

        # 국가 힌트가 있으면 프롬프트에 명시
        country_hint_str = ""
        if country_hint:
            country_hint_str = f"\n참고: 이 엔티티의 소재 국가 힌트: {country_hint}"

        return f"""엔티티에 대한 상세한 소셜 미디어 사용자 페르소나를 생성하며, 기존 현실 상황을 최대한 재현합니다.

엔티티 이름: {entity_name}
엔티티 유형: {entity_type}
엔티티 요약: {entity_summary}
엔티티 속성: {attrs_str}{country_hint_str}

컨텍스트 정보:
{context_str}

다음 필드를 포함하는 JSON을 생성하세요:

1. bio: 소셜 미디어 소개, 200자
2. persona: 상세 페르소나 설명 (2000자 순수 텍스트), 다음을 포함해야 함:
   - 기본 정보 (나이, 직업, 교육 배경, 소재지)
   - 인물 배경 (중요한 경험, 사건과의 연관, 사회적 관계)
   - 성격 특성 (MBTI 유형, 핵심 성격, 감정 표현 방식)
   - 소셜 미디어 행동 (게시 빈도, 콘텐츠 선호, 상호작용 스타일, 언어 특성)
   - 입장 관점 (주제에 대한 태도, 분노/감동을 유발할 수 있는 내용)
   - 독특한 특징 (말버릇, 특별한 경험, 개인 취미)
   - 개인 기억 (페르소나의 중요 부분, 이 개인과 사건의 연관, 그리고 사건에서의 기존 행동과 반응 소개)
3. age: 나이 숫자 (반드시 정수)
4. gender: 성별, 반드시 영어: "male" 또는 "female"
5. mbti: MBTI 유형 (16가지 중 엔티티의 성격/행동 패턴에 가장 부합하는 유형 선택. 다양한 유형을 고려하세요)
6. country: 국가 (한국어로 작성). 엔티티 속성에 headquarters, location, country, 소재지 등의 정보가 있으면 반드시 그 정보를 기반으로 국가를 결정하세요. 실제 존재하는 엔티티라면 실제 본사/본거지 소재 국가를 사용하세요.
7. profession: 직업
8. interested_topics: 관심 주제 배열
9. stance: 시뮬레이션 주제에 대한 입장. "supportive"/"opposing"/"neutral"/"observer" 중 하나. persona 텍스트의 입장/관점과 반드시 일치.
10. sentiment_bias: 감정 성향 (-1.0~1.0). persona의 톤/태도와 반드시 일치. 비판적이면 음수, 지지적이면 양수, 중립이면 0 근처.

중요:
- 모든 필드 값은 문자열 또는 숫자여야 하며, 줄바꿈을 사용하지 마세요
- persona는 하나의 연결된 텍스트 설명이어야 합니다
- 한국어를 사용하세요 (gender 필드는 반드시 영어 male/female)
- 내용은 엔티티 정보와 일관성을 유지해야 합니다
- age는 유효한 정수, gender는 "male" 또는 "female"이어야 합니다
- stance와 sentiment_bias는 persona 텍스트의 입장/태도와 반드시 정합성을 유지해야 합니다
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
        country_hint: Optional[str] = None
    ) -> str:
        """그룹/기관 엔티티의 상세 페르소나 프롬프트 구성"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "추가 컨텍스트 없음"

        # 국가 힌트가 있으면 프롬프트에 명시
        country_hint_str = ""
        if country_hint:
            country_hint_str = f"\n참고: 이 엔티티의 소재 국가 힌트: {country_hint}"

        return f"""기관/그룹 엔티티에 대한 상세한 소셜 미디어 계정 설정을 생성하며, 기존 현실 상황을 최대한 재현합니다.

엔티티 이름: {entity_name}
엔티티 유형: {entity_type}
엔티티 요약: {entity_summary}
엔티티 속성: {attrs_str}{country_hint_str}

컨텍스트 정보:
{context_str}

다음 필드를 포함하는 JSON을 생성하세요:

1. bio: 공식 계정 소개, 200자, 전문적이고 적절하게
2. persona: 상세 계정 설정 설명 (2000자 순수 텍스트), 다음을 포함해야 함:
   - 기관 기본 정보 (정식 명칭, 기관 성격, 설립 배경, 주요 기능)
   - 계정 포지셔닝 (계정 유형, 타깃 오디언스, 핵심 기능)
   - 발언 스타일 (언어 특성, 자주 사용하는 표현, 금기 주제)
   - 게시 콘텐츠 특성 (콘텐츠 유형, 게시 빈도, 활동 시간대)
   - 입장 태도 (핵심 주제에 대한 공식 입장, 논란에 대한 대응 방식)
   - 특별 참고사항 (대표하는 그룹 프로필, 운영 습관)
   - 기관 기억 (기관 페르소나의 중요 부분, 이 기관과 사건의 연관, 그리고 사건에서의 기존 행동과 반응 소개)
3. age: 고정값 30 (기관 계정의 가상 나이)
4. gender: 고정값 "other" (기관 계정은 other로 비개인 표시)
5. mbti: MBTI 유형, 계정의 커뮤니케이션 스타일을 반영 (예: ENTJ=리더십, ENFJ=소통중심, ISTJ=원칙적, ESTP=행동지향 등)
6. country: 국가 (한국어로 작성). 엔티티 속성에 headquarters, location, country, 소재지 등의 정보가 있으면 반드시 그 정보를 기반으로 국가를 결정하세요. 실제 존재하는 기관이라면 실제 본사/본부 소재 국가를 사용하세요.
7. profession: 기관 기능 설명
8. interested_topics: 관심 분야 배열
9. stance: 시뮬레이션 주제에 대한 입장. "supportive"/"opposing"/"neutral"/"observer" 중 하나. persona 텍스트의 입장/관점과 반드시 일치.
10. sentiment_bias: 감정 성향 (-1.0~1.0). persona의 톤/태도와 반드시 일치.

중요:
- 모든 필드 값은 문자열 또는 숫자여야 하며, null 값은 허용되지 않음
- persona는 하나의 연결된 텍스트 설명이어야 합니다, 줄바꿈을 사용하지 마세요
- 한국어를 사용하세요 (gender 필드는 반드시 영어 "other")
- age는 반드시 정수 30, gender는 반드시 문자열 "other"
- 기관 계정 발언은 그 신원 포지셔닝에 부합해야 함
- stance와 sentiment_bias는 persona 텍스트의 입장/태도와 반드시 정합성을 유지해야 합니다"""
    
    # 개인(사람) 엔티티 유형 목록
    INDIVIDUAL_ENTITY_TYPES = {
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist",
        "politician", "leader", "researcher", "analyst", "citizen"
    }

    def _is_individual_entity(self, entity_type_lower: str) -> bool:
        """엔티티 유형이 개인(사람)인지 판별"""
        return entity_type_lower in self.INDIVIDUAL_ENTITY_TYPES

    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """규칙 기반으로 기본 페르소나 생성"""

        # 엔티티 속성에서 국가 힌트 추출
        country_hint = self._extract_country_hint(entity_attributes)

        # 엔티티 유형에 따라 다른 페르소나 생성
        entity_type_lower = entity_type.lower()

        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"학업과 사회 문제에 관심이 있는 {entity_name}.",
                "persona": f"{entity_name}은(는) 학업 및 사회적 토론에 적극적으로 참여하는 학생입니다. 동료들과 소통하고 다양한 관점을 공유하는 것을 즐깁니다.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": country_hint or random.choice(self.COUNTRIES),
                "profession": "학생",
                "interested_topics": ["교육", "사회 이슈", "기술"],
                "stance": "neutral",
                "sentiment_bias": round(random.uniform(-0.3, 0.3), 2),
            }

        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"해당 분야의 전문가이자 오피니언 리더인 {entity_name}.",
                "persona": f"{entity_name}은(는) 중요한 사안에 대해 전문적인 견해와 통찰을 공유하는 인물입니다. 공론장에서의 전문성과 영향력으로 알려져 있습니다.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": country_hint or random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "전문가"),
                "interested_topics": ["정치", "경제", "문화와 사회"],
                "stance": "neutral",
                "sentiment_bias": 0.0,
            }

        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"{entity_name}의 공식 계정. 뉴스 및 최신 소식 제공.",
                "persona": f"{entity_name}은(는) 뉴스를 보도하고 공론을 촉진하는 미디어입니다. 시의적절한 소식을 전달하고 현안에 대해 독자와 소통합니다.",
                "age": 30,
                "gender": "other",
                "mbti": random.choice(self.INSTITUTION_MBTI_TYPES),
                "country": country_hint or random.choice(self.COUNTRIES),
                "profession": "미디어",
                "interested_topics": ["종합 뉴스", "시사", "공공 문제"],
                "stance": "observer",
                "sentiment_bias": 0.0,
            }

        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"{entity_name}의 공식 계정.",
                "persona": f"{entity_name}은(는) 공식 입장과 공지사항을 전달하고 이해관계자와 소통하는 기관입니다.",
                "age": 30,
                "gender": "other",
                "mbti": random.choice(self.INSTITUTION_MBTI_TYPES),
                "country": country_hint or random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["공공 정책", "커뮤니티", "공식 발표"],
                "stance": "neutral",
                "sentiment_bias": 0.0,
            }

        else:
            # 개인 엔티티 여부 판별 후 분기
            if self._is_individual_entity(entity_type_lower):
                return {
                    "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                    "persona": entity_summary or f"{entity_name}은(는) 사회적 토론에 참여하는 참가자입니다.",
                    "age": random.randint(25, 50),
                    "gender": random.choice(["male", "female"]),
                    "mbti": random.choice(self.MBTI_TYPES),
                    "country": country_hint or random.choice(self.COUNTRIES),
                    "profession": entity_type,
                    "interested_topics": ["일반", "사회 이슈"],
                    "stance": "neutral",
                    "sentiment_bias": 0.0,
                }
            else:
                # 비인간 엔티티 (기관/이벤트/국가 등)
                return {
                    "bio": entity_summary[:150] if entity_summary else f"{entity_name}의 공식 계정.",
                    "persona": entity_summary or f"{entity_name}은(는) 공식 입장과 정보를 전달하는 기관/단체입니다.",
                    "age": 30,
                    "gender": "other",
                    "mbti": random.choice(self.INSTITUTION_MBTI_TYPES),
                    "country": country_hint or random.choice(self.COUNTRIES),
                    "profession": entity_type,
                    "interested_topics": ["일반", "사회 이슈"],
                    "stance": "neutral",
                    "sentiment_bias": 0.0,
                }
    
    def set_graph_id(self, graph_id: str):
        """Zep 검색용 그래프 ID 설정"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        엔티티에서 Agent Profile 일괄 생성 (병렬 생성 지원)
        
        Args:
            entities: 엔티티 목록
            use_llm: LLM을 사용하여 상세 페르소나 생성 여부
            progress_callback: 진행 상황 콜백 함수 (current, total, message)
            graph_id: 그래프 ID, Zep 검색으로 더 풍부한 컨텍스트 획득용
            parallel_count: 병렬 생성 수, 기본값 5
            realtime_output_path: 실시간 기록 파일 경로 (제공되면 하나 생성할 때마다 기록)
            output_platform: 출력 플랫폼 형식 ("reddit" 또는 "twitter")
            
        Returns:
            Agent Profile 목록
        """
        import concurrent.futures
        from threading import Lock
        
        # Zep 검색용 graph_id 설정
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # 순서 유지를 위해 목록 사전 할당
        completed_count = [0]  # 클로저에서 수정 가능하도록 목록 사용
        lock = Lock()
        
        # 실시간 파일 기록 보조 함수
        def save_profiles_realtime():
            """이미 생성된 profiles을 파일에 실시간 저장"""
            if not realtime_output_path:
                return
            
            with lock:
                # 이미 생성된 profiles 필터링
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON 형식
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV 형식
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"profiles 실시간 저장 실패: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """단일 profile 생성 작업 함수"""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # 생성된 페르소나를 콘솔과 로그에 실시간 출력
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"엔티티 {entity.name}의 페르소나 생성 실패: {str(e)}")
                # 기본 profile 생성
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or "사회적 토론에 참여하는 참가자.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"{total}개 Agent 페르소나 병렬 생성 시작 (병렬 수: {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"Agent 페르소나 생성 시작 - 총 {total}개 엔티티, 병렬 수: {parallel_count}")
        print(f"{'='*60}\n")
        
        # 스레드 풀로 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 모든 작업 제출
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # 결과 수집
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # 실시간 파일 기록
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"{current}/{total} 완료: {entity.name} ({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 대체 페르소나 사용: {error}")
                    else:
                        logger.info(f"[{current}/{total}] 페르소나 생성 성공: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"엔티티 {entity.name} 처리 중 예외 발생: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "사회적 토론에 참여하는 참가자.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 실시간 파일 기록 (대체 페르소나라도)
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"페르소나 생성 완료! 총 {len([p for p in profiles if p])}개 Agent 생성됨")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """생성된 페르소나를 콘솔에 실시간 출력 (전체 내용, 잘림 없음)"""
        separator = "-" * 70
        
        # 전체 출력 내용 구성 (잘림 없음)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '없음'
        
        output_lines = [
            f"\n{separator}",
            f"[생성 완료] {entity_name} ({entity_type})",
            f"{separator}",
            f"사용자명: {profile.user_name}",
            f"",
            f"【소개】",
            f"{profile.bio}",
            f"",
            f"【상세 페르소나】",
            f"{profile.persona}",
            f"",
            f"【기본 속성】",
            f"나이: {profile.age} | 성별: {profile.gender} | MBTI: {profile.mbti}",
            f"직업: {profile.profession} | 국가: {profile.country}",
            f"입장: {profile.stance or 'N/A'} | 감정 성향: {profile.sentiment_bias if profile.sentiment_bias is not None else 'N/A'}",
            f"관심 주제: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # 콘솔에만 출력 (중복 방지, logger는 전체 내용을 출력하지 않음)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Profile을 파일에 저장 (플랫폼에 따라 올바른 형식 선택)
        
        OASIS 플랫폼 형식 요구사항:
        - Twitter: CSV 형식
        - Reddit: JSON 형식
        
        Args:
            profiles: Profile 목록
            file_path: 파일 경로
            platform: 플랫폼 유형 ("reddit" 또는 "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Twitter Profile을 CSV 형식으로 저장 (OASIS 공식 요구사항 준수)
        
        OASIS Twitter에서 요구하는 CSV 필드:
        - user_id: 사용자 ID (CSV 순서에 따라 0부터 시작)
        - name: 사용자 실제 이름
        - username: 시스템의 사용자명
        - user_char: 상세 페르소나 설명 (LLM 시스템 프롬프트에 주입되어 Agent 행동 안내)
        - description: 짧은 공개 소개 (사용자 프로필 페이지에 표시)
        
        user_char vs description 차이:
        - user_char: 내부 사용, LLM 시스템 프롬프트, Agent의 사고와 행동 결정
        - description: 외부 표시, 다른 사용자에게 보이는 소개
        """
        import csv
        
        # 파일 확장자가 .csv인지 확인
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # OASIS에서 요구하는 헤더 작성
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # 데이터 행 작성
            for idx, profile in enumerate(profiles):
                # user_char: 전체 페르소나 (bio + persona), LLM 시스템 프롬프트용
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # 줄바꿈 처리 (CSV에서는 공백으로 대체)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: 짧은 소개, 외부 표시용
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: 0부터 시작하는 순서 ID
                    profile.name,           # name: 실제 이름
                    profile.user_name,      # username: 사용자명
                    user_char,              # user_char: 전체 페르소나 (내부 LLM 사용)
                    description             # description: 짧은 소개 (외부 표시)
                ]
                writer.writerow(row)
        
        logger.info(f"{len(profiles)}개 Twitter Profile을 {file_path}에 저장 (OASIS CSV 형식)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        gender 필드를 OASIS에서 요구하는 영문 형식으로 표준화
        
        OASIS 요구사항: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # 한국어 매핑
        gender_map = {
            "남": "male",
            "여": "female",
            "기관": "other",
            "기타": "other",
            # 영어 이미 존재
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Reddit Profile을 JSON 형식으로 저장
        
        to_reddit_format()과 일치하는 형식 사용, OASIS가 올바르게 읽을 수 있도록 보장.
        user_id 필드를 반드시 포함해야 하며, 이것이 OASIS agent_graph.get_agent() 매칭의 핵심!
        
        필수 필드:
        - user_id: 사용자 ID (정수, initial_posts의 poster_agent_id 매칭용)
        - username: 사용자명
        - name: 표시 이름
        - bio: 소개
        - persona: 상세 페르소나
        - age: 나이 (정수)
        - gender: "male", "female", 또는 "other"
        - mbti: MBTI 유형
        - country: 국가
        """
        data = []
        for idx, profile in enumerate(profiles):
            # to_reddit_format()과 일치하는 형식 사용
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # 핵심: user_id 반드시 포함
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS 필수 필드 - 모두 기본값 보장
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else random.choice(["ISTJ", "ESTJ", "ENTJ", "INTJ"]),
                "country": profile.country if profile.country else random.choice(self.COUNTRIES),
            }
            
            # 선택 필드
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            if profile.source_entity_type:
                item["entity_type"] = profile.source_entity_type
            if profile.stance:
                item["stance"] = profile.stance
            if profile.sentiment_bias is not None:
                item["sentiment_bias"] = profile.sentiment_bias

            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"{len(profiles)}개 Reddit Profile을 {file_path}에 저장 (JSON 형식, user_id 필드 포함)")
    
    def verify_and_enhance_diversity(
        self,
        profiles: List[OasisAgentProfile],
        similarity_threshold: float = 0.85,
        max_regen_attempts: int = 2,
        simulation_requirement: str = "",
        entities: Optional[List] = None,
    ) -> List[OasisAgentProfile]:
        """
        ChromaDB 임베딩(all-MiniLM-L6-v2)으로 코사인 유사도 계산 → 유사한 쌍 재생성

        Args:
            profiles: 생성된 프로필 목록
            similarity_threshold: 유사도 임계값 (이 이상이면 재생성)
            max_regen_attempts: 최대 재생성 시도 횟수
            simulation_requirement: 시뮬레이션 요구사항
            entities: 엔티티 목록 (재생성 시 컨텍스트용)

        Returns:
            다양성이 보장된 프로필 목록
        """
        import chromadb

        if len(profiles) < 2:
            return profiles

        # 엔티티 UUID → 엔티티 매핑 구축
        entity_map = {}
        if entities:
            for e in entities:
                entity_map[e.uuid] = e

        for attempt in range(max_regen_attempts):
            # 임시 인메모리 ChromaDB 컬렉션 생성
            client = chromadb.Client()
            collection_name = f"diversity_check_{attempt}"
            collection = client.create_collection(name=collection_name)

            # 모든 persona 텍스트 임베딩
            persona_texts = [p.persona or "" for p in profiles]
            ids = [str(i) for i in range(len(profiles))]
            collection.add(documents=persona_texts, ids=ids)

            # 유사 쌍 식별
            similar_pairs = []
            for i, profile in enumerate(profiles):
                results = collection.query(
                    query_texts=[persona_texts[i]],
                    n_results=2,  # self + 가장 유사한 것
                )
                if results and results["distances"] and results["distances"][0]:
                    for j, (dist, rid) in enumerate(zip(results["distances"][0], results["ids"][0])):
                        other_idx = int(rid)
                        if other_idx != i:
                            # ChromaDB 기본 거리는 L2; 코사인 유사도로 변환
                            # cosine_similarity ≈ 1 - (l2_distance^2 / 2) for normalized vectors
                            similarity = 1.0 - (dist / 2.0) if dist < 2.0 else 0.0
                            if similarity > similarity_threshold:
                                pair = tuple(sorted([i, other_idx]))
                                if pair not in similar_pairs:
                                    similar_pairs.append(pair)

            # 임시 컬렉션 삭제
            client.delete_collection(collection_name)

            if not similar_pairs:
                logger.info(f"다양성 검증 완료 (시도 {attempt + 1}): 유사 쌍 없음, 모든 프로필이 충분히 다양함")
                return profiles

            logger.info(f"다양성 검증 (시도 {attempt + 1}): {len(similar_pairs)}개 유사 쌍 발견, 재생성 시도")

            # 쌍 중 컨텍스트가 적은 쪽을 재생성
            regen_indices = set()
            for i, j in similar_pairs:
                # persona 길이가 짧은 쪽을 재생성 대상으로 선택
                if len(profiles[i].persona or "") <= len(profiles[j].persona or ""):
                    regen_indices.add(i)
                else:
                    regen_indices.add(j)

            for idx in regen_indices:
                profile = profiles[idx]
                # 유사한 상대 프로필 찾기
                similar_profile = None
                for i, j in similar_pairs:
                    other = j if i == idx else (i if j == idx else None)
                    if other is not None:
                        similar_profile = profiles[other]
                        break

                if similar_profile is None:
                    continue

                # 차별화 재생성
                entity = entity_map.get(profile.source_entity_uuid)
                if entity:
                    new_profile = self._regenerate_with_differentiation(
                        profile=profile,
                        similar_profile=similar_profile,
                        entity=entity,
                        simulation_requirement=simulation_requirement,
                    )
                    if new_profile:
                        profiles[idx] = new_profile
                        logger.info(f"프로필 재생성 완료: {profile.name} (인덱스 {idx})")

        logger.info(f"다양성 검증 및 보강 완료: {len(profiles)}개 프로필")
        return profiles

    def _regenerate_with_differentiation(
        self,
        profile: OasisAgentProfile,
        similar_profile: OasisAgentProfile,
        entity: 'EntityNode',
        simulation_requirement: str = "",
    ) -> Optional[OasisAgentProfile]:
        """유사한 프로필과 차별화된 페르소나 재생성"""
        entity_type = entity.get_entity_type() or "Entity"
        is_individual = self._is_individual_entity(entity_type)
        context = self._build_entity_context(entity)

        differentiation_hint = f"""
중요: 이미 시뮬레이션에 다음 페르소나가 존재합니다:
---
{similar_profile.persona[:500]}
---
당신의 페르소나는 위와 명확히 차별화되어야 합니다.
고유한 경험, 다른 커뮤니케이션 스타일, 다른 감정 반응 패턴에 집중하세요.
stance나 sentiment_bias도 가능하다면 다르게 설정하세요.
"""

        country_hint = self._extract_country_hint(entity.attributes)

        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity.name, entity_type, entity.summary, entity.attributes, context,
                country_hint=country_hint
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity.name, entity_type, entity.summary, entity.attributes, context,
                country_hint=country_hint
            )

        prompt = differentiation_hint + "\n" + prompt

        messages = [
            {"role": "system", "content": self._get_system_prompt(is_individual)},
            {"role": "user", "content": prompt}
        ]

        try:
            content, finish_reason = self.llm.chat_with_retry(
                messages=messages,
                temperature=0.9,  # 다양성을 위해 높은 temperature
                response_format={"type": "json_object"}
            )

            if finish_reason == 'length':
                content = self._fix_truncated_json(content)

            profile_data = json.loads(content)

            return OasisAgentProfile(
                user_id=profile.user_id,
                user_name=profile.user_name,
                name=profile.name,
                bio=profile_data.get("bio", profile.bio),
                persona=profile_data.get("persona", profile.persona),
                karma=profile_data.get("karma", profile.karma),
                friend_count=profile_data.get("friend_count", profile.friend_count),
                follower_count=profile_data.get("follower_count", profile.follower_count),
                statuses_count=profile_data.get("statuses_count", profile.statuses_count),
                age=profile_data.get("age", profile.age),
                gender=profile_data.get("gender", profile.gender),
                mbti=profile_data.get("mbti", profile.mbti),
                country=profile_data.get("country", profile.country),
                profession=profile_data.get("profession", profile.profession),
                interested_topics=_normalize_topics(profile_data.get("interested_topics", profile.interested_topics)),
                source_entity_uuid=profile.source_entity_uuid,
                source_entity_type=profile.source_entity_type,
                stance=profile_data.get("stance", profile.stance),
                sentiment_bias=profile_data.get("sentiment_bias", profile.sentiment_bias),
            )

        except Exception as e:
            logger.warning(f"차별화 재생성 실패 ({profile.name}): {e}")
            return None

    # 이전 메서드 이름을 별칭으로 유지, 하위 호환성 보장
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[폐기됨] save_profiles() 메서드를 사용하세요"""
        logger.warning("save_profiles_to_json은 폐기되었습니다. save_profiles 메서드를 사용하세요")
        self.save_profiles(profiles, file_path, platform)

