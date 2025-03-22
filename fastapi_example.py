import requests

# 定义 API 端点
voice_clone_url = "http://localhost:8000/voice_clone"

# 定义请求数据
data = {
    "text": "这是一段测试文本",
    "prompt_text": "提示文本示例",
    "prompt_speech": "path/to/prompt_audio.wav"  # 替换为实际的提示音频文件路径
}

# 发送 POST 请求
response = requests.post(voice_clone_url, json=data)

# 检查响应状态
if response.status_code == 200:
    result = response.json()
    print("语音克隆成功，音频文件路径为:", result["audio_path"])
else:
    print("语音克隆失败，错误信息:", response.text)


import requests

# 定义 API 端点
voice_creation_url = "http://localhost:8000/voice_creation"

# 定义请求数据
data = {
    "text": "这是一段用于语音生成的测试文本",
    "gender": "male",
    "pitch": 3,
    "speed": 3
}

# 发送 POST 请求
response = requests.post(voice_creation_url, json=data)

# 检查响应状态
if response.status_code == 200:
    result = response.json()
    print("语音生成成功，音频文件路径为:", result["audio_path"])
else:
    print("语音生成失败，错误信息:", response.text)
