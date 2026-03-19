"""
페르소나 스팟 테스트 검증기
생성된 페르소나를 샘플링하여 품질 검증하고, 실패한 프로필을 보정
"""

import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .oasis_profile_generator import OasisAgentProfile, _normalize_topics

logger = get_logger('mirofish.persona_validator')


@dataclass
class ValidationResult:
    """검증 결과"""
    total_validated: int = 0
    passed_count: int = 0
    failed_count: int = 0
    failed_indices: List[int] = field(default_factory=list)
    scores: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    average_score: float = 0.0


class PersonaValidator:
    """생성된 페르소나를 스팟 테스트하여 품질 검증"""

    # 배치당 검증할 프로필 수
    VALIDATION_BATCH_SIZE = 5

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.model_name = model_name or Config.LLM_MODEL_NAME
        self.llm = LLMClient(api_key=api_key, model=model_name)

    def validate_batch(
        self,
        profiles: List[OasisAgentProfile],
        simulation_requirement: str,
        sample_size: int = 5,
        score_threshold: int = 60,
    ) -> ValidationResult:
        """
        샘플링 검증 → 낮은 점수 프로필 식별

        Args:
            profiles: 전체 프로필 목록
            simulation_requirement: 시뮬레이션 요구사항
            sample_size: 검증할 샘플 수
            score_threshold: 합격 기준 점수 (100점 만점)

        Returns:
            ValidationResult
        """
        if not profiles:
            return ValidationResult()

        # 샘플 선택 (전체보다 적으면 전체 검증)
        total = len(profiles)
        sample_size = min(sample_size, total)
        sample_indices = random.sample(range(total), sample_size)
        sampled_profiles = [(idx, profiles[idx]) for idx in sample_indices]

        result = ValidationResult(total_validated=sample_size)

        # 배치별 병렬 검증 (홀수 배치는 Boost LLM 사용)
        batches = []
        for batch_start in range(0, len(sampled_profiles), self.VALIDATION_BATCH_SIZE):
            batches.append(sampled_profiles[batch_start:batch_start + self.VALIDATION_BATCH_SIZE])

        max_workers = min(len(batches), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    self._validate_batch_llm, batch, simulation_requirement,
                    use_boost=(batch_idx % 2 == 1)
                ): batch_idx
                for batch_idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                try:
                    batch_scores = future.result(timeout=180)
                except Exception as e:
                    logger.warning(f"검증 배치 실패: {e}")
                    continue

                for idx, score_data in batch_scores.items():
                    total_score = score_data.get("total_score", 0)
                    result.scores[idx] = score_data

                    if total_score >= score_threshold:
                        result.passed_count += 1
                    else:
                        result.failed_count += 1
                        result.failed_indices.append(idx)

        # 평균 점수 계산
        if result.scores:
            result.average_score = sum(
                s.get("total_score", 0) for s in result.scores.values()
            ) / len(result.scores)

        logger.info(
            f"페르소나 검증 완료: {result.total_validated}개 검증, "
            f"합격 {result.passed_count}, 불합격 {result.failed_count}, "
            f"평균 점수 {result.average_score:.1f}"
        )

        return result

    def _validate_batch_llm(
        self,
        batch: List[tuple],
        simulation_requirement: str,
        use_boost: bool = False,
    ) -> Dict[int, Dict[str, Any]]:
        """LLM으로 배치 검증 (use_boost=True이면 Boost LLM 사용)"""

        # 검증 대상 프로필 정보 구성
        profiles_text = []
        for idx, profile in batch:
            profiles_text.append(
                f"[에이전트 {idx}]\n"
                f"이름: {profile.name}\n"
                f"엔티티 유형: {profile.source_entity_type}\n"
                f"stance: {profile.stance}\n"
                f"sentiment_bias: {profile.sentiment_bias}\n"
                f"persona:\n{profile.persona[:800]}\n"
            )

        prompt = f"""다음 시뮬레이션 에이전트들의 페르소나 품질을 평가하세요.

시뮬레이션 요구사항: {simulation_requirement}

{chr(10).join(profiles_text)}

각 에이전트에 대해 다음 기준으로 평가하세요:
1. stance_consistency (0-40): persona 텍스트의 톤이 stance/sentiment_bias와 일치하는가
2. role_consistency (0-30): entity_type에 적합한 행동 패턴인가
3. specificity (0-30): 일반적 표현이 아닌 구체적 사실/경험 포함 여부

JSON 형식으로 반환 (마크다운 사용 금지):
{{
    "evaluations": [
        {{
            "agent_index": <인덱스>,
            "stance_consistency": <0-40>,
            "role_consistency": <0-30>,
            "specificity": <0-30>,
            "total_score": <합계>,
            "feedback": "<간략한 피드백>"
        }},
        ...
    ]
}}"""

        system_prompt = "당신은 AI 에이전트 페르소나 품질 평가 전문가입니다. 순수 JSON으로 반환하세요."

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            llm_client = LLMClient(use_boost=True) if use_boost else self.llm
            content, _ = llm_client.chat_with_retry(
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(content)
            evaluations = result.get("evaluations", [])

            scores = {}
            for eval_data in evaluations:
                agent_idx = eval_data.get("agent_index")
                if agent_idx is not None:
                    scores[agent_idx] = {
                        "stance_consistency": eval_data.get("stance_consistency", 0),
                        "role_consistency": eval_data.get("role_consistency", 0),
                        "specificity": eval_data.get("specificity", 0),
                        "total_score": eval_data.get("total_score", 0),
                        "feedback": eval_data.get("feedback", ""),
                    }

            return scores

        except Exception as e:
            logger.warning(f"검증 LLM 호출 실패: {e}")
            # 실패 시 모든 프로필에 기본 점수 부여 (통과)
            return {idx: {"total_score": 70, "feedback": "검증 실패, 기본 점수 부여"} for idx, _ in batch}

    def refine_failed_profiles(
        self,
        profiles: List[OasisAgentProfile],
        failed_indices: List[int],
        validation_results: Dict[int, Dict[str, Any]],
        simulation_requirement: str,
    ) -> List[OasisAgentProfile]:
        """
        검증 실패 프로필 보정

        Args:
            profiles: 전체 프로필 목록
            failed_indices: 실패한 프로필 인덱스 목록
            validation_results: 검증 점수/피드백
            simulation_requirement: 시뮬레이션 요구사항

        Returns:
            보정된 프로필 목록
        """
        # 실패 프로필 병렬 보정 (홀수 인덱스는 Boost LLM 사용)
        valid_items = [
            (i, idx) for i, idx in enumerate(failed_indices) if idx < len(profiles)
        ]

        if not valid_items:
            return profiles

        max_workers = min(len(valid_items), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for i, idx in valid_items:
                profile = profiles[idx]
                feedback = validation_results.get(idx, {}).get("feedback", "")
                use_boost = (i % 2 == 1)

                future = pool.submit(
                    self._refine_single_profile,
                    profile=profile,
                    feedback=feedback,
                    simulation_requirement=simulation_requirement,
                    use_boost=use_boost,
                )
                futures[future] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    new_profile = future.result(timeout=180)
                    if new_profile:
                        profiles[idx] = new_profile
                        logger.info(f"프로필 보정 완료: {profiles[idx].name} (인덱스 {idx})")
                except Exception as e:
                    logger.warning(f"프로필 보정 실패 (인덱스 {idx}): {e}")

        return profiles

    def _refine_single_profile(
        self,
        profile: OasisAgentProfile,
        feedback: str,
        simulation_requirement: str,
        use_boost: bool = False,
    ) -> Optional[OasisAgentProfile]:
        """단일 프로필 보정 (use_boost=True이면 Boost LLM 사용)"""

        prompt = f"""다음 페르소나의 품질을 개선하세요.

시뮬레이션 요구사항: {simulation_requirement}

현재 페르소나:
이름: {profile.name}
엔티티 유형: {profile.source_entity_type}
stance: {profile.stance}
sentiment_bias: {profile.sentiment_bias}
persona: {profile.persona[:1000]}

평가 피드백: {feedback}

개선 지시:
1. stance와 persona 텍스트의 톤이 일관성을 갖도록 수정
2. entity_type에 적합한 구체적 경험/사실 추가
3. 기존 persona의 핵심 정보는 유지하되 품질 개선

개선된 프로필을 JSON으로 반환:
{{
    "persona": "<개선된 페르소나 텍스트 2000자>",
    "bio": "<개선된 소개 200자>",
    "stance": "<supportive/opposing/neutral/observer>",
    "sentiment_bias": <-1.0~1.0>
}}"""

        system_prompt = "당신은 페르소나 품질 개선 전문가입니다. persona 텍스트와 stance/sentiment_bias의 정합성에 집중하세요. 순수 JSON으로 반환하세요. 한국어를 사용하세요."

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            llm_client = LLMClient(use_boost=True) if use_boost else self.llm
            content, _ = llm_client.chat_with_retry(
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            data = json.loads(content)

            # 기존 프로필 복제 후 개선된 필드만 업데이트
            return OasisAgentProfile(
                user_id=profile.user_id,
                user_name=profile.user_name,
                name=profile.name,
                bio=data.get("bio", profile.bio),
                persona=data.get("persona", profile.persona),
                karma=profile.karma,
                friend_count=profile.friend_count,
                follower_count=profile.follower_count,
                statuses_count=profile.statuses_count,
                age=profile.age,
                gender=profile.gender,
                mbti=profile.mbti,
                country=profile.country,
                profession=profile.profession,
                interested_topics=profile.interested_topics,
                source_entity_uuid=profile.source_entity_uuid,
                source_entity_type=profile.source_entity_type,
                stance=data.get("stance", profile.stance),
                sentiment_bias=data.get("sentiment_bias", profile.sentiment_bias),
            )

        except Exception as e:
            logger.warning(f"프로필 보정 실패 ({profile.name}): {e}")
            return None
