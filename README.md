# veddy-backend
pip freeze > requirements.txt
pip install -r requirements.txt

python3 -m venv ~/.virtualenvs/veddy-backend
source /home/june/.virtualenvs/veddy-backend/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
ngrok http 8000


az containerapp update \
--name ca-veddy-backend \
--resource-group VESSELLINK_BOT_RESOURCE \
--min-replicas 1 \
--max-replicas 3

az containerapp logs show \
--name ca-veddy-backend \
--resource-group VESSELLINK_BOT_RESOURCE \
--follow

# 기존 이미지 삭제
docker rmi veddy-backend:latest

# .dockerignore 확인
cat .dockerignore

# 캐시 없이 재빌드
docker build --no-cache -t veddy-backend:latest .

# 크기 확인
docker images veddy-backend:latest

# Registry의 이미지 확인
az acr repository show-tags --name acrveddyprod --repository veddy-backend

# 1. ACR 로그인
az acr login --name acrveddyprod

# 2. 태그
docker tag veddy-backend:latest acrveddyprod.azurecr.io/veddy-backend:latest

# 3. 푸시 (5-10분 소요)
docker push acrveddyprod.azurecr.io/veddy-backend:latest

# 업데이트 실행
az containerapp update \
--name ca-veddy-backend \
--resource-group VESSELLINK_BOT_RESOURCE \
--image acrveddyprod.azurecr.io/veddy-backend:latest
