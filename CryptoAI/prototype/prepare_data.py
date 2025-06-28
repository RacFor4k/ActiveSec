import os
import subprocess
import sys

MAX_LEN = 10*1024

if __name__ == '__main__':
    source = sys.argv[1]
    act = int(sys.argv[2])
    os.mkdir('prepared')
    os.mkdir('prepared\\normal')
    os.mkdir('prepared\\AES')
    os.mkdir('prepared\\ChaCha20')
    for file in os.listdir(source):
        if not os.path.isfile(file):
            continue
        if act == 1:
            with open(file, 'rb') as s:
                with open(f'prepared\\normal\\{os.path.basename(file)}', 'wb') as f:
                    f.write(s.read(MAX_LEN))
        else:
            args = [os.path.abspath(f'prepared\\normal\\{os.path.basename(file)}'), [os.path.abspath(f'prepared\\AES\\{os.path.basename(file)}'),os.path.abspath(f'prepared\\ChaCha20\\{os.path.basename(file)}')]]
            subprocess.run(['python', 'CryptoAI\\prototype\\encoder.py']+args)
        

