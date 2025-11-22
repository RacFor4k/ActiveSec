using Client.Native;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Client.Core
{
    public class DriverConnector : IDisposable
    {
        private IntPtr _hPort = IntPtr.Zero;
        private Thread _listenerThread;
        private bool _disposed;
        private readonly ProcessingQueue _queue;

        private const int MaxBufferSize = 4096;

        public DriverConnector(ProcessingQueue queue)
        {
            _queue = queue;
        }

        public bool ConnectAndAuthiorize()
        {
#if DEBUG
            Console.WriteLine("[DriverConnector] Connecting to driver...");
#endif
            int hr = Native.NativeMethods.FilterConnectCommunicationPort(
                Constants.PortName,
                0,
                IntPtr.Zero,
                0,
                IntPtr.Zero,
                out _hPort);

            if (hr != 0 || _hPort == IntPtr.Zero)
            {
#if DEBUG
                Console.WriteLine($"[DriverConnector] Failed to connect to driver. HRESULT: 0x{hr:X8}");
#endif
                return false;
            }

        }

    }
}
