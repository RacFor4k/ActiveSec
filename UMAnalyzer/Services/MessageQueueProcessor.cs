using System;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using UMAnalyzer.Models;

namespace UMAnalyzer.Services
{
    /// <summary>
    /// Очередь для приёма и обработки сообщений.
    /// Если обработка предыдущего сообщения ещё не завершена — новые ждут в очереди.
    /// </summary>
    public class MessageQueueProcessor
    {
        private readonly Channel<KM_Message> _channel;

        public MessageQueueProcessor()
        {
            _channel = Channel.CreateUnbounded<KM_Message>(new UnboundedChannelOptions
            {
                SingleReader = true,
                SingleWriter = false
            });
        }

        /// <summary>
        /// Помещает сообщение в очередь.
        /// </summary>
        public void Enqueue(KM_Message message)
        {
            if (!_channel.Writer.TryWrite(message))
                Console.WriteLine("⚠ Не удалось поместить сообщение в очередь");
        }

        /// <summary>
        /// Асинхронный обработчик очереди сообщений.
        /// </summary>
        public async Task StartProcessingAsync(CancellationToken token)
        {
            await foreach (var message in _channel.Reader.ReadAllAsync(token))
            {
                try
                {
                    Console.WriteLine($"📨 Получено сообщение: {message}");
                    await ProcessMessageAsync(message, token);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"❌ Ошибка обработки: {ex}");
                }
            }
        }

        /// <summary>
        /// Логика обработки одного сообщения (демо — задержка 2 секунды).
        /// </summary>
        private async Task ProcessMessageAsync(KM_Message message, CancellationToken token)
        {
            // Здесь может быть любая бизнес-логика
            await Task.Delay(TimeSpan.FromSeconds(2), token);
            Console.WriteLine($"✅ Сообщение обработано: {message}");
        }
    }
}
