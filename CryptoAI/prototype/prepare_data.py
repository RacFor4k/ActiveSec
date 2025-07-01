import os
import subprocess
import sys
from multiprocessing import Pool

MAX_LEN = 10*1024

folders = [
    'prepared',
    'prepared\\normal',
    'prepared\\AES',
    'prepared\\ChaCha20'
]
def f(file):
    copy(file)
    encode(file)

def copy(file):
    file = os.path.join(sys.argv[1], file)
    with open(file, 'rb') as s:
        with open(f'prepared\\normal\\{os.path.basename(file)}', 'wb') as f:
            f.write(s.read(MAX_LEN))
            
def encode(file):
    args = [os.path.abspath(f'prepared\\normal\\{file}'), f'{os.path.abspath(f'prepared\\AES\\{file}')};{os.path.abspath(f'prepared\\ChaCha20\\{file}')}']
    subprocess.run(['python', 'CryptoAI\\prototype\\encoder.py']+args)
        

if __name__ == '__main__':
    source = sys.argv[1]
    #act = int(sys.argv[2])
    for folder in folders:
        if not os.path.exists(folder):
            os.mkdir(folder)
    with Pool(100) as pool:
        pool.map(f, os.listdir(source))
        

