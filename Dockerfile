# Spark Schedule — container image.
# Base: python:3.11-slim. Pre-installs the CJK font (so PDFs render Traditional
# Chinese without a separate fetch step) and all Python dependencies.
FROM python:3.11-slim

# System: CJK font + Latin font + build deps for pyswisseph.
# Uses fonts-droid-fallback (same as CI) so the font resolver finds the glyf
# TTF ReportLab can embed; fonts-noto-cjk ships a TTC which ReportLab can't.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-droid-fallback \
        fonts-liberation \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project.
COPY core/ ./core/
COPY Financial_Intelligence/ ./Financial_Intelligence/
COPY Global_Intelligence/ ./Global_Intelligence/
COPY Spiritual_Intelligence/ ./Spiritual_Intelligence/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY main.py .

# Default output goes to /app/output; mount a volume to extract PDFs.
ENV PYTHONUNBUFFERED=1 \
    SPARK_OUTPUT_DIR=/app/output
RUN mkdir -p /app/output

# fonts.py resolves the apt-installed Noto CJK at build time; verify on start.
ENTRYPOINT ["python", "main.py"]
CMD ["all"]
