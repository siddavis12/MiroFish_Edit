
## 프로젝트 소개

**MiroFish**는 뉴스, 정책 문서, 금융 보고서, 소설 등 현실 세계의 시드 자료를 입력받아 **수백 개의 독립적 AI 에이전트가 자유롭게 상호작용하는 디지털 세계**를 구축하고, 그 과정에서 발현되는 집단 지능을 통해 미래를 예측하는 엔진이다.

> **입력**: 시드 자료(PDF, 텍스트) + 자연어로 기술한 예측 요구사항
> **출력**: 상세한 예측 보고서 + 심층 인터랙션이 가능한 시뮬레이션 세계

### 활용 사례

- **여론 시뮬레이션** — 정책 발표 전 다양한 이해관계자의 반응 예측
- **시나리오 분석** — "만약 ~한다면?" 질문에 대한 군중 지능 기반 답변
- **트렌드 예측** — 업계 변화, 기술 발전 경로에 대한 다중 관점 수렴 예측
- **내러티브 추론** — 소설, 역사적 사건의 미완결 결말 예측

---

## 작동 원리 — 5단계 파이프라인

```
시드 문서 업로드
       │
       ▼
┌─────────────────┐
│ 1. 그래프 구축   │  온톨로지 자동 생성 → LLM 엔티티/관계 추출 → Neo4j + ChromaDB에 GraphRAG 구축
└───────┬─────────┘
        ▼
┌─────────────────┐
│ 2. 환경 구성     │  엔티티 필터링 → 시뮬레이션 설정 자동 생성 → OASIS 에이전트 프로필 생성
└───────┬─────────┘
        ▼
┌─────────────────┐
│ 3. 시뮬레이션    │  Twitter/Reddit 병렬 시뮬레이션 → 에이전트 토론·충돌·합의 → 실시간 모니터링
└───────┬─────────┘
        ▼
┌─────────────────┐
│ 4. 보고서 생성   │  ReportAgent가 ReACT 패턴으로 시뮬레이션 세계를 탐색하며 예측 보고서 작성
└───────┬─────────┘
        ▼
┌─────────────────┐
│ 5. 심층 인터랙션 │  시뮬레이션 세계의 에이전트와 직접 대화 + ReportAgent에 추가 질의
└─────────────────┘
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **프론트엔드** | Vue 3.5 + Vite 7 + D3.js 7 + Vue Router 4 + Axios |
| **백엔드** | Python 3.11+ / Flask 3 + OpenAI SDK |
| **그래프 DB** | Neo4j 5 (엔티티/관계 저장) |
| **벡터 검색** | ChromaDB (시맨틱 검색, 인프로세스) |
| **시뮬레이션** | CAMEL-OASIS 0.2.5 (소셜 미디어 시뮬레이션 엔진) |
| **LLM** | OpenAI SDK 호환 API (기본: gpt-5-mini) |
| **패키지 관리** | npm (프론트엔드), uv (백엔드) |

---

## 빠른 시작

### 사전 요구사항

| 도구 | 버전 | 확인 명령 |
|------|------|-----------|
| **Node.js** | 18+ | `node -v` |
| **Python** | 3.11 ~ 3.12 | `python --version` |
| **uv** | 최신 | `uv --version` |
| **Neo4j** | 5.x | Docker 또는 로컬 설치 |

### 1단계: Neo4j 실행

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/mirofish \
  neo4j:5-community
```

### 2단계: 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 필수 값을 입력:

```env
# LLM API (OpenAI SDK 호환이면 모두 사용 가능)
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=gpt-5-mini

# Neo4j (기본값이 있으므로 로컬 Docker 사용 시 수정 불필요)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish
```

### 3단계: 의존성 설치

```bash
# 전체 설치 (루트 + 프론트엔드 + 백엔드)
npm run setup:all
```

또는 분리 설치:

```bash
npm run setup          # Node.js 의존성 (루트 + 프론트엔드)
npm run setup:backend  # Python 의존성 (자동 가상환경 생성)
```

### 4단계: 개발 서버 실행

```bash
# 프론트엔드 + 백엔드 동시 실행
npm run dev
```

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:3000 |
| 백엔드 API | http://localhost:5001 |
| Neo4j Browser | http://localhost:7474 |

개별 실행:

```bash
npm run frontend   # 프론트엔드만
npm run backend    # 백엔드만
```

### Docker 배포

```bash
cp .env.example .env
# .env 파일 편집 후:
docker compose up -d
```

### Windows 원클릭 실행

```powershell
.\start.ps1
```

---

## 프로젝트 구조

