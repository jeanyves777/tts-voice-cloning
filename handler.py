#!/usr/bin/env python3
"""
F5-TTS RunPod Serverless Handler (Simplified)
Multilingual TTS with voice cloning
NO sys.exit() - proper error handling
"""

import runpod
import os
import torch
import torchaudio
import tempfile
import shutil
from pathlib import Path
import requests
import traceback

print("[TTS] Starting F5-TTS handler...")

# S3 Configuration
S3_ACCESS_KEY = os.environ.get('RUNPOD_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('RUNPOD_S3_SECRET_KEY')
S3_BUCKET = os.environ.get('RUNPOD_S3_BUCKET', 'flowsmartly-avatars')
S3_ENDPOINT = os.environ.get('RUNPOD_S3_ENDPOINT', 'https://storage.runpod.io')

# Import S3 client if credentials available
s3_client = None
if S3_ACCESS_KEY and S3_SECRET_KEY:
    try:
        import boto3
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY
        )
        print("[S3] ✅ S3 client initialized")
    except Exception as e:
        print(f"[S3] ⚠️ S3 client failed: {e}")

# Global model (loaded once)
f5_model = None

def initialize_f5_tts():
    """Initialize F5-TTS model"""
    global f5_model

    if f5_model is not None:
        return True

    try:
        print("[F5-TTS] Loading model...")

        # Import F5-TTS
        from f5_tts.api import F5TTS

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[F5-TTS] Using device: {device}")

        # Initialize model with default settings
        # F5TTS() uses defaults: model_type="F5-TTS", ode_method="euler"
        f5_model = F5TTS()

        print(f"[F5-TTS] ✅ Model loaded successfully")
        return True

    except Exception as e:
        print(f"[F5-TTS] ❌ Failed to load: {e}")
        traceback.print_exc()
        return False

def download_file(url, local_path):
    """Download file from URL"""
    try:
        print(f"[Download] {url}")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[Download] ✅ Saved to {local_path}")
        return local_path, None

    except Exception as e:
        error = f"Download failed: {str(e)}"
        print(f"[Download] ❌ {error}")
        return None, error

def upload_to_s3(local_path, object_name=None):
    """Upload file to S3"""
    if not s3_client:
        return None, "S3 not configured"

    try:
        if object_name is None:
            object_name = f"tts-output/{Path(local_path).name}"

        print(f"[S3] Uploading to {S3_BUCKET}/{object_name}")

        s3_client.upload_file(
            local_path,
            S3_BUCKET,
            object_name,
            ExtraArgs={'ACL': 'public-read'}
        )

        url = f"{S3_ENDPOINT}/{S3_BUCKET}/{object_name}"
        print(f"[S3] ✅ Uploaded: {url}")
        return url, None

    except Exception as e:
        error = f"S3 upload failed: {str(e)}"
        print(f"[S3] ❌ {error}")
        return None, error

def generate_tts(text, language="en", ref_audio=None, ref_text=None):
    """
    Generate TTS audio

    Args:
        text: Text to synthesize
        language: Language code (en, es, fr, etc.)
        ref_audio: Path to reference audio for voice cloning (optional)
        ref_text: Transcript of reference audio (optional)

    Returns:
        (audio_path, error)
    """
    try:
        # Ensure model is loaded
        if not initialize_f5_tts():
            return None, "F5-TTS model not available"

        print(f"[TTS] Generating: '{text[:50]}...' (lang: {language})")

        # Create temp output file
        output_path = tempfile.mktemp(suffix='.wav')

        # Generate speech
        # F5TTS.infer() actually has ref_file and ref_text as optional
        # Let's use the simpler export_wav method for generation
        print(f"[TTS] Generating audio...")

        if ref_audio and ref_text:
            # Voice cloning mode
            print(f"[TTS] Using voice cloning with ref: {ref_audio}")
            audio, sample_rate = f5_model.infer(
                ref_file=ref_audio,
                ref_text=ref_text,
                gen_text=text,
                target_rms=0.1,
                nfe_step=32
            )
        else:
            # Default voice - use export_wav which doesn't need ref
            print(f"[TTS] Using default voice")
            audio, sample_rate = f5_model.export_wav(
                gen_text=text,
                file_wave=output_path,
                target_rms=0.1,
                nfe_step=32
            )
            print(f"[TTS] ✅ Generated: {output_path}")
            return output_path, None

        # Save audio if using voice cloning
        import soundfile as sf
        sf.write(output_path, audio, sample_rate)

        print(f"[TTS] ✅ Generated: {output_path}")
        return output_path, None

    except Exception as e:
        error = f"TTS generation failed: {str(e)}"
        print(f"[TTS] ❌ {error}")
        traceback.print_exc()
        return None, error

def handler(job):
    """
    RunPod serverless handler
    NO sys.exit() - returns error dict instead
    """
    job_input = job.get('input', {})

    # Get inputs
    text = job_input.get('text')
    if not text:
        return {"error": "text is required"}

    language = job_input.get('language', 'en')
    voice_clone_url = job_input.get('voice_clone_url')
    voice_clone_text = job_input.get('voice_clone_text')
    output_format = job_input.get('output_format', 'mp3')

    print(f"\n[Job] Starting TTS generation")
    print(f"[Job] Text length: {len(text)} chars")
    print(f"[Job] Language: {language}")
    print(f"[Job] Voice cloning: {'Yes' if voice_clone_url else 'No'}")

    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    ref_audio_path = None

    try:
        # Download reference audio if provided
        if voice_clone_url:
            ref_audio_path = os.path.join(temp_dir, 'ref_audio.wav')
            ref_audio_path, error = download_file(voice_clone_url, ref_audio_path)
            if error:
                return {"error": f"Failed to download voice sample: {error}"}

        # Generate TTS
        audio_path, error = generate_tts(
            text=text,
            language=language,
            ref_audio=ref_audio_path,
            ref_text=voice_clone_text
        )

        if error:
            return {"error": error}

        # Convert to requested format if needed
        final_path = audio_path
        if output_format != 'wav':
            final_path = audio_path.replace('.wav', f'.{output_format}')
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_wav(audio_path)
                audio.export(final_path, format=output_format)
                print(f"[Convert] ✅ Converted to {output_format}")
            except Exception as e:
                print(f"[Convert] ⚠️ Failed to convert to {output_format}: {e}")
                final_path = audio_path

        # Upload to S3
        audio_url, error = upload_to_s3(final_path)
        if error:
            # If S3 fails, return local path (RunPod will handle)
            print(f"[Job] ⚠️ S3 upload failed, returning local path")
            audio_url = final_path

        # Clean up
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

        print(f"[Job] ✅ Complete!")

        return {
            "audio_url": audio_url,
            "status": "completed",
            "language": language,
            "text_length": len(text),
            "voice_cloned": bool(voice_clone_url)
        }

    except Exception as e:
        # Clean up
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

        error_msg = f"Handler error: {str(e)}"
        print(f"[Job] ❌ {error_msg}")
        traceback.print_exc()

        return {"error": error_msg}

# Initialize model at startup
print("[TTS] Pre-loading F5-TTS model...")
initialize_f5_tts()
print("[TTS] Handler ready!")

# Start RunPod handler
if __name__ == "__main__":
    print("[RunPod] Starting serverless handler...")
    runpod.serverless.start({"handler": handler})
