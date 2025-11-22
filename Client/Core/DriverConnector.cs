using Client.Native;
using Client.Security;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace Client.Core
{
    public class DriverConnector(ProcessingQueue queue) : IDisposable
    {
        private IntPtr _hPort = IntPtr.Zero;
        private Thread _listenerThread;
        private bool _disposed;
        private readonly ProcessingQueue _queue = queue;
        private const int MaxBufferSize = 4096;

        public bool ConnectAndAuthorize()
        {
#if DEBUG
            Console.WriteLine("[DriverConnector] Connecting to driver...");
#endif
            int hr = NativeMethods.FilterConnectCommunicationPort(
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
#if DEBUG
            Console.WriteLine("[DriverConnector] Connected to driver.");
#endif
            try
            {
                byte[]? challengekey = RequestChallengeKey();
                if (challengekey == null) return false;
                CryptoHelper.ApplySalt(challengekey);
                byte[] token = CryptoHelper.Encrypt(challengekey);
                if (!SendAuthToken(token))
                {
#if DEBUG
                    Console.WriteLine("[DriverConnector] Authorization failed.");
#endif
                    return false;
                }
#if DEBUG
                Console.WriteLine("[DriverConnector] Authorized successfully.");
#endif
                _disposed = false;
                _listenerThread = new Thread(ListenerLoop);
                _listenerThread.Start();
                return true;
            }
            catch (Exception ex)
            {
#if DEBUG
                Console.WriteLine($"[DriverConnector] Exception during authorization: {ex.Message}");
#endif
                return false;
            }
        }

        private byte[]? RequestChallengeKey()
        {
            USER_MSG_HEADER request = new USER_MSG_HEADER
            {
                Command = CmdType.CmdType_GetKey
            };

            int requestSize = Marshal.SizeOf<USER_MSG_HEADER>();
            int outSize = Constants.KeyLength;

            IntPtr inPtr = Marshal.AllocHGlobal(requestSize);
            IntPtr outPtr = Marshal.AllocHGlobal(outSize);

            try
            {
                Marshal.StructureToPtr(request, inPtr, false);

                byte[] empty = new byte[outSize];
                Marshal.Copy(empty, 0, outPtr, outSize);

                uint bytesReturned = 0;
                int hr = NativeMethods.FilterSendMessage(
                    _hPort,
                    inPtr,
                    (uint)requestSize,
                    outPtr,
                    (uint)outSize,
                    out bytesReturned);

                if (hr != 0)
                {
#if DEBUG
                    Console.WriteLine($"[Comm] GetKey failed. HRESULT: 0x{hr:X}");
#endif
                    return null;
                }

                if (bytesReturned != outSize)
                {
#if DEBUG
                    Console.WriteLine($"[Comm] GetKey returned unexpected size: {bytesReturned}");
#endif
                    return null;
                }
                byte[] key = new byte[Constants.KeyLength];
                Marshal.Copy(outPtr, key, 0, Constants.KeyLength);
                return key;
            }
            finally
            {
                Marshal.FreeHGlobal(inPtr);
                Marshal.FreeHGlobal(outPtr);
            }
        }
        
        private bool SendAuthToken(byte[] token)
        {
            USER_MESSAGE_SET_KEY authMessage = new USER_MESSAGE_SET_KEY
            {
                Header = new USER_MSG_HEADER
                {
                    Command = CmdType.CmdType_Authorize
                },
                KeyMsg = new KEY_MSG
                {
                    Key = token
                }
            };
            int messageSize = Marshal.SizeOf<USER_MESSAGE_SET_KEY>();
            IntPtr messagePtr = Marshal.AllocHGlobal(messageSize);
            try
            {
                Marshal.StructureToPtr(authMessage, messagePtr, false);
                uint bytesReturned = 0;
                int hr = NativeMethods.FilterSendMessage(
                    _hPort,
                    messagePtr,
                    (uint)messageSize,
                    IntPtr.Zero,
                    0,
                    out bytesReturned);
                return hr == 0;
            }
            finally
            {
                Marshal.FreeHGlobal(messagePtr);
            }
        }

        public void SendSignalAck()
        {
            if (_hPort == IntPtr.Zero) return;

            USER_MSG_HEADER msg = new USER_MSG_HEADER { Command = CmdType.CmdType_SignalAck };

            int size = Marshal.SizeOf(msg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.StructureToPtr(msg, ptr, false);
                uint ret;
                NativeMethods.FilterSendMessage(_hPort, ptr, (uint)size, IntPtr.Zero, 0, out ret);
            }
            finally
            {
                Marshal.FreeHGlobal(ptr);
            }
        }

        private void ListenerLoop()
        {
            IntPtr buffer = Marshal.AllocHGlobal(MaxBufferSize);
            while (!_disposed)
            {
                int hr = NativeMethods.FilterGetMessage(
                    _hPort,
                    buffer,
                    (uint)MaxBufferSize,
                    out uint bytesReturned,
                    IntPtr.Zero);
                if (hr == 0)
                {
                    IntPtr dataPtr = IntPtr.Add(buffer, Marshal.SizeOf<NativeMethods.FILTER_MESSAGE_HEADER>());
                    DRIVER_MSG_HEADER header = Marshal.PtrToStructure<DRIVER_MSG_HEADER>(dataPtr);
                    _queue.Add(new QueueItem { Header = header });
                }
                else
                {
                    break;
                }
            }
            Marshal.FreeHGlobal(buffer);
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                _disposed = true;
                _listenerThread?.Join();
                if (_hPort != IntPtr.Zero)
                {
                    NativeMethods.CloseHandle(_hPort);
                    _hPort = IntPtr.Zero;
                }
            }
        }
    }
}
