using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using UMAnalyzer.Common;
using UMAnalyzer.Models;

namespace UMAnalyzer.Services
{
    public class Communication : IDisposable
    {
        private const string PortName = ConstProvider.PortName; // "\\ActiveSec"
        private IntPtr _portHandle = IntPtr.Zero;

        public async Task ConnectAsync(CancellationToken token)
        {
            uint status = FilterConnectCommunicationPort(
                PortName,
                0,
                IntPtr.Zero,
                0,
                IntPtr.Zero,
                out _portHandle);

            if (status != 0 || _portHandle == IntPtr.Zero)
            {
                throw new InvalidOperationException($"Не удалось подключиться к {PortName}. NTSTATUS=0x{status:X8}");
            }

            await Task.CompletedTask;
        }

        /// <summary>
        /// Асинхронное чтение одного сообщения из порта
        /// </summary>
        public Task<safe_KM_Message?> ReadMessageAsync(CancellationToken token)
        {
            if (_portHandle == IntPtr.Zero)
                throw new InvalidOperationException("Подключение не установлено");

            unsafe
            {
                int size = sizeof(Headed_KM_Message);
                IntPtr buffer = Marshal.AllocHGlobal(size);
                try
                {
                    uint status = FilterGetMessage(_portHandle, buffer, (uint)size, IntPtr.Zero);
                    if (status == 0) // STATUS_SUCCESS
                    {
                        // Работаем с сырым указателем на полученный буфер — не создаём промежуточную управляемую копию.
                        Headed_KM_Message* pHead = (Headed_KM_Message*)buffer.ToPointer();
                        KM_Message* pMsg = &pHead->KM_Message;

                        var safe = new safe_KM_Message
                        {
                            Pid = pMsg->Pid,
                            Type = pMsg->Type,
                            Offset = pMsg->Offset,
                            BufferLength = pMsg->BufferLength
                        };

                        // FilePath: fixed WCHAR[260] -> string
                        // у нас есть char*, потому можно прямо создать string
                        char* pFile = pMsg->FilePath;
                        safe.FilePath = new string(pFile); // читается до первого '\0'

                        // Buffer: скопировать BufferLength байт из inline-буфера
                        uint copyLen = pMsg->BufferLength;
                        // защита от неверных значений (опционально)
                        uint maxLen = ConstProvider.MaxLogWriteBufferLen;
                        if (copyLen > maxLen) copyLen = maxLen;

                        if (copyLen > 0)
                        {
                            safe.Buffer = new byte[copyLen];
                            byte* pBuf = pMsg->Buffer;
                            Marshal.Copy((IntPtr)pBuf, safe.Buffer, 0, (int)copyLen);
                        }
                        else
                        {
                            safe.Buffer = Array.Empty<byte>();
                        }

                        return Task.FromResult<safe_KM_Message?>(safe);
                    }
                    else if (status == 0xC0000023) // STATUS_TIMEOUT
                    {
                        return Task.FromResult<safe_KM_Message?>(null);
                    }
                    else
                    {
                        throw new InvalidOperationException($"Ошибка чтения сообщения. NTSTATUS=0x{status:X8}");
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(buffer);
                }
            }
        }




        /// <summary>
        /// Отправка сообщения в KM
        /// </summary>
        public async Task SendMessageAsync(KM_Message message, CancellationToken token)
        {
            if (_portHandle == IntPtr.Zero)
                throw new InvalidOperationException("Подключение не установлено");

            uint status = FilterSendMessage(
                _portHandle,
                ref message,
                (uint)Marshal.SizeOf<KM_Message>(),
                IntPtr.Zero,
                0);

            if (status != 0)
            {
                throw new InvalidOperationException($"Ошибка отправки сообщения. NTSTATUS=0x{status:X8}");
            }
            await Task.CompletedTask;
        }

        public void Dispose()
        {
            if (_portHandle != IntPtr.Zero)
            {
                CloseHandle(_portHandle);
                _portHandle = IntPtr.Zero;
            }
        }

        #region PInvoke

        [DllImport("fltlib.dll", CharSet = CharSet.Unicode)]
        private static extern uint FilterConnectCommunicationPort(
            string lpPortName,
            uint dwOptions,
            IntPtr lpContext,
            uint dwSize,
            IntPtr lpSecurityAttributes,
            out IntPtr hPort
        );

        [DllImport("fltlib.dll", SetLastError = true)]
        private static extern uint FilterGetMessage(
            IntPtr hPort,
            IntPtr MessageBuffer,      // указатель на unmanaged память
            uint MessageBufferSize,
            IntPtr lpOverlapped
        );


        [DllImport("fltlib.dll")]
        private static extern uint FilterSendMessage(
            IntPtr hPort,
            ref KM_Message MessageBuffer,
            uint MessageBufferSize,
            IntPtr ReplyBuffer,
            uint ReplyBufferSize
        );

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        #endregion
    }
}
