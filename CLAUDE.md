# MiroFish

다중 에이전트 기반 군중 지능 예측 엔진 — 현실 세계의 시드 정보로 디지털 시뮬레이션 세계를 구축하여 미래를 예측

## 기술 스택

- **프론트엔드**: Vue 3.5 + Vite 7 + D3.js 7 + Vue Router 4 + Axios
- **백엔드**: Python 3.11+ / Flask 3 + OpenAI SDK + Neo4j 5 + ChromaDB + CAMEL-OASIS 0.2.5
- **패키지 관리**: npm (프론트엔드), uv (백엔드)
- **빌드 도구**: Vite (프론트엔드), Hatchling (백엔드)

## 주요 명령어

```bash
# 전체 설치
npm run setup:all

# 개발 서버 (프론트+백엔드 동시)
npm run dev

# 개별 실행
npm run frontend     # 프론트엔드만 (localhost:3000)
npm run backend      # 백엔드만 (localhost:5001)

# 프론트엔드 빌드
npm run build

# Neo4j 로컬 실행 (Docker 단독)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/mirofish neo4j:5-community

# Docker 배포
docker compose up -d
```

## 디렉토리 구조

- `frontend/src/` - Vue 3 프론트엔드 소스
  - `components/` - Vue 컴포넌트 (7개: Step1~5, GraphPanel, HistoryDatabase)
  - `views/` - 페이지 뷰 (7개: Home, MainView, Process, SimulationView, SimulationRunView, ReportView, InteractionView)
  - `api/` - API 호출 모듈 (index, graph, simulation, report)
  - `store/` - 상태 관리 (pendingUpload)
  - `router/` - 라우팅 설정
- `backend/app/` - Flask 백엔드 소스
  - `api/` - API 엔드포인트 (graph, simulation, report)
  - `models/` - 데이터 모델 (project, task)
  - `services/` - 비즈니스 로직 (19개 서비스 파일)
    - **그래프 저장소 계층**: `graph_store.py` (추상 인터페이스), `neo4j_store.py` (Neo4j 구현), `chroma_store.py` (ChromaDB 벡터 검색)
    - **LLM/추출**: `llm_extractor.py` (엔티티/관계 추출), `ontology_generator.py` (온톨로지 생성)
    - **그래프 구축**: `graph_builder.py` (그래프 구축), `entity_reader.py` (엔티티 읽기/필터링)
    - **시뮬레이션**: `simulation_config_generator.py`, `oasis_profile_generator.py`, `simulation_runner.py`, `simulation_manager.py`, `simulation_ipc.py`
    - **리포트/도구**: `report_agent.py` (ReACT 패턴), `graph_tools.py` (검색/분석 도구), `graph_memory_updater.py` (시뮬레이션 메모리 업데이트)
    - **유틸리티**: `text_processor.py`
  - `utils/` - 유틸리티 (file_parser, llm_client, logger, retry)
  - `config.py` - 설정
- `DOC/` - 리서치 자료 및 프롬프트 (git 미추적)
- `old_backend/` - 이전 Zep 기반 백엔드 (마이그레이션 참조용, git 미추적)
- `static/` - 정적 리소스 (이미지 등)

## 코딩 컨벤션

- 주석 언어: 한국어
- 프론트엔드: ESM (`"type": "module"`), JavaScript, 세미콜론 없음, 쌍따옴표
- 백엔드: Python 3.11+, Pydantic 모델 사용, 들여쓰기 4칸
- API 프록시: Vite에서 `/api` → `localhost:5001`로 프록시

## 워크플로우 (5단계 파이프라인)

1. **그래프 구축** (Step1): 시드 문서 업로드 → 온톨로지 생성 → GraphRAG 구축 (Neo4j + ChromaDB)
2. **환경 구성** (Step2): 엔티티 필터링 → 시뮬레이션 설정 생성 → OASIS 에이전트 프로필 생성
3. **시뮬레이션** (Step3): OASIS 엔진으로 Twitter/Reddit 병렬 시뮬레이션 실행 + 실시간 모니터링
4. **리포트 생성** (Step4): ReportAgent가 ReACT 패턴으로 도구(InsightForge, Panorama, Interview) 활용하여 보고서 생성
5. **심층 인터랙션** (Step5): 시뮬레이션 세계의 에이전트와 대화, ReportAgent와 추가 질의

## 프로젝트 특이사항

- `.env` 파일에 `LLM_API_KEY`, `LLM_MODEL_NAME` 필수
- Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 설정 필요 (기본값: bolt://localhost:7687, neo4j, mirofish)
- ChromaDB: 인프로세스 실행 (별도 서버 불필요), `backend/chroma_data/`에 영속 저장
- OASIS 시뮬레이션 엔진 기반 — `camel-oasis==0.2.5` 패키지 의존
- LLM API는 OpenAI SDK 호환 API 사용 (기본: gpt-5-mini)
- Boost LLM: 병렬 시뮬레이션 시 두 번째 API 서비스로 동시성 향상 (선택)
- 시뮬레이션은 토큰 소모가 크므로 40라운드 이하로 테스트 권장
- 그래프 구축 시 LLM 추출을 사용하므로 토큰 소모 증가 가능
- Zep Cloud → Neo4j + ChromaDB 마이그레이션 완료 (2026-03)
