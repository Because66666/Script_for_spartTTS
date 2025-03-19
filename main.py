import re
from gradio_client import Client, file
import shutil
import os
from tqdm import tqdm
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import *

if not os.path.exists(save_path):
    os.makedirs(save_path)



def make_wav(msg: str, filename: str):
    global client
    source_file = client.predict(
        text=msg,
        prompt_text="",
        prompt_wav_upload=file(used_voices),
        prompt_wav_record=None,
        api_name="/voice_clone"
    )
    destination_file = os.path.join(save_path, filename)
    shutil.copyfile(source_file, destination_file)


def read_txt(path: str, debug=False):
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

client = Client("http://127.0.0.1:7860/")
read_txt(read_txt_file,debug_)
combine(output_wav_file)
