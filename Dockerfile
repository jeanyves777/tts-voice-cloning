# Simplified TTS with F5-TTS for RunPod
# Start with F5-TTS only, add OpenVoice later

FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsndfile1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install core dependencies first
RUN pip install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    transformers \
    accelerate \
    einops \
    pydub \
    soundfile \
    librosa \
    cached-path \
    vocos

# Install F5-TTS from source
RUN git clone https://github.com/SWivid/F5-TTS.git /workspace/F5-TTS && \
    cd /workspace/F5-TTS && \
    pip install --no-cache-dir -e .

# Install RunPod and S3 dependencies
RUN pip install --no-cache-dir \
    runpod \
    boto3 \
    requests

# Copy handler files
COPY handler.py /workspace/handler.py
COPY voice_manager.py /workspace/voice_manager.py

# Set environment variables
ENV PYTHONPATH="/workspace/F5-TTS"
ENV HF_HOME="/workspace/.cache/huggingface"
ENV TORCH_HOME="/workspace/.cache/torch"

# Create cache directories
RUN mkdir -p /workspace/.cache/huggingface /workspace/.cache/torch

# Expose ports
EXPOSE 8000

# Run handler
CMD ["python", "-u", "/workspace/handler.py"]
