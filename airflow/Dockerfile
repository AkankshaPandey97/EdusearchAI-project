FROM apache/airflow:2.10.3

USER root

# Install system-level dependencies
RUN apt-get update && \
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        gnupg \
        curl \
        tesseract-ocr \
        wget \
        chromium-driver && \
    echo "deb https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update && \
    apt-get install -y google-cloud-sdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Pre-download EasyOCR models (optional, reduces runtime latency for the first usage)
RUN python -c "from easyocr import Reader; Reader(['en'], download_enabled=True)"

# Switch back to airflow user
USER airflow

# Set the entrypoint to use the default Airflow entrypoint
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Set the default command for the container
CMD ["webserver"]
