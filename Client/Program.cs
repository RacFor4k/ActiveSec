using System;
using Client.Core;
using Client.IO;

namespace DriverClient
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("=== ActiveSec User Mode Client ===");

            // 1. Инициализация Shared Memory (должна быть создана драйвером)
            try
            {
                SharedMemoryManager.Initialize();
            }
            catch (Exception)
            {
                Console.WriteLine("Critical: Driver probably not loaded. Exiting.");
                return;
            }

            // 2. Подготовка инфраструктуры
            var queue = new ProcessingQueue();
            var connector = new DriverConnector(queue);
            var worker = new Worker(queue, connector);

            // 3. Запуск воркера
            worker.Start();

            // 4. Подключение к драйверу
            if (!connector.ConnectAndAuthorize())
            {
                Console.WriteLine("Critical: Failed to connect/authorize.");
                worker.Stop();
                SharedMemoryManager.Dispose();
                return;
            }

            Console.WriteLine("Press ENTER to exit...");
            Console.ReadLine();

            // 5. Завершение
            connector.Dispose();
            worker.Stop();
            SharedMemoryManager.Dispose();
        }
    }
}