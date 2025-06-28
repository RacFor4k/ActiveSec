from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

def generate_rsa_keys():
    # Генерируем пару ключей
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048  # Можно 3072 или 4096 для большей безопасности
    )
    public_key = private_key.public_key()
    return private_key, public_key

key, _ = generate_rsa_keys()

with open("key.pem", "wb") as f:
    f.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,  # универсальный формат
            encryption_algorithm=serialization.NoEncryption()
        )
    )