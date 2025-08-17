using System;
using System.Threading;
using System.Threading.Tasks;
using UMAnalyzer.Models;
using UMAnalyzer.Services;

namespace UMAnalyzer
{
    internal class Program
    {
        static async Task Main()
        {
            unsafe
            {
                Console.WriteLine($"KM_Message size: {sizeof(KM_Message)}");
            }

            Console.WriteLine("🚀 Запуск клиента MiniFilter...");
            using var cts = new CancellationTokenSource();

            Console.CancelKeyPress += (s, e) =>
            {
                Console.WriteLine("⏹ Остановка...");
                cts.Cancel();
                e.Cancel = true;
            };

            var portClient = new Communication();
            var processor = new MessageProcessor();

            try
            {
                await portClient.ConnectAsync(cts.Token);
                Console.WriteLine("✅ Подключение к порту установлено");

                // Запускаем обработку очереди в фоне
                var processingTask = processor.StartProcessingAsync(cts.Token);

                // Читаем и ставим в очередь
                while (!cts.Token.IsCancellationRequested)
                {
                    var msg = await portClient.ReadMessageAsync(cts.Token);
                    if (msg.HasValue)
                        processor.Enqueue(msg.Value);
                }

                await processingTask;
            }
            catch (OperationCanceledException)
            {
                // Нормальное завершение
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Ошибка: {ex}");
            }
        }
    }
}
