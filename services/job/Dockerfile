FROM python:3.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/job/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY services/__init__.py ./services/__init__.py
COPY services/job ./services/job
COPY scripts ./scripts
RUN useradd --create-home appuser && mkdir -p /data/cvs && chown -R appuser:appuser /data
USER appuser
CMD ["sh", "-c", "python scripts/migrate.py job && exec uvicorn services.job.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
