# Production TTS with F5-TTS + OpenVoice for RunPod
# Multilingual voice generation and cloning

FROM runpod/pytorch:2.2.0-py3.11-cuda12.1.1-devel-ubuntu22.04

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsndfile1 \
    libsox-dev \
    sox \
    espeak-ng \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install F5-TTS
RUN git clone https://github.com/SWivid/F5-TTS.git /workspace/F5-TTS && \
    cd /workspace/F5-TTS && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir \
    torch \
    torchaudio \
    transformers \
    accelerate \
    cached_path \
    einops \
    vocos \
    pydub \
    soundfile

# Install OpenVoice
RUN git clone https://github.com/myshell-ai/OpenVoice.git /workspace/OpenVoice && \
    cd /workspace/OpenVoice && \
    pip install --no-cache-dir -r requirements.txt

# Install RunPod SDK and utilities
RUN pip install --no-cache-dir \
    runpod \
    boto3 \
    requests \
    fastapi \
    uvicorn \
    python-multipart

# Download F5-TTS models
RUN cd /workspace/F5-TTS && \
    python3 -c "from f5_tts.infer.utils_infer import load_model; load_model('F5-TTS')" || \
    echo "Models will download at first run"

# Download OpenVoice models
RUN cd /workspace/OpenVoice && \
    mkdir -p checkpoints && \
    wget -q https://myshell-public-repo-hosting.s3.amazonaws.com/openvoice/basespeakers/EN/en_default_se.pth -O checkpoints/base_speakers/EN/en_default_se.pth || \
    echo "Models will download at first run"

# Copy handler
COPY handler.py /workspace/handler.py
COPY voice_manager.py /workspace/voice_manager.py

# Set environment variables
ENV PYTHONPATH="/workspace/F5-TTS:/workspace/OpenVoice:${PYTHONPATH}"
ENV HF_HOME="/workspace/.cache/huggingface"

# Expose ports
EXPOSE 8000

# Run handler
CMD ["python", "-u", "/workspace/handler.py"]
