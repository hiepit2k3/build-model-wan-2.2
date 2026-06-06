# Wan2.2 S2V Image Option

This repository now supports building a separate RunPod Serverless image that includes the Wan2.2 S2V speech-to-video model assets.

## Build

Use the existing Dockerfile with the S2V build argument enabled:

```bash
docker build -t your-dockerhub-user/wan22-s2v:latest --build-arg INCLUDE_WAN22_S2V=true .
```

Then push it:

```bash
docker push your-dockerhub-user/wan22-s2v:latest
```

## Included S2V Assets

When `INCLUDE_WAN22_S2V=true`, the image downloads:

- `/ComfyUI/models/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors`
- `/ComfyUI/models/audio_encoders/wav2vec2_large_english_fp16.safetensors`
- `/ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- `/ComfyUI/models/vae/wan_2.1_vae.safetensors`

The S2V RunPod manifest is available at `.runpod/hub.s2v.json`.

## Handler Note

The S2V endpoint is selected when `mode` is `s2v` or any `audio_*` input is provided. Use these input fields:

- `image_path`, `image_url`, or `image_base64`
- `audio_path`, `audio_url`, or `audio_base64`
- `prompt`
- `negative_prompt`
- `seed`
- `width`
- `height`
- `steps`
- `cfg`
- `frame_rate`

## Request Example

```json
{
  "input": {
    "mode": "s2v",
    "image_url": "https://example.com/character.png",
    "audio_url": "https://example.com/voice.wav",
    "prompt": "A person speaks naturally to the camera with subtle facial expression and head movement.",
    "negative_prompt": "blurry, low quality, distorted, bad lip sync",
    "seed": 42,
    "width": 640,
    "height": 640,
    "length": 77,
    "steps": 20,
    "cfg": 6.0,
    "frame_rate": 16
  }
}
```

Wan2.2 S2V is substantially heavier than the current I2V image. Prefer fp8/offload settings first on RunPod Serverless GPUs.
