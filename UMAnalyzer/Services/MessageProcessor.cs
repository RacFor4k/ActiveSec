using System;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using UMAnalyzer.Models;

namespace UMAnalyzer.Services
{
    public class MessageProcessor : IDisposable
    {
        private readonly Channel<safe_KM_Message> _channel;
        private readonly CancellationTokenSource _cts;
        private readonly Task _processingTask;
        private readonly FileStream _logStream;

        private static byte[] Serialize(safe_KM_Message msg)
        {
            using var ms = new MemoryStream();
            using var bw = new BinaryWriter(ms, Encoding.Unicode, true);

            // 1. Pid (8 байт)
            bw.Write(msg.Pid);

            // 2. Type (4 байта)
            bw.Write(msg.Type);

            // 3. FilePath (WCHAR[260], 520 байт)
            var filePath = msg.FilePath ?? string.Empty;
            if (filePath.Length > 259)
                filePath = filePath.Substring(0, 259); // оставляем место для \0

            // добавляем null-terminator
            filePath += '\0';

            // кодируем в UTF-16LE
            var encoded = Encoding.Unicode.GetBytes(filePath);

            // записываем и дополняем нулями до 520 байт
            bw.Write(encoded);
            if (encoded.Length < 520)
                bw.Write(new byte[520 - encoded.Length]);

            // 4. Offset (4 байта)
            bw.Write(msg.Offset);

            // 5. BufferLength (4 байта)
            bw.Write(msg.BufferLength);

            // 6. Buffer (ровно BufferLength байт)
            if (msg.Buffer != null && msg.Buffer.Length > 0)
            {
                bw.Write(msg.Buffer, 0, (int)msg.BufferLength);
            }

            bw.Flush();
            return ms.ToArray();
        }

        public MessageProcessor()
        {
            _logStream = File.OpenWrite("log.txt");
            // Канал с неограниченной емкостью
            _channel = Channel.CreateUnbounded<safe_KM_Message>(new UnboundedChannelOptions
            {
                SingleReader = true,   // один поток обработки
                SingleWriter = false   // несколько потоков могут писать
            });

            _cts = new CancellationTokenSource();
            _processingTask = Task.Run(ProcessMessagesAsync);
        }

        // Метод для добавления сообщения в очередь
        public async Task EnqueueMessageAsync(safe_KM_Message message)
        {
            await _channel.Writer.WriteAsync(message);
        }

        // Основной метод обработки сообщений
        private async Task ProcessMessagesAsync()
        {
            try
            {
                await foreach (var message in _channel.Reader.ReadAllAsync(_cts.Token))
                {
                    try
                    {
                        HandleMessage(message);
                    }
                    catch (Exception ex)
                    {
                        // Логирование или обработка ошибок
                        Console.WriteLine($"Ошибка обработки сообщения: {ex.Message}");
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Завершение при отмене
            }
        }

        // Пример метода обработки одного сообщения
        private void HandleMessage(safe_KM_Message message)
        {
            _logStream.Write(Serialize(message));
            _logStream.Flush();
            // TODO: Реализовать логику обработки
            Console.WriteLine($"Обрабатываем сообщение: {message.Buffer.Count()}");
        }

        // Остановка очереди и освобождение ресурсов
        public async Task StopAsync()
        {
            _cts.Cancel();
            _channel.Writer.Complete();
            await _processingTask;
        }

        public void Dispose()
        {
            _logStream.Dispose();
            _cts.Cancel();
            _channel.Writer.Complete();
            _processingTask.Wait();
            _cts.Dispose();
        }
    }
}
