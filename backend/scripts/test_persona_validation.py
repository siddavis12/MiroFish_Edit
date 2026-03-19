"""
페르소나 검증 Before/After 실제 LLM 테스트
- 기존 프로필의 persona 텍스트로 응답 생성 (Before)
- LLM이 persona 품질을 평가하고 보정
- 보정된 persona로 동일 질문 재응답 (After)
- Before/After 비교 리포트 출력
"""

import json
import os
import sys
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.llm_client import LLMClient
from app.config import Config

# ── 설정 ──────────────────────────────────────────────────

SIM_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations/sim_c9a5143f114b')
PROFILES_PATH = os.path.join(SIM_DIR, 'reddit_profiles.json')
CONFIG_PATH = os.path.join(SIM_DIR, 'simulation_config.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '../outputs')

# 대표 에이전트 인덱스
TARGET_AGENTS = [0, 1, 3, 12]  # SAG-AFTRA, 스튜디오 CEO, 마이크로소프트, 독립 개발자

# 테스트 질문
TEST_QUESTIONS = [
    "게임 산업에서 AI 도입에 대한 당신의 입장은?",
    "NC소프트의 대규모 구조조정에 대해 어떻게 생각하시나요?",
    "인디 개발자가 AI 도구로 1인 개발하는 현상을 어떻게 보시나요?",
]


def load_data():
    """프로필과 시뮬레이션 설정 로드"""
    with open(PROFILES_PATH, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return profiles, config


def get_agent_config(config, agent_id):
    """agent_configs에서 해당 에이전트의 설정 반환"""
    for ac in config['agent_configs']:
        if ac['agent_id'] == agent_id:
            return ac
    return {}


def generate_responses(llm: LLMClient, persona_text: str, agent_name: str, questions: list) -> list:
    """페르소나를 system prompt로 넣고 질문별 개별 응답 (배치 시 누락 방지)"""
    system_msg = f"당신은 '{agent_name}'입니다. 아래는 당신의 페르소나입니다:\n\n{persona_text}\n\n이 페르소나에 완전히 몰입하여 답변하세요. 3-5문장으로 답변하세요."
    answers = []
    for q in questions:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": q}
        ]
        answer = llm.chat(messages, temperature=0.7, max_tokens=512)
        answers.append(answer)
    return answers


def evaluate_personas(llm: LLMClient, agents_info: list, sim_requirement: str) -> list:
    """전체 에이전트의 persona를 배치로 평가"""
    agents_block = ""
    for info in agents_info:
        agents_block += f"""
--- 에이전트: {info['name']} ---
entity_type: {info['entity_type']}
stance: {info['stance']} (sentiment_bias: {info['sentiment_bias']})
influence_weight: {info['influence_weight']}
현재 persona:
{info['persona']}
"""

    messages = [
        {"role": "system", "content": "당신은 시뮬레이션 에이전트 페르소나의 품질을 평가하는 전문가입니다."},
        {"role": "user", "content": f"""아래는 시뮬레이션의 요구사항과 에이전트들의 페르소나입니다.

## 시뮬레이션 요구사항
{sim_requirement}

## 평가 대상 에이전트들
{agents_block}

각 에이전트의 페르소나를 다음 4가지 기준으로 평가하세요:
1. **역할 일관성** (0-25): persona가 해당 엔티티의 실제 역할/입장을 반영하는가
2. **톤 정합성** (0-25): stance(opposing/supportive/neutral)에 맞는 톤을 가지는가. opposing인데 "협상과 합의 우선" 같은 톤이면 감점.
3. **차별화** (0-25): 다른 에이전트와 구별되는 고유한 관점이 있는가
4. **사실 기반** (0-25): seed data의 구체적 사실(SAG-AFTRA 11개월 파업, GDC 설문 52% 부정적, NC소프트 구조조정 등)을 활용하는가

JSON 형식으로 응답:
{{
  "evaluations": [
    {{
      "agent_name": "에이전트명",
      "total_score": 0-100,
      "role_consistency": 0-25,
      "tone_alignment": 0-25,
      "differentiation": 0-25,
      "fact_based": 0-25,
      "problems": ["문제점1", "문제점2"],
      "strengths": ["강점1"]
    }}
  ]
}}"""}
    ]
    result = llm.chat_json(messages, temperature=0.3, max_tokens=4096)
    return result.get("evaluations", [])


def refine_persona(llm: LLMClient, agent_info: dict, evaluation: dict, sim_requirement: str) -> str:
    """검증 결과를 반영하여 persona 보정"""
    messages = [
        {"role": "system", "content": "당신은 시뮬레이션 에이전트 페르소나를 최적화하는 전문가입니다."},
        {"role": "user", "content": f"""아래 에이전트의 페르소나를 보정해주세요.

## 시뮬레이션 요구사항 (핵심 부분)
{sim_requirement[:1500]}

## 에이전트 정보
- 이름: {agent_info['name']}
- entity_type: {agent_info['entity_type']}
- stance: {agent_info['stance']} (sentiment_bias: {agent_info['sentiment_bias']})
- influence_weight: {agent_info['influence_weight']}

## 현재 persona
{agent_info['persona']}

## 평가 결과
- 총점: {evaluation.get('total_score', 0)}/100
- 문제점: {json.dumps(evaluation.get('problems', []), ensure_ascii=False)}

## 보정 지침
1. stance가 opposing이면 비판적/저항적 톤을 명확히 하세요
2. stance가 supportive이면 옹호/추진 톤을 명확히 하세요
3. 시뮬레이션 요구사항의 구체적 사실과 수치를 persona에 녹여넣으세요
4. 다른 에이전트와 차별화되는 고유 관점을 강화하세요
5. 원래 persona의 좋은 부분은 유지하되, 문제점을 개선하세요

보정된 persona 텍스트만 출력하세요. JSON이 아닌 순수 텍스트로 응답하세요."""}
    ]
    return llm.chat(messages, temperature=0.5, max_tokens=2048)


def format_report(results: list) -> str:
    """Before/After 비교 리포트 생성"""
    lines = []
    lines.append("═" * 60)
    lines.append("  페르소나 검증 Before/After 비교 리포트")
    lines.append(f"  생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("═" * 60)
    lines.append("")

    total_before = 0
    total_after = 0

    for r in results:
        before_score = r['evaluation'].get('total_score', 0)
        after_score = r.get('after_score', before_score)
        total_before += before_score
        total_after += after_score

        lines.append(f"┌─ 에이전트: {r['name']} ({r['entity_type']}, stance: {r['stance']})")
        lines.append(f"│  검증 점수: {before_score}/100")
        lines.append(f"│  역할일관성: {r['evaluation'].get('role_consistency', '?')}/25  "
                     f"톤정합성: {r['evaluation'].get('tone_alignment', '?')}/25  "
                     f"차별화: {r['evaluation'].get('differentiation', '?')}/25  "
                     f"사실기반: {r['evaluation'].get('fact_based', '?')}/25")
        if r['evaluation'].get('problems'):
            lines.append(f"│  문제점: {', '.join(r['evaluation']['problems'])}")
        if r['evaluation'].get('strengths'):
            lines.append(f"│  강점: {', '.join(r['evaluation']['strengths'])}")
        lines.append("│")

        for qi, q in enumerate(TEST_QUESTIONS):
            lines.append(f"│  질문 {qi+1}: {q}")
            lines.append("│")

            before_answer = r['before_answers'][qi] if qi < len(r['before_answers']) else "(응답 없음)"
            after_answer = r['after_answers'][qi] if qi < len(r['after_answers']) else "(응답 없음)"

            lines.append("│  ── Before ──")
            for line in before_answer.split('\n'):
                lines.append(f"│  {line}")
            lines.append("│")
            lines.append("│  ── After ──")
            for line in after_answer.split('\n'):
                lines.append(f"│  {line}")
            lines.append("│")

        lines.append("└" + "─" * 59)
        lines.append("")

    # 종합 분석
    n = len(results)
    avg_before = total_before / n if n else 0
    avg_after = total_after / n if n else 0

    lines.append("═" * 60)
    lines.append("  종합 분석")
    lines.append("═" * 60)
    lines.append(f"  평균 검증 점수: Before {avg_before:.0f} → After {avg_after:.0f} ({avg_after - avg_before:+.0f})")
    lines.append("")

    for r in results:
        before_score = r['evaluation'].get('total_score', 0)
        after_score = r.get('after_score', before_score)
        delta = after_score - before_score
        bar_before = "█" * (before_score // 5)
        bar_after = "█" * (after_score // 5)
        lines.append(f"  {r['name'][:15]:15s}  Before [{bar_before:20s}] {before_score}")
        lines.append(f"  {'':15s}  After  [{bar_after:20s}] {after_score} ({delta:+d})")

    lines.append("")
    lines.append("═" * 60)

    return "\n".join(lines)


def main():
    print("페르소나 검증 테스트를 시작합니다...")
    print(f"  모델: {Config.LLM_MODEL_NAME}")
    print(f"  대상 에이전트: {len(TARGET_AGENTS)}명")
    print(f"  테스트 질문: {len(TEST_QUESTIONS)}개")
    print()

    # 데이터 로드
    profiles, config = load_data()
    sim_requirement = config.get('simulation_requirement', '')

    # 대상 에이전트 정보 수집
    agents_info = []
    for idx in TARGET_AGENTS:
        profile = profiles[idx]
        agent_config = get_agent_config(config, idx)
        agents_info.append({
            'index': idx,
            'name': profile['name'],
            'entity_type': profile.get('entity_type', ''),
            'persona': profile['persona'],
            'bio': profile.get('bio', ''),
            'stance': agent_config.get('stance', 'neutral'),
            'sentiment_bias': agent_config.get('sentiment_bias', 0),
            'influence_weight': agent_config.get('influence_weight', 1.0),
        })

    llm = LLMClient()
    results = []

    # ── Step 1: Before 응답 생성 ──
    print("=" * 50)
    print("[Step 1/4] Before 응답 생성 중...")
    print("=" * 50)
    for info in agents_info:
        print(f"  → {info['name']}...", end=" ", flush=True)
        answers = generate_responses(llm, info['persona'], info['name'], TEST_QUESTIONS)
        print(f"완료 ({len(answers)}개 응답)")
        results.append({
            'name': info['name'],
            'entity_type': info['entity_type'],
            'stance': info['stance'],
            'sentiment_bias': info['sentiment_bias'],
            'original_persona': info['persona'],
            'before_answers': answers,
            'evaluation': {},
            'refined_persona': '',
            'after_answers': [],
        })

    # ── Step 2: 페르소나 평가 ──
    print()
    print("=" * 50)
    print("[Step 2/4] 페르소나 품질 평가 중...")
    print("=" * 50)
    evaluations = evaluate_personas(llm, agents_info, sim_requirement)
    for i, ev in enumerate(evaluations):
        if i < len(results):
            results[i]['evaluation'] = ev
            print(f"  → {results[i]['name']}: {ev.get('total_score', '?')}/100")

    # ── Step 3: 페르소나 보정 ──
    print()
    print("=" * 50)
    print("[Step 3/4] 페르소나 보정 중...")
    print("=" * 50)
    for i, info in enumerate(agents_info):
        if i < len(results):
            print(f"  → {info['name']}...", end=" ", flush=True)
            refined = refine_persona(llm, info, results[i]['evaluation'], sim_requirement)
            results[i]['refined_persona'] = refined
            print(f"완료 ({len(refined)}자)")

    # ── Step 4: After 응답 생성 ──
    print()
    print("=" * 50)
    print("[Step 4/4] After 응답 생성 중...")
    print("=" * 50)
    for i, r in enumerate(results):
        print(f"  → {r['name']}...", end=" ", flush=True)
        answers = generate_responses(llm, r['refined_persona'], r['name'], TEST_QUESTIONS)
        r['after_answers'] = answers
        print(f"완료 ({len(answers)}개 응답)")

    # ── After 페르소나 재평가 (점수만) ──
    print()
    print("보정 후 재평가 중...")
    after_agents_info = []
    for i, info in enumerate(agents_info):
        after_info = dict(info)
        after_info['persona'] = results[i]['refined_persona']
        after_agents_info.append(after_info)

    after_evaluations = evaluate_personas(llm, after_agents_info, sim_requirement)
    for i, ev in enumerate(after_evaluations):
        if i < len(results):
            results[i]['after_score'] = ev.get('total_score', 0)
            print(f"  → {results[i]['name']}: {results[i]['evaluation'].get('total_score', 0)} → {ev.get('total_score', 0)}")

    # ── 리포트 생성 ──
    report = format_report(results)
    print()
    print(report)

    # 파일 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 텍스트 리포트 저장
    report_path = os.path.join(OUTPUT_DIR, f'persona_validation_{timestamp}.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n리포트 저장: {report_path}")

    # JSON 상세 데이터 저장
    json_path = os.path.join(OUTPUT_DIR, f'persona_validation_{timestamp}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"상세 데이터 저장: {json_path}")


if __name__ == '__main__':
    main()
