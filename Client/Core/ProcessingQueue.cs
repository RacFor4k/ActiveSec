using Client.Native;
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Client.Core
{
    public class QueueItem
    {
        public DRIVER_MSG_HEADER Header { get; set; }
    }

    public class ProcessingQueue
    {
        private readonly BlockingCollection<QueueItem> _queue;

        public ProcessingQueue()
        {
            _queue = new BlockingCollection<QueueItem>(new ConcurrentQueue<QueueItem>());
        }

        public void Add(QueueItem item)
        {
            _queue.Add(item);
        }

        public QueueItem? Take(CancellationToken cancellationToken)
        {
            try
            {
                return _queue.Take(cancellationToken);
            }
            catch (OperationCanceledException)
            {
                return null;
            }
        }
    }
}
