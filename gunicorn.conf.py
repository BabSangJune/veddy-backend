import multiprocessing
import os

# 서버 바인딩
bind = "0.0.0.0:8000"

# ==========================================
# 워커 설정 (메모리 제약 고려)
# ==========================================
# Azure Container: 1 Core, 2GB RAM
# BGE-m3-ko 모델 메모리: ~800MB per worker
# 안전한 워커 수: 1~2개

# 환경변수로 명시적 지정 (권장)
workers = int(os.getenv("GUNICORN_WORKERS", 2))

# ⚠️ CPU 기반 자동 계산 사용 시 메모리 초과 위험
# workers = multiprocessing.cpu_count() * 2 + 1  # 사용 금지

worker_class = "uvicorn.workers.UvicornWorker"

# 연결 설정
worker_connections = 1000
keepalive = 5

# 타임아웃 (SSE 스트리밍 고려)
timeout = 120
graceful_timeout = 30

# 로깅
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ==========================================
# 재시작 설정 (메모리 누수 방지)
# ==========================================
# 1000번 요청 후 워커 재시작 (메모리 누수 대비)
max_requests = 1000
max_requests_jitter = 50

# 프로세스 네이밍
proc_name = "veddy-backend"

# ==========================================
# 워커 프리로드 (메모리 최적화)
# ==========================================
# True: 마스터 프로세스가 모델 로드 후 fork (메모리 공유)
# False: 각 워커가 독립적으로 모델 로드 (메모리 많이 사용)
preload_app = True  # ✅ 메모리 절약

# 시작 시 로그
def on_starting(server):
    import psutil
    mem_info = psutil.virtual_memory() if 'psutil' in dir() else None

    print("=" * 50)
    print("🚀 VEDDY Gunicorn 서버 시작!")
    print(f"워커 수: {workers}")
    print(f"환경: {os.getenv('ENV', 'unknown')}")
    if mem_info:
        print(f"사용 가능 메모리: {mem_info.available / (1024**3):.2f}GB")
    print("=" * 50)

def on_reload(server):
    print("🔄 서버 재시작 중...")

def worker_int(worker):
    """워커 종료 시 로그"""
    print(f"⚠️  워커 {worker.pid} 종료됨")

def worker_abort(worker):
    """워커 비정상 종료 시 로그"""
    print(f"🚨 워커 {worker.pid} 비정상 종료!")
