"""
설정 관리
프로젝트 루트의 .env 파일에서 통합 로드
"""

import os
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드
# 경로: MiroFish/.env (backend/app/config.py 기준 상대 경로)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 루트에 .env가 없으면 환경변수에서 로드 (프로덕션 환경)
    load_dotenv(override=True)


class Config:
    """Flask 설정 클래스"""

    # Flask 설정
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON 설정 - ASCII 이스케이프 비활성화, 한글/중국어 직접 표시
    JSON_AS_ASCII = False

    # LLM 설정 (OpenAI API)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-5-mini')

    # Boost LLM 설정 (선택 — 병렬 시뮬레이션 시 두 번째 API로 동시성 향상)
    LLM_BOOST_API_KEY = os.environ.get('LLM_BOOST_API_KEY', '')
    LLM_BOOST_MODEL_NAME = os.environ.get('LLM_BOOST_MODEL_NAME', '')

    # Neo4j 설정
    NEO4J_HOST = os.environ.get('NEO4J_HOST', 'localhost')
    NEO4J_BOLT_PORT = int(os.environ.get('NEO4J_BOLT_PORT', '7687'))
    NEO4J_HTTP_PORT = int(os.environ.get('NEO4J_HTTP_PORT', '7474'))
    # NEO4J_URI: 직접 지정하거나, HOST+BOLT_PORT로 자동 생성
    NEO4J_URI = os.environ.get('NEO4J_URI', f'bolt://{NEO4J_HOST}:{NEO4J_BOLT_PORT}')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'mirofish')

    # ChromaDB 설정
    CHROMA_PERSIST_DIR = os.environ.get(
        'CHROMA_PERSIST_DIR',
        os.path.join(os.path.dirname(__file__), '../chroma_data')
    )

    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # 텍스트 처리 설정
    DEFAULT_CHUNK_SIZE = 500  # 기본 청크 크기
    DEFAULT_CHUNK_OVERLAP = 50  # 기본 오버랩 크기

    # OASIS 시뮬레이션 설정
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS 플랫폼 가용 액션 설정
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent 설정
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """필수 설정 검증"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 미설정")
        return errors
