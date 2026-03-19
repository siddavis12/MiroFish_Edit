# Simulation Brief: AI 시대 게임 개발자 업무 방식 및 회사-구성원 관계 변화

## 사용법
MiroFish Step1 "시뮬레이션 요구사항" 입력란에 아래 영어 텍스트를 복사하여 붙여넣으세요.

## Simulation Requirement (영어 — 이 부분을 복사)

Simulate the transformation of game development workflows and studio-employee relations driven by AI adoption over a 5-year horizon (2024–2029), focusing on the global and Korean gaming industry.

Key questions:
- How do game studio executives and field developers diverge in their framing of AI—executives as "efficiency revolution" vs. developers as "displacement threat"—and does this gap widen or narrow over time?
- What happens to mid-career developers (concept artists, game designers, narrative writers) as AI tools automate 30–50% of their tasks, while senior developers become "AI-augmented super-producers"?
- How do indie developers leverage AI tools (Cursor, Ludo.ai, Tripo3D) to achieve team-level output as solo creators, and does this reshape industry power dynamics?

Expected actor types: Game company executives (Andrew Wilson/EA, Yves Guillemot/Ubisoft, Chang Byung-gyu/Crafton, Park Byung-moo/NC Soft), field game developers and artists (concept artists, programmers, game designers facing layoffs), major game studios (EA, Ubisoft, Unity, NC Soft, Crafton, Nexon, Kakao Games), indie developers (Tristan Bouchier, Cakez, FireBrick Games), labor unions and advocacy groups (SAG-AFTRA led by Duncan Crabtree-Ireland), industry analysts and game media (GDC surveys, Quantic Foundry, Nintendo Life), government and policy agencies (KOCCA, Korean Ministry of Culture), and gaming/AI tool platforms (Steam, Google Cloud, Ludo.ai).

Interaction dynamics: Observe the escalating tension between executive "productivity" narratives and developer resistance—GDC surveys show negativity rising from 18% (2024) to 52% (2026). Track how Korean studios (Crafton: concept art 16hrs→1hr, NC Soft: company-wide AI TF) frame AI as "efficiency" while simultaneously executing mass layoffs (NC Soft restructuring, Joycity 30% cuts, Clover Games post-launch dismissals). Monitor SAG-AFTRA's 11-month strike (2024.07–2025.06) as a model for organized labor response. Watch indie developers navigate the ethical duality—AI enables solo creation but community backlash grows (62.7% of 1.75M gamers "very negative" on AI in games, Steam's 7,000 "gameslop" titles).

Scenarios: (1) Polarization deepens: Executives double down on AI cost-cutting, developer unions expand globally, and a clear labor-vs-management divide emerges resembling the Hollywood strikes. (2) Pragmatic convergence: Industry develops ethical AI frameworks, studios adopt "AI-assisted but human-directed" models, and mid-career developers reskill into AI pipeline managers. (3) Indie disruption: AI-equipped solo developers and small teams erode AAA studio market share, forcing studios to compete on creative vision rather than production scale.

IMPORTANT: All simulation outputs—including agent posts, comments, report analysis, and interaction summaries—must be written in Korean (한국어).

---

## 한국어 해설

| 섹션 | 설명 |
|------|------|
| **Topic & Context** | 2024~2029년 5년간 AI가 게임 개발 워크플로우와 회사-직원 관계를 어떻게 변화시키는지 시뮬레이션 |
| **Key Questions** | (1) 경영진 vs 개발자 간 AI 인식 격차 변화 (2) 중견 개발자(컨셉 아티스트, 게임 디자이너, 내러티브 작가)의 운명 (3) 인디 개발자의 AI 활용과 업계 역학 변화 |
| **Expected Actor Types** | 시드 문서에 등장하는 실제 인물/기관을 구체적으로 명시하여 온톨로지 품질 향상 |
| **Interaction Dynamics** | GDC 설문 데이터(18%→52%), Crafton 16시간→1시간 수치, SAG-AFTRA 11개월 파업, Steam 7,000 AI 게임 등 구체적 근거 포함 |
| **Scenarios** | 극화 심화 / 실용적 수렴 / 인디 파괴적 혁신 — 3가지 전개 방향 |
| **Output Language** | 시뮬레이션의 모든 결과물(에이전트 게시글, 댓글, 리포트 분석, 상호작용 요약)을 한국어로 출력하도록 지시 |

## 예상 온톨로지

```
엔티티 타입 (10개):
  1. GameExecutive — 게임 회사 경영진/의사결정자
     (예: Andrew Wilson, Yves Guillemot, 장병규, 박병무)
  2. GameDeveloper — 게임 개발자/아티스트 (현업 종사자)
     (예: 컨셉 아티스트, 프로그래머, 게임 디자이너, 내러티브 작가)
  3. GameStudio — 대형 게임 개발사/퍼블리셔
     (예: EA, Ubisoft, Unity, NC Soft, Crafton, Nexon, Kakao Games)
  4. IndieDeveloper — 인디/소규모 게임 개발자
     (예: Tristan Bouchier, Cakez, FireBrick Games)
  5. LaborUnion — 게임 업계 노동조합/노동권 단체
     (예: SAG-AFTRA, 게임 개발자 커뮤니티)
  6. IndustryAnalyst — 업계 분석기관/게임 미디어
     (예: GDC, Quantic Foundry, Nintendo Life, 게임 저널리스트)
  7. GovernmentAgency — 정부/정책 기관
     (예: KOCCA, 한국 문화체육관광부)
  8. GamingPlatform — 게임 유통 플랫폼/AI 도구 플랫폼
     (예: Steam, Google Cloud, Ludo.ai, Cursor)
  9. Person — 개인 폴백 (일반 게이머, 익명 네티즌)
 10. Organization — 조직 폴백 (소규모 단체, 임시 그룹)

관계 타입 (8개):
  1. EMPLOYS — 고용 관계 (GameStudio → GameDeveloper)
  2. LEADS — 경영 지휘 (GameExecutive → GameStudio)
  3. LAYS_OFF — 구조조정/해고 (GameStudio → GameDeveloper)
  4. OPPOSES — 반대/저항 (LaborUnion → GameStudio, GameDeveloper → GameExecutive)
  5. ADVOCATES_FOR — 권익 옹호 (LaborUnion → GameDeveloper)
  6. REGULATES — 정책/규제 (GovernmentAgency → GameStudio)
  7. PUBLISHES_ON — 작품 출시 (IndieDeveloper → GamingPlatform)
  8. REPORTS_ON — 보도/분석 (IndustryAnalyst → GameStudio)
```
