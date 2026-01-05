"""
Docstring for train.data.prepare

markup:
    0 - don't encoded files
    1 - encoded files

    first line - addintional meta data
"""
import torch
import numpy as np
from typing import List
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.backends import default_backend
import os
import random
import tqdm

class CryptoAnalysis:
    """
    Класс для алгоритмического и математического определения шифрования в бинарных данных
    """
    
    @staticmethod
    def calculate_entropy(data: torch.Tensor) -> torch.Tensor:
        """
        Вычисляет энтропию Шеннона для бинарных данных
        :param data: torch.Tensor с байтами (значения от 0 до 255)
        :return: torch.Tensor с значением энтропии.
        """
        # Подсчет частот байтов
        counts = torch.bincount(data.flatten().long(), minlength=256)
        probabilities = counts.float() / data.numel()
        
        # Убираем нулевые вероятности для избежания log(0)
        probabilities = probabilities[probabilities > 0]
        
        # Вычисление энтропии Шеннона
        entropy = -torch.sum(probabilities * torch.log2(probabilities))
        return entropy
    
    @staticmethod
    def calculate_chi_square(data: torch.Tensor) -> torch.Tensor:
        """
        Вычисляет статистику хи-квадрат для проверки равномерности распределения
        :param data: torch.Tensor с байтами
        :return: torch.Tensor со значением хи-квадрат
        """
        counts = torch.bincount(data.flatten().long(), minlength=256)
        expected = data.numel() / 256.0
        chi_square = torch.sum((counts.float() - expected) ** 2 / expected)
        return chi_square
    
class FileOperations:
    """
    Класс для операций с файлами
    """
    
    @staticmethod
    def read_binary_file(file_path: str) -> torch.Tensor:
        """
        Читает бинарный файл и возвращает его содержимое в виде torch.Tensor
        :param file_path: путь к бинарному файлу
        :return: torch.Tensor с байтами файла
        """
        with open(file_path, 'rb') as f:
            byte_data = f.read()
        byte_array = np.frombuffer(byte_data, dtype=np.uint8)
        return torch.from_numpy(byte_array.copy())
    
    @staticmethod
    def write_binary_file(file_path: str, data: torch.Tensor):
        """
        Записывает данные в бинарный файл
        :param file_path: путь к бинарному файлу
        :param data: torch.Tensor с байтами для записи
        """
        byte_data = data.cpu().numpy().copy().astype(np.uint8).tobytes()
        with open(file_path, 'ba') as f:
            f.write(byte_data)

    @staticmethod
    def write_meta_in_file(file_path: str, meta_data: str):
        """
        Записывает метаданные в файл
        :param file_path: путь к файлу
        :param meta_data: строка с метаданными для записи
        """
        with open(file_path, 'w') as f:
            f.write(meta_data)

class DataEncoder:
    """
    Класс для кодирования и декодирования данных с метаданными

    :param algorithm: str - алгоритм кодирования (например, "aes", "self", "xor")

    """
    def __init__(self, algorithm: str) -> None:
        if algorithm == "aes":
            self._encode_func = self._encode_aes
            self._decode_func = self._decode_aes
        elif algorithm == "self":
            # Алгоритм "self" - данные не изменяются
            self._encode_func = self._encode_self
            self._decode_func = self._decode_self
        elif algorithm == "xor":
            self._encode_func = self._encode_xor
            self._decode_func = self._decode_xor
        else:
            raise ValueError(f"Неизвестный алгоритм: {algorithm}")


    def encode_data(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Кодирует данные в соответствии с выбранным алгоритмом.
        """
        return self._encode_func(data, key)


    def decode_data(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Декодирует данные в соответствии с выбранным алгоритмом.
        """
        return self._decode_func(data, key)


    def _encode_self(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для кодирования данных с алгоритмом "self".
        Возвращает данные без изменений.
        """
        # Возвращаем данные как есть
        return data


    def _decode_self(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для декодирования данных с алгоритмом "self".
        Возвращает данные без изменений.
        """
        # Возвращаем данные как есть
        return data


    def _encode_aes(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для кодирования данных с AES.
        """
        # Генерация случайного IV
        iv = os.urandom(16)

        # Создание объекта шифрования
        cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Преобразование torch.Tensor в bytes
        data_bytes = data.cpu().numpy().astype(np.uint8).tobytes()

        # Выравнивание данных до кратности 16 байтам (размер блока AES)
        padding_length = 16 - (len(data_bytes) % 16)
        padded_data = data_bytes + bytes([padding_length] * padding_length)

        # Шифрование
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Объединение IV и зашифрованных данных
        result = iv + encrypted_data

        # Преобразование результата обратно в torch.Tensor
        result_array = np.frombuffer(result, dtype=np.uint8)
        return torch.from_numpy(result_array.copy())


    def _decode_aes(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для декодирования данных с AES.
        """
        # Извлечение IV из начала данных
        data_bytes = data.cpu().numpy().astype(np.uint8).tobytes()
        iv = data_bytes[:16]
        encrypted_data = data_bytes[16:]

        # Создание объекта дешифрования
        cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Дешифрование
        padded_decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Удаление выравнивания
        padding_length = padded_decrypted_data[-1]
        decrypted_data = padded_decrypted_data[:-padding_length]

        # Преобразование результата обратно в torch.Tensor
        result_array = np.frombuffer(decrypted_data, dtype=np.uint8)
        return torch.from_numpy(result_array.copy())


    def _encode_xor(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для кодирования данных с XOR.
        """
        # Преобразование torch.Tensor в numpy массив
        data_np = data.cpu().numpy()

        # Повторение ключа до размера данных
        key_repeated = np.resize(np.frombuffer(key, dtype=np.uint8), data_np.shape)

        # Применение XOR
        result_np = np.bitwise_xor(data_np, key_repeated)

        # Преобразование результата обратно в torch.Tensor
        return torch.from_numpy(result_np.copy())


    def _decode_xor(self, data: torch.Tensor, key: bytes) -> torch.Tensor:
        """
        Приватный метод для декодирования данных с XOR.
        """
        # Для XOR операция кодирования и декодирования одинакова
        return self._encode_xor(data, key)

if __name__ == "__main__":
    RANDOM = random.Random(42)
    RAW_DATA = r"train\data\raw"
    MARKUP_PATH = r"train\data\markup"
    raw_files = os.listdir(RAW_DATA)
    encoder = DataEncoder(algorithm="aes")

    for i, file in tqdm.tqdm(enumerate(raw_files)):
        data = FileOperations.read_binary_file(os.path.join(RAW_DATA, file))
        chi2 = CryptoAnalysis.calculate_chi_square(data)
        FileOperations.write_meta_in_file(os.path.join(MARKUP_PATH,'0', f'{i}.bin'), str(chi2.item()))
        FileOperations.write_binary_file(os.path.join(MARKUP_PATH, '0', f'{i}.bin'), data)

        key = os.urandom(16)
        data = encoder.encode_data(data, key)
        chi2 = CryptoAnalysis.calculate_chi_square(data)
        FileOperations.write_meta_in_file(os.path.join(MARKUP_PATH,'1', f'{i}.bin'), str(chi2.item()))
        FileOperations.write_binary_file(os.path.join(MARKUP_PATH, '1', f'{i}.bin'), data)

