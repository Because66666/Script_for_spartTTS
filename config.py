save_path = "./输出的语音" # 切分后，合成的语音文件路径，临时保存
used_voices = './收集的语音/旅行者-荧-正常.wav' # 使用的参考音频路径
read_txt_file='文本.txt' # 输入的文本路径
output_wav_file='naxida-output.wav' # 最后保存的音频文件路径。
debug_=False # 是否进入调试模式
using_fast_api = False # 是否使用FastAPI?和Client("http://127.0.0.1:7860/")二选一