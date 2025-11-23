#!/usr/bin/env python3
"""
F5-TTS + OpenVoice RunPod Serverless Handler
Multilingual TTS with voice cloning capabilities
NO sys.exit() - proper error handling
"""

import runpod
import os
import sys
import json
import torch
import torchaudio
import tempfile
import shutil
from pathlib import Path
import requests

print("[TTS] Initializing F5-TTS + OpenVoice handler...")

# Add to Python path
sys.path.insert(0, '/workspace/F5-TTS')
sys.path.insert(0, '/workspace/OpenVoice')

# Configuration
WORKSPACE = Path("/workspace")
F5_DIR = WORKSPACE / "F5-TTS"
OPENVOICE_DIR = WORKSPACE / "OpenVoice"
CACHE_DIR = WORKSPACE / ".cache"

# Create cache directory
CACHE_DIR.mkdir(exist_ok=True)

# Global models (loaded once at startup)
f5_model = None
f5_vocab = None
openvoice_model = None
tone_converter = None

def initialize_f5_tts():
    """Initialize F5-TTS model"""
    global f5_model, f5_vocab

    try:
        print("[F5-TTS] Loading model...")
        from f5_tts.api import F5TTS

        f5_model = F5TTS(
            model_type="F5-TTS",
            ckpt_file=None,  # Use default checkpoint
            vocab_file=None,
            ode_method="euler",
            use_ema=True,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"[F5-TTS] ✅ Model loaded on {f5_model.device}")
        return True

    except Exception as e:
        print(f"[F5-TTS] ⚠️ Failed to load: {e}")
        return False

def initialize_openvoice():
    """Initialize OpenVoice model"""
    global openvoice_model, tone_converter

    try:
        print("[OpenVoice] Loading model...")
        from openvoice import se_extractor
        from openvoice.api import ToneColorConverter

        ckpt_converter = str(OPENVOICE_DIR / "checkpoints" / "converter")
        device = "cuda" if torch.cuda.is_available() else "cpu"

        tone_converter = ToneColorConverter(f'{ckpt_converter}/config.json', device=device)
        tone_converter.load_ckpt(f'{ckpt_converter}/checkpoint.pth')

        print(f"[OpenVoice] ✅ Model loaded on {device}")
        return True

    except Exception as e:
        print(f"[OpenVoice] ⚠️ Failed to load: {e}")
        return False

# Initialize models at startup
print("[TTS] Initializing models...")
f5_initialized = initialize_f5_tts()
openvoice_initialized = initialize_openvoice()

if not f5_initialized:
    print("[TTS] ⚠️ F5-TTS not available - will try to load on first request")
if not openvoice_initialized:
    print("[TTS] ⚠️ OpenVoice not available - will try to load on first request")

def download_file(url, local_path):
    """Download file from URL"""
    try:
        print(f"[TTS] Downloading: {url}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"[TTS] Downloaded: {local_path}")
        return str(local_path), None

    except Exception as e:
        return None, f"Download failed: {str(e)}"

def upload_to_s3(file_path, bucket_name, object_name):
    """Upload file to S3"""
    try:
        import boto3
        from botocore.client import Config

        endpoint_url = os.getenv('RUNPOD_S3_ENDPOINT', 'https://storage.runpod.io')
        access_key = os.getenv('RUNPOD_S3_ACCESS_KEY')
        secret_key = os.getenv('RUNPOD_S3_SECRET_KEY')

        if not access_key or not secret_key:
            return None, "S3 credentials not configured"

        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4')
        )

        s3_client.upload_file(str(file_path), bucket_name, object_name)
        url = f"{endpoint_url}/{bucket_name}/{object_name}"

        print(f"[TTS] Uploaded to: {url}")
        return url, None

    except Exception as e:
        return None, f"S3 upload failed: {str(e)}"

