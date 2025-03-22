# ... 原有的导入部分 ...
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime
import torch
from fastapi import FastAPI
from pydantic import BaseModel
import logging
from sparktts.utils.token_parser import LEVELS_MAP_UI
from cli.SparkTTS import SparkTTS
import soundfile as sf

# 创建 FastAPI 应用实例
app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s : %(message)s")


def initialize_model(model_dir="pretrained_models/Spark-TTS-0.5B", device=0):
    """Load the model once at the beginning."""
    logging.info(f"Loading model from: {model_dir}")

    # Determine appropriate device based on platform and availability
    if platform.system() == "Darwin":
        # macOS with MPS support (Apple Silicon)
        device = torch.device(f"mps:{device}")
        logging.info(f"Using MPS device: {device}")
    elif torch.cuda.is_available():
        # System with CUDA support
        device = torch.device(f"cuda:{device}")
        logging.info(f"Using CUDA device: {device}")
    else:
        # Fall back to CPU
        device = torch.device("cpu")
        logging.info("GPU acceleration not available, using CPU")

    model = SparkTTS(model_dir, device)
    return model


def strip_text(text):
    """分割长文本为多个短文本。"""
    lines2 = []
    delimiters = r'[\。\，\、\；\：\？\！\……\,\.\?\:]'
    sentences = re.split(delimiters, text)
    cache = ''
    se2 = []
    for sen in sentences:
        s2 = sen.strip()
        if s2 == '':
            continue
        if len(s2) <= 10:
            cache += s2 + '，'
        else:
            se2.append('  ' + cache + s2)
            cache = ''
    if cache:
        se2.append('  ' + cache)  # 前面加空格是为了防止之后连接不太流畅。
    lines2 += se2
    return lines2


# 初始化模型
model = initialize_model()


# 定义语音克隆请求的数据模型
class VoiceCloneRequest(BaseModel):
    text: str
    prompt_text: str = None
    prompt_speech: str = None


# 定义语音创建请求的数据模型
class VoiceCreationRequest(BaseModel):
    text: str
    gender: str
    pitch: int
    speed: int


def run_tts(
        text,
        model,
        prompt_text=None,
        prompt_speech=None,
        gender=None,
        pitch=None,
        speed=None,
        save_dir="example/results",
):
    """Perform TTS inference and save the generated audio."""
    logging.info(f"Saving audio to: {save_dir}")
    if prompt_text is not None:
        prompt_text = None if len(prompt_text) <= 1 else prompt_text

    # Ensure the save directory exists
    os.makedirs(save_dir, exist_ok=True)

    # 先将语句拆分，后分别合成.视频存储在：/example/results/cache_0.wav, cache_1.wav, ...
    text_list = strip_text(text)
    logging.info(f"切分为了: {len(text_list)} 段")
    for index, t in enumerate(text_list):
        # Generate unique filename using timestamp
        save_path = os.path.join(save_dir, f"cache_{index}.wav")
        logging.info("Starting inference...")

        # Perform inference and save the output audio
        with torch.no_grad():
            wav = model.inference(
                t,
                prompt_speech,
                prompt_text,
                gender,
                pitch,
                speed,
            )
            sf.write(save_path, wav, samplerate=16000)
        logging.info(f"Audio saved at: {save_path}")
    files = ''
    for index in range(len(text_list)):
        save_path = f"./output/cache_{index}.wav"
        files += f"file {save_path}\n"
    with open('file_list.txt', 'w', encoding='utf8') as e:
        e.write(files)

    # 依次对各视频进行超分,视频存储在/AP_BWE/output/
    absolute_path = os.path.abspath(save_dir)
    process = subprocess.Popen(
        ['python', 'inference_48k.py', '--checkpoint_file', './checkpoints/16kto48k/g_16kto48k', '--output_dir',
         'output', '--input_wavs_dir', absolute_path]
        , cwd='./AP_BWE')
    return_code = process.wait()
    if return_code != 0:
        logging.error(f"Subprocess failed with return code:{return_code}")
        stderr = process.stderr.read().decode('utf-8')
        logging.error(f"Error:{stderr}")
    shutil.copy('file_list.txt', os.path.join('AP_BWE', 'file_list.txt'))
    filename = '[已超分]' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '.wav'
    if os.path.exists(f'./AP_BWE/{filename}'):
        os.remove(f'./AP_BWE/{filename}')
    logging.info('合成前检查。')
    flag = False
    for index in range(len(text_list)):
        filename0 = f'./AP_BWE/output/cache_{index}.wav'
        if os.path.exists(filename0):
            pass
        else:
            logging.info(f"{filename0} does not exist.")
            flag = True
    if flag:
        raise Exception('合成检查未通过。')
    logging.info('合成检查已通过。')
    # 将视频合成在一起。存储在./AP_BWE/[已超分].wav
    process = subprocess.Popen(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='./AP_BWE', shell=True)
    return_code = process.wait()
    save_path = ''
    if return_code != 0:
        logging.error(f"Subprocess failed with return code:{return_code}")
        stderr = process.stderr.read().decode('utf-8')
        logging.error(f"Error:{stderr}")
    else:
        logging.info("Subprocess completed successfully.")
        # os.startfile(filename)
        logging.info('已经完成超分音频合成。')
        save_path = os.path.abspath('./AP_BWE/' + filename)

    return save_path


def run_tts_old(
        text,
        model,
        prompt_text=None,
        prompt_speech=None,
        gender=None,
        pitch=None,
        speed=None,
        save_dir="example/results",
):
    """Perform TTS inference and save the generated audio."""
    logging.info(f"Saving audio to: {save_dir}")

    if prompt_text is not None:
        prompt_text = None if len(prompt_text) <= 1 else prompt_text

    # Ensure the save directory exists
    os.makedirs(save_dir, exist_ok=True)

    # Generate unique filename using timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    save_path = os.path.join(save_dir, f"{timestamp}.wav")

    logging.info("Starting inference...")

    # Perform inference and save the output audio
    with torch.no_grad():
        wav = model.inference(
            text,
            prompt_speech,
            prompt_text,
            gender,
            pitch,
            speed,
        )

        sf.write(save_path, wav, samplerate=16000)

    logging.info(f"Audio saved at: {save_path}")

    return save_path


# 语音克隆 API 端点
@app.post("/voice_clone")
async def voice_clone_api(request: VoiceCloneRequest):
    prompt_text_clean = None if len(request.prompt_text) < 2 else request.prompt_text
    audio_output_path = run_tts(
        request.text,
        model,
        prompt_text=prompt_text_clean,
        prompt_speech=request.prompt_speech
    )
    return {"audio_path": audio_output_path}


# 语音创建 API 端点
@app.post("/voice_creation")
async def voice_creation_api(request: VoiceCreationRequest):
    pitch_val = LEVELS_MAP_UI[int(request.pitch)]
    speed_val = LEVELS_MAP_UI[int(request.speed)]
    audio_output_path = run_tts_old(
        request.text,
        model,
        gender=request.gender,
        pitch=pitch_val,
        speed=speed_val
    )
    return {"audio_path": audio_output_path}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