```
MiroFish/
├── frontend/src/
│   ├── components/          # Vue 컴포넌트
│   │   ├── Step1GraphBuild  #   그래프 구축 UI
│   │   ├── Step2EnvSetup    #   환경 구성 UI
│   │   ├── Step3Simulation  #   시뮬레이션 실행 UI
│   │   ├── Step4Report      #   보고서 생성 UI
│   │   ├── Step5Interaction #   심층 인터랙션 UI
│   │   ├── GraphPanel       #   D3.js 그래프 시각화
│   │   └── HistoryDatabase  #   프로젝트 히스토리
│   ├── views/               # 페이지 라우트
│   ├── api/                 # API 호출 모듈
│   ├── store/               # 상태 관리
│   └── router/              # Vue Router 설정
│
├── backend/app/
│   ├── api/                 # Flask API 엔드포인트
│   │   ├── graph.py         #   그래프 구축/조회 API
│   │   ├── simulation.py    #   시뮬레이션 관리 API
│   │   └── report.py        #   보고서 생성/조회 API
│   ├── services/            # 비즈니스 로직
│   │   ├── graph_store.py           # 그래프 저장소 추상 인터페이스
│   │   ├── neo4j_store.py           # Neo4j 구현
│   │   ├── chroma_store.py          # ChromaDB 벡터 검색
│   │   ├── llm_extractor.py         # LLM 엔티티/관계 추출
│   │   ├── ontology_generator.py    # 온톨로지 자동 생성
│   │   ├── graph_builder.py         # 그래프 구축 오케스트레이터
│   │   ├── entity_reader.py         # 엔티티 읽기/필터링
│   │   ├── simulation_config_generator.py  # 시뮬레이션 설정 자동 생성
│   │   ├── oasis_profile_generator.py      # OASIS 에이전트 프로필 생성
│   │   ├── simulation_runner.py     # 시뮬레이션 실행/모니터링
│   │   ├── simulation_manager.py    # 시뮬레이션 생명주기 관리
│   │   ├── simulation_ipc.py        # 프로세스 간 통신
│   │   ├── report_agent.py          # ReACT 기반 보고서 생성
│   │   ├── graph_tools.py           # 검색/분석 도구 (InsightForge, Panorama, Interview)
│   │   ├── graph_memory_updater.py  # 시뮬레이션 중 그래프 동적 업데이트
│   │   └── text_processor.py        # 텍스트 전처리
│   ├── models/              # Pydantic 데이터 모델
│   ├── utils/               # 유틸리티 (LLM 클라이언트, 파일 파서, 로거, 재시도)
│   └── config.py            # 환경 변수 설정
│
├── static/                  # 정적 리소스
├── .env.example             # 환경 변수 템플릿
├── docker-compose.yml       # Docker 배포 설정
├── package.json             # 루트 스크립트 (dev, setup 등)
└── start.ps1                # Windows 원클릭 실행 스크립트
```

---

## 환경 변수 참조

| 변수 | 필수 | 기본값 | 설명 |
|------|:----:|--------|------|
| `LLM_API_KEY` | O | — | OpenAI SDK 호환 API 키 |
| `LLM_MODEL_NAME` | O | `gpt-5-mini` | 사용할 LLM 모델명 |
| `LLM_BASE_URL` | | — | 커스텀 API 엔드포인트 (OpenAI 이외) |
| `NEO4J_URI` | | `bolt://localhost:7687` | Neo4j 접속 URI |
| `NEO4J_USER` | | `neo4j` | Neo4j 사용자명 |
| `NEO4J_PASSWORD` | | `mirofish` | Neo4j 비밀번호 |
| `LLM_BOOST_API_KEY` | | — | 병렬 시뮬레이션용 두 번째 LLM API 키 |
| `LLM_BOOST_MODEL_NAME` | | — | 병렬 시뮬레이션용 두 번째 모델명 |
| `CHROMA_PERSIST_DIR` | | `./chroma_data` | ChromaDB 영속 저장 경로 |

---

## 주의사항

- **토큰 소모**: 시뮬레이션은 다량의 LLM 호출을 수반한다. 테스트 시 **40라운드 이하**를 권장한다.
- **그래프 구축**: LLM 추출을 사용하므로 시드 문서 크기에 비례하여 토큰 소모가 증가한다.
- **ChromaDB**: 인프로세스로 실행되므로 별도 서버 설치가 불필요하다. 데이터는 `backend/chroma_data/`에 영속 저장된다.
- **Boost LLM**: 병렬 시뮬레이션(Twitter + Reddit 동시)에서 두 번째 API를 사용하면 동시성이 향상된다. 미설정 시 기본 LLM으로 폴백한다.

---

## 감사의 말

MiroFish의 시뮬레이션 엔진은 **[OASIS](https://github.com/camel-ai/oasis)** (CAMEL-AI)를 기반으로 한다.

원본 프로젝트: **[MiroFish](https://github.com/666ghj/MiroFish)** by 666ghj

---

## 라이선스

[AGPL-3.0](LICENSE)
