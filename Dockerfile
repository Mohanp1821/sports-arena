# Dockerfile: the recipe for the Sports Arena container image.
# The same image is used by both services in docker-compose.yml.

# 1. Start from an official, small Python image.
FROM python:3.12-slim

# 2. All project files live in /app inside the container.
WORKDIR /app

# 3. Install the pinned libraries first (Docker caches this layer,
#    so later rebuilds are fast when only the code changes).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3b. Node.js (open source) runs the chatbot's question checks (tests/test_chatbot.js).
RUN apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*

# 4. Copy the code, tests and data into the image.
COPY src/ src/
COPY tests/ tests/
COPY data/ data/

# 5. Default command: run the whole pipeline in order.
#    verify data -> clean data -> charts -> fact checks -> Model A -> Model B -> dashboard pages -> chatbot checks
CMD python src/verify_data.py && \
    python src/prepare_data.py && \
    python src/analysis.py && \
    python tests/test_facts.py && \
    python src/predict.py && \
    python src/predict_ml.py && \
    python src/build_report.py && \
    node tests/test_chatbot.js && \
    node tests/test_site.js
