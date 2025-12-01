# veddy-backend
python3 -m venv ~/.virtualenvs/veddy-backend
source /home/june/.virtualenvs/veddy-backend/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
ngrok http 8000


az containerapp update \
--name ca-veddy-backend \
--resource-group VESSELLINK_BOT_RESOURCE \
--min-replicas 1 \
--max-replicas 3
