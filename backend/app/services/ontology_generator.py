"""
온톨로지 생성 서비스
인터페이스1: 텍스트 내용을 분석하여 사회 시뮬레이션에 적합한 엔티티 및 관계 유형 정의 생성
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# 온톨로지 생성 시스템 프롬프트
ONTOLOGY_SYSTEM_PROMPT = """당신은 전문 지식 그래프 온톨로지 설계 전문가입니다. 주어진 텍스트 내용과 시뮬레이션 요구사항을 분석하여, **소셜 미디어 여론 시뮬레이션**에 적합한 엔티티 유형과 관계 유형을 설계하는 것이 당신의 임무입니다.

**중요: 유효한 JSON 형식 데이터만 출력해야 하며, 다른 내용은 출력하지 마세요.**

## 핵심 작업 배경

우리는 **소셜 미디어 여론 시뮬레이션 시스템**을 구축하고 있습니다. 이 시스템에서:
- 각 엔티티는 소셜 미디어에서 발언, 상호작용, 정보 전파가 가능한 "계정" 또는 "주체"
- 엔티티 간에 서로 영향을 주고, 리트윗, 댓글, 응답함
- 여론 이벤트에서 각 측의 반응과 정보 전파 경로를 시뮬레이션해야 함

따라서, **엔티티는 반드시 현실에 실제 존재하며, 소셜 미디어에서 발언하고 상호작용할 수 있는 주체**여야 합니다:

**가능한 것**:
- 구체적인 개인 (공인, 당사자, 오피니언 리더, 전문가, 일반인)
- 기업, 회사 (공식 계정 포함)
- 조직 기관 (대학교, 협회, NGO, 노조 등)
- 정부 부처, 규제 기관
- 미디어 기관 (신문사, 방송국, 1인 미디어, 웹사이트)
- 소셜 미디어 플랫폼 자체
- 특정 그룹 대표 (동문회, 팬클럽, 권익 단체 등)

**불가능한 것**:
- 추상적 개념 (예: "여론", "감정", "트렌드")
- 주제/화제 (예: "학술 청렴", "교육 개혁")
- 관점/태도 (예: "지지측", "반대측")

## 출력 형식

JSON 형식으로 출력하세요. 다음 구조를 포함해야 합니다:

```json
{
    "entity_types": [
        {
            "name": "엔티티 유형명 (영어, PascalCase)",
            "description": "간략 설명 (영어, 100자 이내)",
            "attributes": [
                {
                    "name": "속성명 (영어, snake_case)",
                    "type": "text",
                    "description": "속성 설명"
                }
            ],
            "examples": ["예시 엔티티1", "예시 엔티티2"]
        }
    ],
    "edge_types": [
        {
            "name": "관계 유형명 (영어, UPPER_SNAKE_CASE)",
            "description": "간략 설명 (영어, 100자 이내)",
            "source_targets": [
                {"source": "소스 엔티티 유형", "target": "대상 엔티티 유형"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "텍스트 내용에 대한 간략 분석 설명 (한국어)"
}
```

## 설계 가이드 (매우 중요!)

### 1. 엔티티 유형 설계 - 반드시 엄격히 준수

**수량 요구: 반드시 정확히 10개 엔티티 유형**

**계층 구조 요구 (구체적 유형과 폴백 유형을 반드시 동시에 포함)**:

10개 엔티티 유형은 다음 계층을 포함해야 합니다:

A. **폴백 유형 (반드시 포함, 목록 마지막 2개에 배치)**:
   - `Person`: 모든 자연인 개인의 폴백 유형. 다른 더 구체적인 인물 유형에 속하지 않을 때 이 유형으로 분류.
   - `Organization`: 모든 조직 기관의 폴백 유형. 다른 더 구체적인 조직 유형에 속하지 않을 때 이 유형으로 분류.

B. **구체적 유형 (8개, 텍스트 내용에 따라 설계)**:
   - 텍스트에 등장하는 주요 역할에 대해 더 구체적인 유형 설계
   - 예: 텍스트가 학술 이벤트 관련이면 `Student`, `Professor`, `University` 가능
   - 예: 텍스트가 상업 이벤트 관련이면 `Company`, `CEO`, `Employee` 가능

**폴백 유형이 필요한 이유**:
- 텍스트에는 다양한 인물이 등장함, 예: "초중학교 교사", "행인", "어떤 네티즌"
- 전용 유형이 없으면 `Person`으로 분류되어야 함
- 마찬가지로, 소규모 조직, 임시 단체 등은 `Organization`으로 분류

**구체적 유형의 설계 원칙**:
- 텍스트에서 고빈도 등장 또는 핵심 역할 유형 식별
- 각 구체적 유형은 명확한 경계를 가져야 하며, 중복 방지
- description은 이 유형과 폴백 유형의 차이를 명확히 설명해야 함

### 2. 관계 유형 설계

- 수량: 6-10개
- 관계는 소셜 미디어 상호작용의 실제 연결을 반영해야 함
- 관계의 source_targets가 정의한 엔티티 유형을 포함하도록 보장

