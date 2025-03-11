FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Rust and build dependencies
RUN apt-get update && \
    apt-get -y install curl build-essential libssl-dev pkg-config && \
    rm -rf /var/lib/apt/lists/* && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    cargo --version

WORKDIR /app
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --upgrade openai httpx

CMD ["python", "app.py"]
