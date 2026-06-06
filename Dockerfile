FROM wlsdml1114/engui_genai-base_blackwell:1.1 as runtime

RUN pip install -U "huggingface_hub[hf_transfer]" && \
    pip install runpod websocket-client

WORKDIR /

RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install -r requirements.txt

RUN mkdir -p \
      /ComfyUI/models/audio_encoders \
      /ComfyUI/models/diffusion_models \
      /ComfyUI/models/text_encoders \
      /ComfyUI/models/vae && \
    wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors \
      -O /ComfyUI/models/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors && \
    wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors \
      -O /ComfyUI/models/audio_encoders/wav2vec2_large_english_fp16.safetensors && \
    wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
      -O /ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors && \
    wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors \
      -O /ComfyUI/models/vae/wan_2.1_vae.safetensors

COPY . .
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
