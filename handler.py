import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import urllib.error
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time
import shutil
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())
def to_nearest_multiple_of_16(value):
    """주어진 값을 가장 가까운 16의 배수로 보정, 최소 16 보장"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height 값이 숫자가 아닙니다: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted
def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 파일 경로를 반환하는 함수"""
    if input_type == "path":
        # 경로인 경우 그대로 반환
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return input_data
    elif input_type == "url":
        # URL인 경우 다운로드
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        # Base64인 경우 디코딩하여 저장
        logger.info(f"🔢 Base64 입력 처리")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

        
def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        # wget을 사용하여 파일 다운로드
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        # Base64 문자열 디코딩
        if isinstance(base64_data, str) and base64_data.strip().lower().startswith("data:") and "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]
        decoded_data = base64.b64decode(base64_data)
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        # 파일로 저장
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error(f"ComfyUI prompt failed with HTTP {exc.code}: {body}")
        raise Exception(f"ComfyUI prompt failed with HTTP {exc.code}: {body}")

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                # fullpath를 이용하여 직접 파일을 읽고 base64로 인코딩
                with open(video['fullpath'], 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        for output_key in ("gifs", "videos"):
            if output_key not in node_output:
                continue
            for video in node_output[output_key]:
                fullpath = video.get("fullpath")
                if not fullpath:
                    continue
                with open(fullpath, 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def resolve_media_input(job_input, task_id, field_prefix, output_filename, default_path=None, required=False):
    if f"{field_prefix}_path" in job_input:
        return process_input(job_input[f"{field_prefix}_path"], task_id, output_filename, "path")
    if f"{field_prefix}_url" in job_input:
        return process_input(job_input[f"{field_prefix}_url"], task_id, output_filename, "url")
    if f"{field_prefix}_base64" in job_input:
        return process_input(job_input[f"{field_prefix}_base64"], task_id, output_filename, "base64")
    if required:
        raise Exception(f"Missing required {field_prefix} input. Use {field_prefix}_path, {field_prefix}_url, or {field_prefix}_base64.")
    return default_path

def resolve_comfy_input(job_input, task_id, field_prefix, output_filename, required=False):
    comfy_input_dir = "/ComfyUI/input"
    task_input_dir = os.path.join(comfy_input_dir, task_id)
    os.makedirs(task_input_dir, exist_ok=True)
    relative_path = f"{task_id}/{output_filename}"
    target_path = os.path.join(task_input_dir, output_filename)

    if f"{field_prefix}_url" in job_input:
        download_file_from_url(job_input[f"{field_prefix}_url"], target_path)
        return relative_path
    if f"{field_prefix}_base64" in job_input:
        save_base64_to_file(job_input[f"{field_prefix}_base64"], task_input_dir, output_filename)
        return relative_path
    if f"{field_prefix}_path" in job_input:
        source_path = job_input[f"{field_prefix}_path"]
        if not os.path.exists(source_path):
            raise Exception(f"{field_prefix}_path does not exist: {source_path}")
        source_abs = os.path.abspath(source_path)
        comfy_abs = os.path.abspath(comfy_input_dir)
        if source_abs.startswith(comfy_abs + os.sep):
            return os.path.relpath(source_abs, comfy_abs).replace(os.sep, "/")
        shutil.copyfile(source_abs, target_path)
        return relative_path
    if required:
        raise Exception(f"Missing required {field_prefix} input. Use {field_prefix}_path, {field_prefix}_url, or {field_prefix}_base64.")
    return None

def configure_s2v_workflow(job_input, image_path, audio_path):
    prompt = load_workflow("/new_Wan22_s2v_api.json")

    width = to_nearest_multiple_of_16(job_input.get("width", 640))
    height = to_nearest_multiple_of_16(job_input.get("height", 640))
    length = int(job_input.get("length", 77))
    if length < 73:
        logger.info(f"S2V length adjusted to minimum supported frames: {length} -> 77")
        length = 77
    if length > 77:
        logger.info(f"S2V length capped to single-chunk workflow frames: {length} -> 77")
        length = 77

    steps = int(job_input.get("steps", 20))
    cfg = float(job_input.get("cfg", 6.0))
    frame_rate = int(job_input.get("frame_rate", 16))
    frame_rate = max(8, min(frame_rate, 30))

    prompt["160"]["inputs"]["image"] = image_path
    prompt["162"]["inputs"]["audio"] = audio_path
    prompt["159"]["inputs"]["text"] = job_input.get("prompt", "A person speaks naturally to the camera with subtle facial expression and head movement.")
    prompt["149"]["inputs"]["text"] = job_input.get("negative_prompt", "bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards")
    prompt["152"]["inputs"]["seed"] = int(job_input.get("seed", 42))
    prompt["152"]["inputs"]["steps"] = steps
    prompt["152"]["inputs"]["cfg"] = cfg
    prompt["153"]["inputs"]["width"] = width
    prompt["153"]["inputs"]["height"] = height
    prompt["153"]["inputs"]["length"] = length
    prompt["167"]["inputs"]["frame_rate"] = frame_rate

    return prompt

def run_prompt_and_return_video(prompt):
    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")

    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")

    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP connection succeeded (attempt {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP connection failed (attempt {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("Cannot connect to ComfyUI server.")
            time.sleep(1)

    ws = websocket.WebSocket()
    max_attempts = int(180 / 5)
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            logger.info(f"WebSocket connection succeeded (attempt {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"WebSocket connection failed (attempt {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("WebSocket connection timed out.")
            time.sleep(5)

    try:
        videos = get_videos(ws, prompt)
    finally:
        ws.close()

    for node_id in videos:
        if videos[node_id]:
            return {"video": videos[node_id][0]}

    return {"error": "Video not found."}

def handler(job):
    job_input = job.get("input", {})

    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"

    mode = str(job_input.get("mode", "")).lower()
    has_audio_input = any(key in job_input for key in ("audio_path", "audio_url", "audio_base64"))
    is_s2v = mode == "s2v" or has_audio_input
    if not is_s2v:
        raise Exception("This worker is S2V-only. Provide mode='s2v' with audio_path, audio_url, or audio_base64.")

    logger.info("Using S2V-only workflow")
    image_path = resolve_comfy_input(job_input, task_id, "image", "input_image.jpg", required=True)
    audio_path = resolve_comfy_input(job_input, task_id, "audio", "input_audio.wav", required=True)
    prompt = configure_s2v_workflow(job_input, image_path, audio_path)
    return run_prompt_and_return_video(prompt)

    # 이미지 입력 처리 (image_path, image_url, image_base64 중 하나만 사용)
    image_path = None
    if "image_path" in job_input:
        image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
    elif "image_url" in job_input:
        image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
    elif "image_base64" in job_input:
        image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
    else:
        # 기본값 사용
        image_path = "/example_image.png"
        logger.info("기본 이미지 파일을 사용합니다: /example_image.png")

    # 엔드 이미지 입력 처리 (end_image_path, end_image_url, end_image_base64 중 하나만 사용)
    end_image_path_local = None
    if "end_image_path" in job_input:
        end_image_path_local = process_input(job_input["end_image_path"], task_id, "end_image.jpg", "path")
    elif "end_image_url" in job_input:
        end_image_path_local = process_input(job_input["end_image_url"], task_id, "end_image.jpg", "url")
    elif "end_image_base64" in job_input:
        end_image_path_local = process_input(job_input["end_image_base64"], task_id, "end_image.jpg", "base64")

    mode = str(job_input.get("mode", "")).lower()
    has_audio_input = any(key in job_input for key in ("audio_path", "audio_url", "audio_base64"))
    is_s2v = mode == "s2v" or has_audio_input
    if not is_s2v:
        raise Exception("This worker is S2V-only. Provide mode='s2v' with audio_path, audio_url, or audio_base64.")
    audio_path = None
    if is_s2v:
        image_path = resolve_comfy_input(job_input, task_id, "image", "input_image.jpg", required=True)
        audio_path = resolve_comfy_input(job_input, task_id, "audio", "input_audio.wav", required=True)
    
    # LoRA 설정 확인 - 배열로 받아서 처리
    lora_pairs = job_input.get("lora_pairs", [])
    
    # 최대 4개 LoRA까지 지원
    lora_count = min(len(lora_pairs), 4)
    if lora_count > len(lora_pairs):
        logger.warning(f"LoRA 개수가 {len(lora_pairs)}개입니다. 최대 4개까지만 지원됩니다. 처음 4개만 사용합니다.")
        lora_pairs = lora_pairs[:4]
    
    # 워크플로우 파일 선택 (end_image_*가 있으면 FLF2V 워크플로 사용)
    workflow_file = "/new_Wan22_flf2v_api.json" if end_image_path_local else "/new_Wan22_api.json"
    logger.info(f"Using {'FLF2V' if end_image_path_local else 'single'} workflow with {lora_count} LoRA pairs")
    
    prompt = load_workflow(workflow_file)
    
    length = job_input.get("length", 81)
    steps = job_input.get("steps", 10)
    frame_rate = int(job_input.get("frame_rate", 16))
    frame_rate = max(8, min(frame_rate, 30))

    prompt["244"]["inputs"]["image"] = image_path
    prompt["541"]["inputs"]["num_frames"] = length
    prompt["135"]["inputs"]["positive_prompt"] = job_input.get("prompt", "A person speaks naturally to the camera with subtle facial expression and head movement.")
    prompt["135"]["inputs"]["negative_prompt"] = job_input.get("negative_prompt", "bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards")
    prompt["220"]["inputs"]["seed"] = job_input.get("seed", 42)
    prompt["540"]["inputs"]["seed"] = job_input.get("seed", 42)
    prompt["540"]["inputs"]["cfg"] = job_input.get("cfg", 2.0)
    # 해상도(폭/높이) 16배수 보정
    original_width = job_input.get("width", 480)
    original_height = job_input.get("height", 832)
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)
    if adjusted_width != original_width:
        logger.info(f"Width adjusted to nearest multiple of 16: {original_width} -> {adjusted_width}")
    if adjusted_height != original_height:
        logger.info(f"Height adjusted to nearest multiple of 16: {original_height} -> {adjusted_height}")
    prompt["235"]["inputs"]["value"] = adjusted_width
    prompt["236"]["inputs"]["value"] = adjusted_height
    prompt["498"]["inputs"]["context_overlap"] = job_input.get("context_overlap", 48)
    prompt["498"]["inputs"]["context_frames"] = length
    if "131" in prompt and "frame_rate" in prompt["131"].get("inputs", {}):
        prompt["131"]["inputs"]["frame_rate"] = frame_rate
        logger.info(f"Frame rate set to: {frame_rate}")

    # step 설정 적용
    if "834" in prompt:
        prompt["834"]["inputs"]["steps"] = steps
        logger.info(f"Steps set to: {steps}")
        lowsteps = int(steps*0.6)
        prompt["829"]["inputs"]["step"] = lowsteps
        logger.info(f"LowSteps set to: {lowsteps}")

    # 엔드 이미지가 있는 경우 617번 노드에 경로 적용 (FLF2V 전용)
    if end_image_path_local:
        prompt["617"]["inputs"]["image"] = end_image_path_local
    
    # LoRA 설정 적용 - HIGH LoRA는 노드 279, LOW LoRA는 노드 553
    if lora_count > 0:
        # HIGH LoRA 노드 (279번)
        high_lora_node_id = "279"
        
        # LOW LoRA 노드 (553번)
        low_lora_node_id = "553"
        
        # 입력받은 LoRA pairs 적용 (lora_1부터 시작)
        for i, lora_pair in enumerate(lora_pairs):
            if i < 4:  # 최대 4개까지만
                lora_high = lora_pair.get("high")
                lora_low = lora_pair.get("low")
                lora_high_weight = lora_pair.get("high_weight", 1.0)
                lora_low_weight = lora_pair.get("low_weight", 1.0)
                
                # HIGH LoRA 설정 (노드 279번, lora_1부터 시작)
                if lora_high:
                    prompt[high_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_high
                    prompt[high_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_high_weight
                    logger.info(f"LoRA {i+1} HIGH applied to node 279: {lora_high} with weight {lora_high_weight}")
                
                # LOW LoRA 설정 (노드 553번, lora_1부터 시작)
                if lora_low:
                    prompt[low_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_low
                    prompt[low_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_low_weight
                    logger.info(f"LoRA {i+1} LOW applied to node 553: {lora_low} with weight {lora_low_weight}")

    if is_s2v:
        logger.info("Using S2V workflow")
        prompt = configure_s2v_workflow(job_input, image_path, audio_path)

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # 먼저 HTTP 연결이 가능한지 확인
    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")
    
    # HTTP 연결 확인 (최대 1분)
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            import urllib.request
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    # 웹소켓 연결 시도 (최대 3분)
    max_attempts = int(180/5)  # 3분 (1초에 한 번씩 시도)
    for attempt in range(max_attempts):
        import time
        try:
            ws.connect(ws_url)
            logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과 (3분)")
            time.sleep(5)
    videos = get_videos(ws, prompt)
    ws.close()

    # 이미지가 없는 경우 처리
    for node_id in videos:
        if videos[node_id]:
            return {"video": videos[node_id][0]}
    
    return {"error": "비디오를를 찾을 수 없습니다."}

runpod.serverless.start({"handler": handler})
