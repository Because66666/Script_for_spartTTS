# Copyright (c) 2025 SparkAudio
#               2025 Xinsheng Wang (w.xinshawn@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import subprocess
import torch
import soundfile as sf
import logging
import argparse
import gradio as gr
import platform
from datetime import datetime
from cli.SparkTTS import SparkTTS
from sparktts.utils.token_parser import LEVELS_MAP_UI
import re
import importlib.util
import sys


def check_and_install(package,version):
    try:
        spec = importlib.util.find_spec(package)
        if spec is None:
            print(f"{package} 未安装，开始安装 {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", f"{package}"])
        else:
            print(f"{package} 已安装。")
    except subprocess.CalledProcessError as e:
        print(f"安装 {package}时出错: {e}")


libraries = {
    "matplotlib": "3.8.0",
    "numpy": "1.26.0",
    "librosa": "0.7.2",
    "scipy": " 1.15.2",
    "tensorboard": "2.11.2",
    "einops": "0.8.0",
    "joblib": "1.3.2",
    "natsort": "8.3.0"
}




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
    delimiters = r'[\。\，\、\；\：\？\！\……]'
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
            se2.append('  '+cache + s2)
            cache = ''
    if cache:
        se2.append('  '+cache) # 前面加空格是为了防止之后连接不太流畅。
    lines2 += se2
    return lines2

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
    for index,t in enumerate(text_list):
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
    files=''
    for index in range(len(text_list)):
        save_path = f"./output/cache_{index}.wav"
        files += f"file {save_path}\n"
    with open('file_list.txt', 'w', encoding='utf8') as e:
        e.write(files)

    # 依次对各视频进行超分,视频存储在/AP_BWE/output/
    absolute_path = os.path.abspath(save_dir)
    process = subprocess.Popen(['python', 'inference_48k.py', '--checkpoint_file', './checkpoints/16kto48k/g_16kto48k', '--output_dir', 'output', '--input_wavs_dir',absolute_path]
                               ,cwd='./AP_BWE')
    return_code = process.wait()
    if return_code != 0:
        logging.error("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        logging.error("Error:", stderr)
    shutil.copy('file_list.txt',os.path.join('AP_BWE','file_list.txt'))
    filename = '[已超分]'+datetime.now().strftime("%Y-%m-%d_%H-%M-%S")+'.wav'
    if os.path.exists(filename):
        os.remove(filename)

    # 将视频合成在一起。存储在/[已超分].wav
    process = subprocess.Popen(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,cwd='./AP_BWE')
    return_code = process.wait()
    save_path = ''
    if return_code != 0:
        logging.error("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        logging.error("Error:", stderr)
    else:
        logging.info("Subprocess completed successfully.")
        # os.startfile(filename)
        logging.info('已经完成超分音频合成。')
        save_path = os.path.abspath('./AP_BWE/'+filename)
    return save_path


def build_ui(model_dir, device=0):

    # Initialize model
    model = initialize_model(model_dir, device=device)

    # Define callback function for voice cloning
    def voice_clone(text, prompt_text, prompt_wav_upload, prompt_wav_record):
        """
        Gradio callback to clone voice using text and optional prompt speech.
        - text: The input text to be synthesised.
        - prompt_text: Additional textual info for the prompt (optional).
        - prompt_wav_upload/prompt_wav_record: Audio files used as reference.
        """
        prompt_speech = prompt_wav_upload if prompt_wav_upload else prompt_wav_record
        prompt_text_clean = None if len(prompt_text) < 2 else prompt_text

        audio_output_path = run_tts(
            text,
            model,
            prompt_text=prompt_text_clean,
            prompt_speech=prompt_speech
        )
        return audio_output_path

    # Define callback function for creating new voices
    def voice_creation(text, gender, pitch, speed):
        """
        Gradio callback to create a synthetic voice with adjustable parameters.
        - text: The input text for synthesis.
        - gender: 'male' or 'female'.
        - pitch/speed: Ranges mapped by LEVELS_MAP_UI.
        """
        pitch_val = LEVELS_MAP_UI[int(pitch)]
        speed_val = LEVELS_MAP_UI[int(speed)]
        audio_output_path = run_tts(
            text,
            model,
            gender=gender,
            pitch=pitch_val,
            speed=speed_val
        )
        return audio_output_path

    with gr.Blocks() as demo:
        # Use HTML for centered title
        gr.HTML('<h1 style="text-align: center;">Spark-TTS by SparkAudio</h1>')
        with gr.Tabs():
            # Voice Clone Tab
            with gr.TabItem("Voice Clone"):
                gr.Markdown(
                    "### Upload reference audio or recording （上传参考音频或者录音）"
                )

                with gr.Row():
                    prompt_wav_upload = gr.Audio(
                        sources="upload",
                        type="filepath",
                        label="Choose the prompt audio file, ensuring the sampling rate is no lower than 16kHz.",
                    )
                    prompt_wav_record = gr.Audio(
                        sources="microphone",
                        type="filepath",
                        label="Record the prompt audio file.",
                    )

                with gr.Row():
                    text_input = gr.Textbox(
                        label="Text", lines=3, placeholder="Enter text here"
                    )
                    prompt_text_input = gr.Textbox(
                        label="Text of prompt speech (Optional; recommended for cloning in the same language.)",
                        lines=3,
                        placeholder="Enter text of the prompt speech.",
                    )

                audio_output = gr.Audio(
                    label="Generated Audio", autoplay=True, streaming=True
                )

                generate_buttom_clone = gr.Button("Generate")

                generate_buttom_clone.click(
                    voice_clone,
                    inputs=[
                        text_input,
                        prompt_text_input,
                        prompt_wav_upload,
                        prompt_wav_record,
                    ],
                    outputs=[audio_output],
                )

            # Voice Creation Tab
            with gr.TabItem("Voice Creation"):
                gr.Markdown(
                    "### Create your own voice based on the following parameters"
                )

                with gr.Row():
                    with gr.Column():
                        gender = gr.Radio(
                            choices=["male", "female"], value="male", label="Gender"
                        )
                        pitch = gr.Slider(
                            minimum=1, maximum=5, step=1, value=3, label="Pitch"
                        )
                        speed = gr.Slider(
                            minimum=1, maximum=5, step=1, value=3, label="Speed"
                        )
                    with gr.Column():
                        text_input_creation = gr.Textbox(
                            label="Input Text",
                            lines=3,
                            placeholder="Enter text here",
                            value="You can generate a customized voice by adjusting parameters such as pitch and speed.",
                        )
                        create_button = gr.Button("Create Voice")

                audio_output = gr.Audio(
                    label="Generated Audio", autoplay=True, streaming=True
                )
                create_button.click(
                    voice_creation,
                    inputs=[text_input_creation, gender, pitch, speed],
                    outputs=[audio_output],
                )

    return demo


def parse_arguments():
    """
    Parse command-line arguments such as model directory and device ID.
    """
    parser = argparse.ArgumentParser(description="Spark TTS Gradio server.")
    parser.add_argument(
        "--model_dir",
        type=str,
        default="pretrained_models/Spark-TTS-0.5B",
        help="Path to the model directory."
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="ID of the GPU device to use (e.g., 0 for cuda:0)."
    )
    parser.add_argument(
        "--server_name",
        type=str,
        default="0.0.0.0",
        help="Server host/IP for Gradio app."
    )
    parser.add_argument(
        "--server_port",
        type=int,
        default=7860,
        help="Server port for Gradio app."
    )
    return parser.parse_args()

if __name__ == "__main__":
    if not os.path.exists('AP_BWE'):
        raise Exception('必要组件 AP_BWE 未找到，请根据指引复制文件夹到本目录下。')
    if not os.path.exists('./AP_BWE/checkpoints/16kto48k/config.json'):
        raise Exception('必要组件 AP_BWE的checkpoint未找到，请根据指引复制文件夹到本目录下。')
    print('适用于AP_BWE插件的依赖库检查。')
    for package, version in libraries.items():
        check_and_install(package, version)
    print("所有库检查和安装完成。")
    # Parse command-line arguments
    args = parse_arguments()

    # Build the Gradio demo by specifying the model directory and GPU device
    demo = build_ui(
        model_dir=args.model_dir,
        device=args.device
    )

    # Launch Gradio with the specified server name and port
    demo.launch(
        server_name=args.server_name,
        server_port=args.server_port
    )
