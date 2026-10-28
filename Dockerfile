FROM python:3.12-slim
ARG INSTALL_ML=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 TOKENIZERS_PARALLELISM=false
WORKDIR /srv/fluilet
COPY requirements.txt ./
COPY ml_training/requirements.txt ./ml_training/requirements.txt
RUN pip install -r requirements.txt && if [ "$INSTALL_ML" = "true" ]; then pip install -r ml_training/requirements.txt; fi
RUN useradd --uid 10001 --no-create-home fluilet
COPY app ./app
COPY app/services/assets/context-ranker-v2.3.json ./checkpoints/context-ranker-v2.3/model.json
ENV RANKER_CHECKPOINT=/srv/fluilet/checkpoints/context-ranker-v2.3/model.json
ENV DEPLOYMENT_ENV=production
COPY ml_training/__init__.py ml_training/prepare_easier.py ./ml_training/
COPY alembic ./alembic
COPY alembic.ini ./
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "app.bootstrap"]