### 3. 속성 설계

- 각 엔티티 유형당 1-3개 핵심 속성
- **주의**: 속성명에 `name`, `uuid`, `group_id`, `created_at`, `summary` 사용 불가 (시스템 예약어)
- 권장: `full_name`, `title`, `role`, `position`, `location`, `description` 등

## 엔티티 유형 참고

**개인 (구체적)**:
- Student: 학생
- Professor: 교수/학자
- Journalist: 기자
- Celebrity: 연예인/인플루언서
- Executive: 임원
- Official: 정부 관료
- Lawyer: 변호사
- Doctor: 의사

**개인 (폴백)**:
- Person: 모든 자연인 (위의 구체적 유형에 속하지 않을 때 사용)

**조직 (구체적)**:
- University: 대학교
- Company: 기업
- GovernmentAgency: 정부 기관
- MediaOutlet: 미디어 기관
- Hospital: 병원
- School: 초중학교
- NGO: 비정부 조직

**조직 (폴백)**:
- Organization: 모든 조직 기관 (위의 구체적 유형에 속하지 않을 때 사용)

## 관계 유형 참고

- WORKS_FOR: 근무
- STUDIES_AT: 재학
- AFFILIATED_WITH: 소속
- REPRESENTS: 대표
- REGULATES: 규제
- REPORTS_ON: 보도
- COMMENTS_ON: 댓글
- RESPONDS_TO: 응답
- SUPPORTS: 지지
- OPPOSES: 반대
- COLLABORATES_WITH: 협력
- COMPETES_WITH: 경쟁
"""


class OntologyGenerator:
    """
    온톨로지 생성기
    텍스트 내용을 분석하여 엔티티 및 관계 유형 정의 생성
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        온톨로지 정의 생성

        Args:
            document_texts: 문서 텍스트 목록
            simulation_requirement: 시뮬레이션 요구사항 설명
            additional_context: 추가 컨텍스트

        Returns:
            온톨로지 정의 (entity_types, edge_types 등)
        """
        # 사용자 메시지 구성
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # LLM 호출 (reasoning 모델은 사고 토큰도 포함하므로 충분히 할당)
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=16384
        )
        
        # 검증 및 후처리
        result = self._validate_and_process(result)
        
        return result
    
    # LLM에 전달할 텍스트 최대 길이 (5만자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """사용자 메시지 구성"""

        # 텍스트 합치기
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # 텍스트가 5만자를 초과하면 절단 (LLM에 전달하는 내용에만 영향, 그래프 구축에는 영향 없음)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(원문 총 {original_length}자, 온톨로지 분석용으로 앞 {self.MAX_TEXT_LENGTH_FOR_LLM}자 발췌)..."
        
        message = f"""## 시뮬레이션 요구사항

{simulation_requirement}

## 문서 내용

{combined_text}
"""
        
        if additional_context:
            message += f"""
## 추가 설명

{additional_context}
"""
        
        message += """
위 내용을 기반으로, 사회 여론 시뮬레이션에 적합한 엔티티 유형과 관계 유형을 설계하세요.

**반드시 준수해야 할 규칙**:
1. 반드시 정확히 10개 엔티티 유형을 출력
2. 마지막 2개는 반드시 폴백 유형: Person (개인 폴백)과 Organization (조직 폴백)
3. 앞 8개는 텍스트 내용에 따라 설계된 구체적 유형
4. 모든 엔티티 유형은 현실에서 발언할 수 있는 주체여야 하며, 추상적 개념은 불가
5. 속성명에 name, uuid, group_id 등 예약어 사용 불가, full_name, org_name 등으로 대체
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 검증 및 후처리"""

        # 필수 필드 존재 보장
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # 엔티티 유형 검증
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # description이 100자를 초과하지 않도록 보장
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # 관계 유형 검증
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 제한: 최대 10개 커스텀 엔티티 유형, 최대 10개 커스텀 엣지 유형
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # 폴백 유형 정의
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # 이미 폴백 유형이 있는지 확인
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # 추가해야 할 폴백 유형
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # 추가 후 10개를 초과하면, 기존 유형 일부 제거 필요
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 제거해야 할 수량 계산
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 끝에서부터 제거 (앞쪽의 더 중요한 구체적 유형 유지)
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # 폴백 유형 추가
            result["entity_types"].extend(fallbacks_to_add)
        
        # 최종적으로 제한 초과하지 않도록 보장 (방어적 프로그래밍)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        온톨로지 정의를 Python 코드로 변환 (ontology.py 유사)

        Args:
            ontology: 온톨로지 정의

        Returns:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            '커스텀 엔티티 유형 정의',
            'MiroFish 자동 생성, 사회 여론 시뮬레이션용',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== 엔티티 유형 정의 ==============',
            '',
        ]
        
        # 엔티티 유형 생성
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== 관계 유형 정의 ==============')
        code_lines.append('')
        
        # 관계 유형 생성
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스명으로 변환
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 유형 딕셔너리 생성
        code_lines.append('# ============== 유형 설정 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 엣지의 source_targets 매핑 생성
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

