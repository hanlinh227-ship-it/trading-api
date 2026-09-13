FROM python:3.13-slim
WORKDIR /app
COPY research/cloud_10coin_backtest/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY research/cloud_10coin_backtest/ ./
ENV PYTHONPATH=/app
CMD ["pytest", "tests/test_g2_global_candidate_guard.py", "-q"]
