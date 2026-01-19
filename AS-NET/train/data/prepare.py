"""
Docstring for train.data.prepare

markup:
    0 - don't encoded files
    1 - encoded files

    first 8 bytes - chi2 value as binary float64
"""

import numpy as np
from typing import List
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.backends import default_backend
import os
import struct


class CryptoAnalysis:
    """
    Класс для алгоритмического и математического определения шифрования в бинарных данных
    """

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """
        Вычисляет энтропию Шеннона для бинарных данных
        :param data: bytes с байтами
        :return: значение энтропии
        """
        # Подсчет частот байтов
        counts = [0] * 256
        for byte in data:
            counts[byte] += 1
        
        # Вычисление вероятностей
        total = len(data)
        if total == 0:
            return 0.0
        
        probabilities = [count / total for count in counts if count > 0]
        
        # Вычисление энтропии Шеннона
        entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)
        return entropy

    @staticmethod
    def calculate_chi_square(data: bytes) -> float:
        """
        Вычисляет статистику хи-квадрат для проверки равномерности распределения
        :param data: bytes с байтами
        :return: значение хи-квадрат
        """
        counts = [0] * 256
        for byte in data:
            counts[byte] += 1
        
        expected = len(data) / 256.0
        chi_square = sum((count - expected) ** 2 / expected for count in counts if expected != 0)
        return chi_square

    @staticmethod
    def calculate_autocorrelation(data: bytes, max_lag: int = 100) -> float:
        """
        Вычисляет автокорреляцию для разных сдвигов
        :param data: bytes с байтами
        :param max_lag: максимальный сдвиг для анализа
        :return: среднее значение автокорреляции
        """
        if len(data) < 2:
            return 0.0
        
        data_float = [float(b) for b in data]
        correlations = []

        for lag in range(1, min(max_lag, len(data_float) // 2)):
            x1 = data_float[:-lag]
            x2 = data_float[lag:]

            # Нормализация
            x1_mean = sum(x1) / len(x1)
            x2_mean = sum(x2) / len(x2)
            x1_std = (sum((x - x1_mean) ** 2 for x in x1) / len(x1)) ** 0.5
            x2_std = (sum((x - x2_mean) ** 2 for x in x2) / len(x2)) ** 0.5

            if x1_std == 0 or x2_std == 0:
                continue

            correlation = sum((a - x1_mean) * (b - x2_mean) for a, b in zip(x1, x2)) / (len(x1) * x1_std * x2_std)
            correlations.append(correlation)

        if correlations:
            return sum(correlations) / len(correlations)
        else:
            return 0.0

    @staticmethod
    def calculate_block_entropy(data: bytes, block_size: int = 1024) -> float:
        """
        Вычисляет энтропию для блоков данных и возвращает стандартное отклонение
        :param data: bytes с байтами
        :param block_size: размер блока для анализа
        :return: стандартное отклонение энтропии блоков
        """
        if len(data) < block_size:
            return CryptoAnalysis.calculate_entropy(data)

        num_blocks = len(data) // block_size
        blocks = [data[i * block_size:(i + 1) * block_size] for i in range(num_blocks)]

        entropies = []
        for block in blocks:
            entropy = CryptoAnalysis.calculate_entropy(block)
            entropies.append(entropy)

        if len(entropies) > 1:
            mean_entropy = sum(entropies) / len(entropies)
            variance = sum((e - mean_entropy) ** 2 for e in entropies) / len(entropies)
            return variance ** 0.5
        else:
            return 0.0

    @staticmethod
    def calculate_bit_dispersion(data: bytes) -> float:
        """
        Вычисляет дисперсию битов в данных
        :param data: bytes с байтами
        :return: значение дисперсии битов
        """
        # Преобразование байтов в биты
        bits = []
        for byte in data:
            for j in range(8):
                bit = (byte >> (7 - j)) & 1
                bits.append(float(bit))

        # Вычисление дисперсии битов
        if not bits:
            return 0.0
        
        bit_mean = sum(bits) / len(bits)
        bit_variance = sum((bit - bit_mean) ** 2 for bit in bits) / len(bits)
        return bit_variance

    @staticmethod
    def calculate_runs_test(data: bytes) -> float:
        """
        Вычисляет количество серий (runs) в бинарной последовательности
        :param data: bytes с байтами
        :return: средняя длина серий
        """
        if not data:
            return 0.0
        
        # Преобразование в бинарную последовательность (биты)
        bits = []
        for byte in data:
            for j in range(8):
                bit = (byte >> (7 - j)) & 1
                bits.append(bit)

        # Подсчет серий
        runs = []
        current_run = 1

        for i in range(1, len(bits)):
            if bits[i] == bits[i-1]:
                current_run += 1
            else:
                runs.append(current_run)
                current_run = 1
        runs.append(current_run)

        if runs:
            return sum(runs) / len(runs)
        else:
            return 0.0

    @staticmethod
    def calculate_differential_entropy(data: bytes) -> float:
        """
        Вычисляет дифференциальную энтропию (разность между соседними байтами)
        :param data: bytes с байтами
        :return: значение дифференциальной энтропии
        """
        if len(data) < 2:
            return 0.0

        # Вычисление разностей между соседними байтами
        diffs = [abs(data[i+1] - data[i]) for i in range(len(data)-1)]

        # Вычисление энтропии разностей
        return CryptoAnalysis.calculate_entropy(bytes(diffs))

    @staticmethod
    def calculate_compression_ratio(data: bytes) -> float:
        """
        Оценка степени сжатия (косвенный признак шифрования)
        :param data: bytes с байтами
        :return: оценка степени сжатия
        """
        # Используем простую оценку - количество уникальных байтов
        unique_count = len(set(data))

        # Чем ближе к 256, тем более случайные данные (возможно, зашифрованные)
        ratio = unique_count / 256.0
        return ratio


class FileOperations:
    """
    Класс для операций с файлами
    """

    @staticmethod
    def read_binary_file(file_path: str) -> bytes:
        """
        Читает бинарный файл и возвращает его содержимое в виде bytes
        :param file_path: путь к бинарному файлу
        :return: bytes с содержимым файла
        """
        with open(file_path, 'rb') as f:
            return f.read()

    @staticmethod
    def write_binary_file(file_path: str, data: bytes):
        """
        Записывает данные в бинарный файл
        :param file_path: путь к бинарному файлу
        :param data: bytes с данными для записи
        """
        with open(file_path, 'wb') as f:
            f.write(data)

    @staticmethod
    def write_meta_in_file(file_path: str, meta_data: str):
        """
        Записывает метаданные в файл
        :param file_path: путь к файлу
        :param meta_data: строка с метаданными для записи
        """
        with open(file_path, 'w') as f:
            f.write(meta_data)

    @staticmethod
    def write_binary_file_with_meta(file_path: str, data: bytes, meta_value: float):
        """
        Записывает данные в бинарный файл, добавляя значение метаданных в первые 8 байт
        :param file_path: путь к бинарному файлу
        :param data: bytes с данными для записи
        :param meta_value: значение метаданных (например, chi2) для записи в первые 8 байт
        """
        # Преобразование значения метаданных в 8 байт (float64)
        meta_bytes = struct.pack('d', meta_value)  # 'd' означает double (8 байт)
        
        # Запись метаданных и данных в файл
        with open(file_path, 'wb') as f:
            f.write(meta_bytes)
            f.write(data)


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

    def encode_data(self, data: bytes, key: bytes) -> bytes:
        """
        Кодирует данные в соответствии с выбранным алгоритмом.
        """
        return self._encode_func(data, key)

    def decode_data(self, data: bytes, key: bytes) -> bytes:
        """
        Декодирует данные в соответствии с выбранным алгоритмом.
        """
        return self._decode_func(data, key)

    def _encode_self(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для кодирования данных с алгоритмом "self".
        Возвращает данные без изменений.
        """
        # Возвращаем данные как есть
        return data

    def _decode_self(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для декодирования данных с алгоритмом "self".
        Возвращает данные без изменений.
        """
        # Возвращаем данные как есть
        return data

    def _encode_aes(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для кодирования данных с AES.
        """
        # Генерация случайного IV
        iv = os.urandom(16)
        
        # Создание объекта шифрования
        cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Выравнивание данных до кратности 16 байтам (размер блока AES)
        padded_data = data[:10224]
        
        # Шифрование
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Объединение IV и зашифрованных данных
        result = iv + encrypted_data
        
        return result

    def _decode_aes(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для декодирования данных с AES.
        """
        # Извлечение IV из начала данных
        iv = data[:16]
        encrypted_data = data[16:]
        
        # Создание объекта дешифрования
        cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # Дешифрование
        padded_decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Удаление выравнивания
        padding_length = padded_decrypted_data[-1]
        decrypted_data = padded_decrypted_data[:-padding_length]
        
        return decrypted_data

    def _encode_xor(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для кодирования данных с XOR.
        """
        # Повторение ключа до размера данных
        key_repeated = bytearray()
        for i in range(len(data)):
            key_repeated.append(key[i % len(key)])
        
        # Применение XOR
        result = bytearray()
        for i in range(len(data)):
            result.append(data[i] ^ key_repeated[i])
        
        return bytes(result)

    def _decode_xor(self, data: bytes, key: bytes) -> bytes:
        """
        Приватный метод для декодирования данных с XOR.
        """
        # Для XOR операция кодирования и декодирования одинакова
        return self._encode_xor(data, key)


if __name__ == "__main__":
    import tqdm
    import os
    import random
    
    RANDOM = random.Random(42)
    RAW_DATA = r"train\data\raw"
    MARKUP_PATH = r"train\data\markup"
    key = os.urandom(16)
    
    raw_files = os.listdir(RAW_DATA)
    encoder = DataEncoder("aes")

    label = []

    for i, file in enumerate(tqdm.tqdm(raw_files)):
        data = FileOperations.read_binary_file(os.path.join(RAW_DATA, file))
        chi2 = CryptoAnalysis.calculate_chi_square(data)
        FileOperations.write_binary_file_with_meta(os.path.join(MARKUP_PATH, f'{i*2}.bin'), data, chi2)
        label.append(f'{i*2}.bin 0\n')
        data = encoder.encode_data(data, key)
        chi2 = CryptoAnalysis.calculate_chi_square(data)
        FileOperations.write_binary_file_with_meta(os.path.join(MARKUP_PATH, f'{i*2+1}.bin'), data, chi2)
        label.append(f'{i*2+1}.bin 1\n')

    with open(os.path.join(MARKUP_PATH, 'label.txt'),'w') as file:
            file.writelines(label)