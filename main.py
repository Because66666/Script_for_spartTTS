import re
from gradio_client import Client, file, handle_file
import shutil
import os
from tqdm import tqdm
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import *
import requests


if not os.path.exists(save_path):
    os.makedirs(save_path)

if not using_fast_api:
    client = Client("http://127.0.0.1:7860/")

def make_wav(msg: str, filename: str):
    global client
    # source_file = client.predict(
    #     text=msg,
    #     prompt_text="",
    #     prompt_wav_upload=handle_file(
    #         'http://127.0.0.1:7860/gradio_api/file=C:\\Users\\z6666\\AppData\\Local\\Temp\\gradio\\424211eca52990f509479aba525798383f55105efba2033c7384a14d74191fbb\\纳西妲-正常.wav'),
    #     prompt_wav_record=None,
    #     api_name="/voice_clone"
    # )
    source_file = client.predict(
        text=msg,
        prompt_text="",
        prompt_wav_upload=file(used_voices),
        prompt_wav_record=None,
        api_name="/voice_clone"
    )
    destination_file = os.path.join(save_path, filename)
    shutil.copyfile(source_file, destination_file)

def make_wav_v2(msg: str, filename: str):
    # 定义 API 端点
    voice_clone_url = "http://localhost:8000/voice_clone"

    # 定义请求数据
    data = {
        "text": msg,
        "prompt_text": "",
        "prompt_speech": os.path.abspath(used_voices) # 替换为实际的提示音频文件路径
    }
    # 发送 POST 请求
    response = requests.post(voice_clone_url, json=data)

    # 检查响应状态
    if response.status_code == 200:
        result = response.json()
        destination_file = os.path.join(save_path, filename)
        shutil.copyfile(result["audio_path"], destination_file)
        # print("语音克隆成功，音频文件路径为:", result["audio_path"])
    else:
        print("语音克隆失败，错误信息:", response.text)

def read_txt(path: str, debug=False):
    # 读取文件、分词、分段合成。
    if not os.path.exists(path):
        print("文件不存在")
        return
    with open(path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    lines2 = []
    if debug:
        from pprint import pp
        pp(lines)
    for line in lines:
        line = line.strip()
        if line == "":
            continue
        delimiters = r'[\。\，\、\；\：\？\！\……]'
        sentences = re.split(delimiters, line)
        cache = ''
        se2 = []
        for sen in sentences:
            s2 = sen.strip()
            if s2 == '':
                continue
            if len(s2) <= 10:
                cache += s2 + '，'
            else:
                se2.append('  '+ cache+s2)
                cache = ''
        if cache:
            se2.append('  '+cache.strip('，')) # 前面加空格是为了防止之后连接不太流畅。
        lines2 += se2
    files = ""
    print(f'切分为了{len(lines2)}段。')
    if not debug:
        # 使用 ThreadPoolExecutor 进行多线程处理
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(make_wav, line, f"{num}.wav"): num for num, line in enumerate(lines2, start=1) if
                       line}
            for future in tqdm(as_completed(futures), total=len(futures)):
                num = futures[future]
                files += f"file {save_path}/{num}.wav\n"
        files = ""
        for num in range(1,len(lines2)+1):
            files += f"file {save_path}/{num}.wav\n"
        with open('file_list.txt', 'w', encoding='utf8') as e:
            e.write(files)

    else:
        for i in lines2:
            print(i)
def combine(filename):
    # ap、合并
    if debug_:
        return
    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(os.path.join('AP_BWE',filename)):
        os.remove(os.path.join('AP_BWE',filename))
    absolute_path = os.path.abspath(save_path)
    process = subprocess.Popen(['python', 'inference_48k.py', '--checkpoint_file', './checkpoints/16kto48k/g_16kto48k', '--output_dir', save_path, '--input_wavs_dir',absolute_path]
                               ,cwd='./AP_BWE')
    return_code = process.wait()
    if return_code != 0:
        print("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        print("Error:", stderr)
    # 未超分
    process = subprocess.Popen(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', '[未超分]'+filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return_code = process.wait()
    if return_code != 0:
        print("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        print("Error:", stderr)
    else:
        print("Subprocess completed successfully.")
        # os.startfile(filename)
        print('已经完成未超分音频合成。')
    # 已超分
    shutil.copy('file_list.txt',os.path.join('AP_BWE','file_list.txt'))
    process = subprocess.Popen(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', '../[已超分]'+filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,cwd='./AP_BWE')
    return_code = process.wait()
    if return_code != 0:
        print("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        print("Error:", stderr)
    else:
        print("Subprocess completed successfully.")
        # os.startfile(filename)
        print('已经完成超分音频合成。')
def combine_without_ap(filename):
    # 只用于合成
    process = subprocess.Popen(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return_code = process.wait()
    if return_code != 0:
        print("Subprocess failed with return code:", return_code)
        stderr = process.stderr.read().decode('utf-8')
        print("Error:", stderr)
    else:
        print("Subprocess completed successfully.")
        # os.startfile(filename)
        print('已经完成音频合成。')

def read_txt_check_one_by_one(path: str, start_num:int,debug=False):
    # 读取文件、分词、分段合成。一个一个合成，每次合成后自动播放，用户自行评价是否重新合成。从start_num开始。
    if not os.path.exists(path):
        print("文件不存在")
        return
    with open(path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    lines2 = []
    if debug:
        from pprint import pp
        pp(lines)

    for line in lines:
        line = line.strip()
        if line == "":
            continue
        delimiters = r'[\。\，\、\；\：\？\！\……]'
        sentences = re.split(delimiters, line)
        cache = ''
        se2 = []
        for sen in sentences:
            s2 = sen.strip()
            if s2 == '':
                continue
            if len(s2) <= 10:
                cache += s2 + '，'
            else:
                se2.append('  '+ cache+s2)
                cache = ''
        if cache:
            se2.append('  '+cache.strip('，')) # 前面加空格是为了防止之后连接不太流畅。
        lines2 += se2

    print(f'切分为了{len(lines2)}段。')
    if len(lines2)<start_num:
        print("start_num超过长度")
        return
    if not debug:
        for num, line in enumerate(lines2, start=1):
            line = line.strip()
            if num < start_num:
                continue
            if line:
                while True:
                    if using_fast_api:
                        make_wav_v2(line, f"{num}.wav")
                    else:
                        make_wav(line, f"{num}.wav")
                    print(f'正在播放第{num}段：{line}')
                    destination_file = os.path.join(save_path, f"{num}.wav")
                    os.startfile(destination_file)
                    a = input('接受?[y|n]')
                    if a == 'y':
                        break
                    elif a == 'n':
                        continue

        files = ""
        for num in range(1,len(lines2)+1):
            files += f"file {save_path}/{num}.wav\n"
        with open('file_list.txt', 'w', encoding='utf8') as e:
            e.write(files)

    else:
        for i in lines2:
            print(i)
def get_txt_and_made_at_once(path: str, debug=False):
    # 一次性读取文本然后一次生成，无分段无ap
    with open(path, 'r', encoding='utf-8') as e:
        data = e.read()
    if not debug:
        output_wav_file = 'cache.wav'
        make_wav(data, output_wav_file)
# read_txt(read_txt_file,debug_)
read_txt_check_one_by_one(read_txt_file,start_num=24,debug=debug_)
# combine_without_ap(output_wav_file)
# get_txt_and_made_at_once(read_txt_file,debug_)