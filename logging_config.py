# logging_config.py

import logging
import sys
import uuid
from pythonjsonlogger import jsonlogger
from config import ENV, LOG_LEVEL, IS_PRODUCTION


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """커스텀 JSON 포맷터 (request_id, user_id 등 추가 가능)"""

    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # 기본 필드
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # 환경 정보
        log_record['environment'] = ENV

        # 프로세스 정보
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread


class ContextLoggerAdapter(logging.LoggerAdapter):
    """컨텍스트 정보 추가 (request_id, user_id 등)"""

    def process(self, msg, kwargs):
        # extra 필드 병합
        if 'extra' not in kwargs:
            kwargs['extra'] = {}

        # adapter의 extra와 호출 시 extra 병합
        kwargs['extra'].update(self.extra)

        return msg, kwargs


def setup_logging():
    """로깅 설정 초기화"""

    # 루트 로거
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)

    if IS_PRODUCTION:
        # ✅ 프로덕션: JSON 포맷
        json_formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(logger)s %(message)s'
        )
        console_handler.setFormatter(json_formatter)
    else:
        # ✅ 개발: 사람이 읽기 쉬운 포맷
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # ✅ httpcore, hpack DEBUG 로그 끄기
    if IS_PRODUCTION:
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("hpack").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("h11").setLevel(logging.WARNING)
    else:
        # 개발 모드에서는 INFO로
        logging.getLogger("httpcore").setLevel(logging.INFO)
        logging.getLogger("hpack").setLevel(logging.INFO)

    logging.info(
        f"✅ 로깅 설정 완료 (환경: {ENV}, 레벨: {LOG_LEVEL}, 포맷: {'JSON' if IS_PRODUCTION else 'TEXT'})"
    )


def get_logger(name: str, **context):
    """
    컨텍스트 정보가 포함된 로거 반환

    Args:
        name: 로거 이름 (보통 __name__)
        **context: 추가 컨텍스트 (user_id, request_id 등)

    Returns:
        ContextLoggerAdapter: 컨텍스트가 포함된 로거

    Example:
        logger = get_logger(__name__, user_id="user123", request_id="abc-456")
        logger.info("사용자 요청 처리 시작")
        # → {"user_id": "user123", "request_id": "abc-456", "message": "사용자 요청 처리 시작", ...}
    """
    logger = logging.getLogger(name)
    return ContextLoggerAdapter(logger, context)


def generate_request_id() -> str:
    """요청 ID 생성 (UUID4 기반)"""
    return str(uuid.uuid4())
