# F5-TTS + OpenVoice Production System

## 🎤 Multilingual TTS with Voice Cloning

A production-ready Text-to-Speech system combining:
- **F5-TTS**: State-of-the-art speech generation (10-15 sec cloning)
- **OpenVoice**: Enhanced voice cloning with emotion control

### ✨ Features

- ✅ **Multilingual**: English, Chinese, Spanish, French, German, and more
- ✅ **Voice Cloning**: Clone any voice with 10-15 seconds of audio
- ✅ **High Quality**: Professional-grade speech synthesis
- ✅ **MIT License**: Free for commercial use!
- ✅ **Fast**: Real-time factor of 0.15
- ✅ **No crashes**: Proper error handling (no sys.exit!)

## 🚀 Deployment on RunPod Serverless

### Configuration

**Basic Settings**:
- Name: `flowsmartly-tts-production`
- Docker: Build from GitHub Dockerfile

**GPU Configuration** (On-Demand Scaling):
- GPU Types: RTX 3090, RTX 4090, A40, A6000
- Workers Min: 0 (no idle workers = $0 cost when idle)
- Workers Max: 5
- Scaler Type: REQUEST_COUNT
- Scaler Value: 1
- Idle Timeout: 10 seconds

**Environment Variables** (Set these in RunPod console):
```bash
RUNPOD_S3_ACCESS_KEY=your_s3_access_key
RUNPOD_S3_SECRET_KEY=your_s3_secret_key
RUNPOD_S3_BUCKET=your_bucket_name
RUNPOD_S3_ENDPOINT=https://storage.runpod.io
HF_HOME=/workspace/.cache/huggingface
```

**Storage**:
- Container Disk: 30GB
- Network Volume: Optional (for model caching)

## 📝 API Usage

### 1. Simple TTS (No Voice Cloning)

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello! This is a test of the TTS system.",
      "language": "en"
    }
  }'
```

### 2. Voice Cloning (F5-TTS)

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "This is my cloned voice speaking!",
      "voice_clone_url": "https://example.com/voice_sample.wav",
      "voice_clone_text": "This is what I sound like.",
      "language": "en"
    }
  }'
```

### 3. Enhanced Voice Cloning (F5-TTS + OpenVoice)

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "This uses both F5-TTS and OpenVoice for better quality!",
      "voice_clone_url": "https://example.com/voice_sample.wav",
      "voice_clone_text": "Sample transcript of the voice.",
      "language": "en",
      "use_openvoice": true
    }
  }'
```

## 🌍 Supported Languages

- English (en), Spanish (es), French (fr), German (de)
- Italian (it), Portuguese (pt), Chinese (zh)
- Japanese (ja), Korean (ko), Hindi (hi)
- Arabic (ar), Russian (ru), Polish (pl)
- Turkish (tr), Dutch (nl)

## 📊 Performance

| GPU | TTS Time (10s audio) | Voice Clone | Cost/Request |
|-----|---------------------|-------------|--------------|
| RTX 3090 | ~2-3 seconds | ~5-7 sec | ~$0.002 |
| RTX 4090 | ~1-2 seconds | ~3-5 sec | ~$0.003 |
| A40 | ~3-4 seconds | ~6-8 sec | ~$0.004 |

## 🎯 User Flow

```
1. User uploads avatar image
2. User records 10-15 sec voice sample
3. System creates voice profile
4. User types text
5. F5-TTS generates audio in user's voice
6. MuseTalk creates video with avatar + voice
7. Personalized avatar video! 🎉
```

## 🔧 Integration

### Environment Variables

```bash
# Add to your .env file
RUNPOD_TTS_ENDPOINT=https://api.runpod.ai/v2/YOUR_TTS_ENDPOINT_ID
RUNPOD_API_KEY=your_runpod_api_key
```

### Example Integration

```typescript
async generateTTSWithVoiceClone(
  text: string,
  voiceProfileId: string
) {
  const profile = await this.getVoiceProfile(voiceProfileId);
  
  const response = await axios.post(
    `${this.ttsEndpoint}/run`,
    {
      input: {
        text,
        voice_clone_url: profile.voiceSampleUrl,
        voice_clone_text: profile.transcript,
        language: profile.language,
        use_openvoice: true
      }
    },
    {
      headers: {
        'Authorization': `Bearer ${this.runpodApiKey}`
      }
    }
  );
  
  return response.data.id;
}
```

## 📚 Resources

- **F5-TTS**: https://github.com/SWivid/F5-TTS
- **OpenVoice**: https://github.com/myshell-ai/OpenVoice
- **Demo**: https://f5tts.org

## 🐛 Troubleshooting

### Model download timeout
Increase execution timeout in RunPod settings to 900000ms (15 minutes)

### CUDA out of memory
- Use RTX 3090 or higher
- Process shorter text segments

### Poor voice quality
- Use 10-15 seconds of clean audio
- Provide accurate transcript
- Enable `use_openvoice: true`

---

**Production-ready TTS with voice cloning**
