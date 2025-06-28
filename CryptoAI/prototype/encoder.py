from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
import os
import sys
import hashlib

def get_key():    
    with open("key.pem", "rb") as f:
        key = serialization.load_pem_private_key(
            f.read(),
            password=None  # или b"my_password", если ключ зашифрован
        )
    return key

def encrypt_rsa(plaintext: bytes, public_key):
    ciphertext = public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return ciphertext

if __name__ == "__main__":
    file_in = sys.argv[1]
    file_out = sys.argv[2].split(';')
    key = hashlib.sha256(os.urandom(8)).digest()
    rsa_key = get_key()
    encoded_key = encrypt_rsa(key, rsa_key.public_key())
    nonce = os.urandom(16)
    encoded = bytes()
    
    
    encryptor = Cipher(
        algorithms.AES(key),
        modes.CTR(nonce),
        backend=default_backend()
    ).encryptor()
    
    with open(file_in, 'rb') as f:
        chunk = f.read(512)
        while len(chunk) != 0:
            encoded += encryptor.update(chunk)
            chunk = f.read(512)
        encoded += encryptor.finalize()
    
    with open(file_out[0], 'wb') as f:
        f.write(nonce)
        f.write(encoded_key)
        f.write(encoded)
    
    
    encryptor = Cipher(
        algorithms.ChaCha20(key, nonce),
        None,
        backend=default_backend()
    ).encryptor()
    
    with open(file_in, 'rb') as f:
        chunk = f.read(512)
        while len(chunk) != 0:
            encoded += encryptor.update(chunk)
            chunk = f.read(512)
        encoded += encryptor.finalize()
    
    with open(file_out[0], 'wb') as f:
        f.write(nonce)
        f.write(encoded_key)
        f.write(encoded)
    