def generate_f5_tts(text, ref_audio_path=None, ref_text=None, language="en"):
    """
    Generate speech using F5-TTS

    Args:
        text: Text to synthesize
        ref_audio_path: Optional reference audio for voice cloning
        ref_text: Optional reference text (transcript of ref_audio)
        language: Language code (en, zh, es, etc.)
    """
    global f5_model

    try:
        # Lazy load if not initialized
        if f5_model is None:
            if not initialize_f5_tts():
                return None, "F5-TTS model not available"

        print(f"[F5-TTS] Generating speech...")
        print(f"  Text: {text[:50]}...")
        print(f"  Language: {language}")
        print(f"  Voice clone: {ref_audio_path is not None}")

        # Generate audio
        if ref_audio_path and ref_text:
            # Voice cloning mode
            print(f"[F5-TTS] Cloning voice from: {ref_audio_path}")

            audio, sr = f5_model.infer(
                ref_file=ref_audio_path,
                ref_text=ref_text,
                gen_text=text,
                target_rms=0.1,
                cross_fade_duration=0.15,
                nfe_step=32,
            )
        else:
            # Use default voice
            print(f"[F5-TTS] Using default voice")

            audio, sr = f5_model.infer(
                ref_file=None,  # Use default voice
                ref_text="",
                gen_text=text,
                target_rms=0.1,
                nfe_step=32,
            )

        return audio, sr, None

    except Exception as e:
        print(f"[F5-TTS] Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None, f"F5-TTS generation failed: {str(e)}"

def apply_openvoice_cloning(source_audio_path, reference_audio_path, output_path):
    """
    Apply OpenVoice tone color conversion

    Args:
        source_audio_path: Path to generated TTS audio
        reference_audio_path: Path to reference voice sample
        output_path: Output path for cloned audio
    """
    global tone_converter

    try:
        # Lazy load if not initialized
        if tone_converter is None:
            if not initialize_openvoice():
                return None, "OpenVoice model not available"

        print(f"[OpenVoice] Applying voice cloning...")
        from openvoice import se_extractor

        # Extract tone from reference
        reference_se, _ = se_extractor.get_se(
            reference_audio_path,
            tone_converter,
            vad=True
        )

        # Convert tone
        tone_converter.convert(
            audio_src_path=source_audio_path,
            src_se=None,  # Let it extract automatically
            tgt_se=reference_se,
            output_path=output_path,
            message="@OpenVoice"
        )

        print(f"[OpenVoice] Voice cloned to: {output_path}")
        return output_path, None

    except Exception as e:
        print(f"[OpenVoice] Error: {e}")
        import traceback
        traceback.print_exc()
        return None, f"OpenVoice cloning failed: {str(e)}"

def handler(job):
    """
    RunPod Serverless Handler

    Input format:
    {
        "text": "Hello world",
        "language": "en",  // optional: en, zh, es, fr, de, etc.
        "voice_clone_url": "https://...",  // optional: URL to voice sample
        "voice_clone_text": "Transcript...",  // optional: transcript of voice sample
        "use_openvoice": true,  // optional: use OpenVoice for better cloning
        "output_format": "mp3"  // optional: mp3, wav (default: mp3)
    }
    """
    try:
        job_input = job.get('input', {})
        job_id = job.get('id', 'unknown')

        print(f"[TTS] Processing job: {job_id}")

        # Validate inputs
        text = job_input.get('text')
        if not text:
            print("[TTS] ERROR: Missing text")
            return {"error": "text is required"}

        language = job_input.get('language', 'en')
        voice_clone_url = job_input.get('voice_clone_url')
        voice_clone_text = job_input.get('voice_clone_text')
        use_openvoice = job_input.get('use_openvoice', False)
        output_format = job_input.get('output_format', 'mp3')

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="tts_")
        print(f"[TTS] Temp dir: {temp_dir}")

        try:
            # Download voice sample if provided
            ref_audio_path = None
            if voice_clone_url:
                ref_audio_path = os.path.join(temp_dir, "reference.wav")
                downloaded_ref, error = download_file(voice_clone_url, ref_audio_path)

                if error:
                    print(f"[TTS] ERROR: {error}")
                    return {"error": f"Failed to download voice sample: {error}"}

                ref_audio_path = downloaded_ref

            # Generate audio with F5-TTS
            audio, sample_rate, error = generate_f5_tts(
                text=text,
                ref_audio_path=ref_audio_path,
                ref_text=voice_clone_text,
                language=language
            )

            if error:
                print(f"[TTS] ERROR: {error}")
                return {"error": error}

            # Save F5-TTS output
            f5_output = os.path.join(temp_dir, "f5_output.wav")
            torchaudio.save(f5_output, audio, sample_rate)

            # Apply OpenVoice cloning if requested
            final_audio_path = f5_output
            if use_openvoice and ref_audio_path:
                print("[TTS] Applying OpenVoice enhancement...")
                openvoice_output = os.path.join(temp_dir, "openvoice_output.wav")

                cloned_path, error = apply_openvoice_cloning(
                    source_audio_path=f5_output,
                    reference_audio_path=ref_audio_path,
                    output_path=openvoice_output
                )

                if error:
                    print(f"[TTS] OpenVoice warning: {error}")
                    # Continue with F5-TTS output
                else:
                    final_audio_path = cloned_path

            # Convert to requested format
            output_file = os.path.join(temp_dir, f"output.{output_format}")

            if output_format == "mp3":
                # Convert to MP3 using ffmpeg
                import subprocess
                cmd = [
                    "ffmpeg", "-y",
                    "-i", final_audio_path,
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",
                    output_file
                ]
                subprocess.run(cmd, check=True, capture_output=True)
            else:
                # Keep as WAV
                shutil.copy(final_audio_path, output_file)

            # Upload to S3
            bucket = os.getenv('RUNPOD_S3_BUCKET', 'flowsmartly-avatars')
            object_name = f"tts/{job_id}.{output_format}"

            audio_url, error = upload_to_s3(output_file, bucket, object_name)

            if error:
                print(f"[TTS] ERROR: {error}")
                return {"error": error}

            print(f"[TTS] ✅ Success: {audio_url}")

            return {
                "audio_url": audio_url,
                "status": "completed",
                "model": "f5-tts" + ("+openvoice" if use_openvoice else ""),
                "language": language,
                "format": output_format,
                "job_id": job_id
            }

        finally:
            # Cleanup
            try:
                shutil.rmtree(temp_dir)
                print(f"[TTS] Cleaned up: {temp_dir}")
            except:
                pass

    except Exception as e:
        print(f"[TTS] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Handler error: {str(e)}"}

# Startup check
if __name__ == "__main__":
    print("[TTS] Starting RunPod Serverless Worker...")
    print(f"[TTS] Python: {sys.version}")
    print(f"[TTS] Workspace: {WORKSPACE}")

    # Check CUDA
    try:
        import torch
        print(f"[TTS] PyTorch: {torch.__version__}")
        print(f"[TTS] CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[TTS] GPU: {torch.cuda.get_device_name(0)}")
            print(f"[TTS] Compute: {torch.cuda.get_device_capability(0)}")
    except:
        print("[TTS] WARNING: PyTorch/CUDA check failed")

    # Check S3 config
    if os.getenv('RUNPOD_S3_ACCESS_KEY'):
        print("[TTS] ✅ S3 credentials configured")
    else:
        print("[TTS] ⚠️ S3 credentials not found")

    # Check models
    print(f"[TTS] F5-TTS: {'✅ Ready' if f5_initialized else '⚠️ Will load on first request'}")
    print(f"[TTS] OpenVoice: {'✅ Ready' if openvoice_initialized else '⚠️ Will load on first request'}")

    print("[TTS] Ready to process jobs!")

    # Start RunPod worker
    runpod.serverless.start({"handler": handler})
