import torch
import socket
from collections import Counter
from ai import ByteClassifier as NN  # импортируем ту же модель
import sys
import os

def predict_file(data, model):
    with torch.no_grad():
        X = torch.tensor(data, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        outputs = model(X.to(device))
        ratio = torch.argmax(outputs, 1)
        if ratio == 1:
            return '1'
        else:
            return '0'



if __name__ == "__main__":
    if len(sys.argv) < 2:
       sys.exit(1)
    
    model_path = sys.argv[1]

    if not (os.path.exists(model_path) or os.path.exists(model_path)):
        sys.exit(1)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = NN(2).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv_sock.bind(('', 9348))
    serv_sock.listen(1)
    conn, addr = serv_sock.accept()

    while True:
        data = conn.recv(256)
        if not data:
            break
        conn.send(predict_file(data, model).encode())

    conn.close()