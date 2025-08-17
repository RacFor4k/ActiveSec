using System;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using UMAnalyzer.Models;

namespace UMAnalyzer.Services
{
    public class MessageProcessor : IDisposable
    {
        private readonly Channel<KM_Message> _channel;
        private readonly CancellationTokenSource _cts;
        private readonly Task _processingTask;

        public MessageProcessor()
        {
            // Канал с неограниченной емкостью
            _channel = Channel.CreateUnbounded<KM_Message>(new UnboundedChannelOptions
            {
                SingleReader = true,   // один поток обработки
                SingleWriter = false   // несколько потоков могут писать
            });

            _cts = new CancellationTokenSource();
            _processingTask = Task.Run(ProcessMessagesAsync);
        }

        // Метод для добавления сообщения в очередь
        public async Task EnqueueMessageAsync(KM_Message message)
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
        private void HandleMessage(KM_Message message)
        {
            // TODO: Реализовать логику обработки
            Console.WriteLine($"Обрабатываем сообщение: {message}");
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
            _cts.Cancel();
            _channel.Writer.Complete();
            _processingTask.Wait();
            _cts.Dispose();
        }
    }
}
