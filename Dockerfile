# The app image: Python 3.12, CPU-only PyTorch, every Hugging Face model the
# app uses already downloaded, served by waitress (serve.py).
#
# Normally built and run by docker-compose.yml (app + PostgreSQL + Redis):
#     docker compose up --build
#
# Layers go from least to most often changed, so editing the code rebuilds only
# the last step (seconds); the packages and models (~3 GB) stay cached.
#
# Not in the image: the trained Round 1 evaluator weights (735 MB, git LFS).
# docker-compose.yml mounts them from the repository; without them Round 1 uses
# the heuristic evaluator, as when running without Docker.

FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

RUN useradd --create-home --uid 1000 cap

# 1. Python packages. CPU-only torch first (about 2 GB smaller than the default
#    CUDA build; nothing at interview time needs a GPU), then the app's part of
#    Requirements_Global.txt: everything above the offline-only sections (slide
#    pipeline, developer tools, tests). Versions are pinned to the ones the
#    project is tested with (docker/constraints.txt).
RUN pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
COPY Requirements_Global.txt docker/constraints.txt /tmp/
RUN sed '/Slide pipeline and question-bank rebuild/,$d' /tmp/Requirements_Global.txt > /tmp/requirements-app.txt \
 && pip install -r /tmp/requirements-app.txt -c /tmp/constraints.txt

# 2. Models (~1.8 GB), downloaded now so the container starts without internet.
COPY docker/download_models.py /tmp/
RUN python /tmp/download_models.py && chown -R cap:cap /opt/hf

# 3. The code: the app and the technical interview's question bank (see .dockerignore for what is left out).
WORKDIR /app
COPY --chown=cap:cap rag_system/rag_tester/question_bank/ rag_system/rag_tester/question_bank/
COPY --chown=cap:cap main_cap/cap/ main_cap/cap/
# instance/ holds uploads and the generated secret key; docker-compose.yml puts
# a volume here so they survive the container being replaced.
RUN mkdir -p main_cap/cap/instance && chown cap:cap main_cap/cap/instance

USER cap
WORKDIR /app/main_cap/cap
ENV CAP_HOST=0.0.0.0 \
    CAP_PORT=5000
EXPOSE 5000

# Healthy once the server answers; models keep loading in the background.
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4)"

CMD ["python", "serve.py"]
