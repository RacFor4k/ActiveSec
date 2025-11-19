import struct
import math
from tqdm import tqdm
from collections import Counter, defaultdict

INPUT_FILE = "log.bin"
MAIN_FILE = "main.bin"

HEADER_SIZE = 540  # pid (8) + type (4) + filepath (520) + offset (4) + buflen (4)


def parse_messages(filename):
    messages = []
    with open(filename, "rb") as f:
        while True:
            header = f.read(HEADER_SIZE)
            if not header:
                break
            if len(header) < HEADER_SIZE:
                # частичный заголовок — конец файла с ошибкой
                print("Обнаружен неполный заголовок, завершение чтения")
                break

            pid, mtype = struct.unpack_from("<Q I", header, 0)
            raw_path = header[12:12 + 520]
            filepath = raw_path.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
            offset, buflen = struct.unpack_from("<II", header, 532)

            # проверяем, что доступно достаточно данных для буфера
            buf = f.read(buflen)
            if len(buf) < buflen:
                print(f"Обнаружен неполный буфер для PID {pid}, пропуск сообщения")
                break  # прекращаем чтение, чтобы не обрабатывать испорченное сообщение

            messages.append({
                "pid": pid,
                "type": mtype,
                "filepath": filepath,
                "offset": offset,
                "buflen": buflen,
                "buffer": buf
            })
    return messages


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def main():
    messages = parse_messages(INPUT_FILE)

    # ищем PID с наибольшей активностью по "*\Новая папка\normal"
    counts = defaultdict(int)
    for m in messages:
        if "Новая папка\\normal" in m["filepath"]:
            counts[m["pid"]] += 1

    main_pid = max(counts, key=counts.get) if counts else None
    if main_pid:
        print(f"Главный PID: {main_pid}")
    else:
        print("Нет главного PID. Все сообщения будут писаться по отдельным PID-файлам.")

    files = {}
    total_entropy = 0.0
    count_entropy = 0

    try:
        for m in tqdm(messages, desc="Запись по PID"):
            record = struct.pack("<I I I", m["type"], m["offset"], m["buflen"]) + m["buffer"]

            if main_pid and m["pid"] == main_pid:
                fname = MAIN_FILE
                if fname not in files:
                    files[fname] = open(fname, "ab")
                files[fname].write(record)

                if m["buffer"]:
                    total_entropy += shannon_entropy(m["buffer"])
                    count_entropy += 1
            else:
                fname = f"pid_{m['pid']}.bin"
                if fname not in files:
                    files[fname] = open(fname, "ab")
                files[fname].write(record)

    finally:
        for f in files.values():
            f.close()

    if main_pid and count_entropy > 0:
        avg_entropy = total_entropy / count_entropy
        print(f"Средняя энтропия для PID {main_pid}: {avg_entropy:.4f} бит/байт")
    elif main_pid:
        print(f"У главного PID {main_pid} нет данных для расчета энтропии")


if __name__ == "__main__":
    main()
