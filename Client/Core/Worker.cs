using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Client.Core
{
    public class Worker(ProcessingQueue queue, DriverConnector connector)
    {
        private readonly ProcessingQueue _queue = queue;
        private readonly DriverConnector _connector = connector;
        private Thread _workerThread;
        private CancellationTokenSource _cts = new CancellationTokenSource();

        public void Start()
        {
            _workerThread = new Thread(ProcessLoop)
            {
                IsBackground = true,
                Name = "DataWorkerThread"
            };
            _workerThread.Start();
        }

        public void Stop()
        {
            _cts.Cancel();
            _workerThread.Join();
        }

        private void ProcessLoop()
        {
#if DEBUG
            Console.WriteLine("[Worker] Worker thread started.");
#endif
            while (!_cts.Token.IsCancellationRequested)
            {
                var item = _queue.Take(_cts.Token);
                if (item != null)
                {
                    try
                    {
                        if (item.Header.Type == 2) // DataReady
                        {
#if DEBUG
                            Console.WriteLine($"[Worker] Processing DataReady message of size {item.Header.DataSize}, Chunk: {(item.Header.TotalSize + item.Header.CurrentOffset - 1) / item.Header.CurrentOffset}");
#endif
                            byte[] data = IO.SharedMemoryManager.ReadChunk((int)item.Header.DataSize);

                            // Process data 

                            _connector.SendSignalAck();
                        }
                        else if (item.Header.Type == 1) // Common message
                        {

                        }
                    }
                    catch (Exception ex)
                    {
#if DEBUG
                        Console.WriteLine($"[Worker] Error processing message: {ex.Message}");
#endif
                    }
                }
            }
        }
    }
}
