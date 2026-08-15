FROM python:3.12-slim

# System dependencies needed by WeasyPrint (Pango/Cairo for PDF text
# rendering — these can't be installed via pip, they're native libraries).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime — the shell form of CMD lets that env var
# actually get substituted (the exec/array form would not expand it).
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
