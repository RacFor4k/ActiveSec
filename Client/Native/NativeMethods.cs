using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace Client.Native
{
    internal static class NativeMethods
    {
        // https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/filterconnectcommunicationport
        [DllImport("FltLib.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern int FilterConnectCommunicationPort(
            string lpPortName,
            uint dwOptions,
            IntPtr lpContext,
            uint dwSizeOfContext,
            IntPtr lpSecurityAttributes,
            out IntPtr hPort);

        // https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/filtersendmessage
        [DllImport("FltLib.dll", SetLastError = true)]
        public static extern int FilterSendMessage(
            IntPtr hPort,
            IntPtr lpInBuffer,
            uint dwInBufferSize,
            IntPtr lpOutBuffer,
            uint dwOutBufferSize,
            out uint lpBytesReturned);

        // https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/filtergetmessage
        [DllImport("FltLib.dll", SetLastError = true)]
        public static extern int FilterGetMessage(
            IntPtr hPort,
            IntPtr lpMessageBuffer,
            uint dwMessageBufferSize,
            out uint lpBytesReturned,
            IntPtr lpOverlapped);

        // https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/filterreplymessage
        [DllImport("FltLib.dll", SetLastError = true)]
        public static extern int FilterReplyMessage(
            IntPtr hPort,
            IntPtr lpReplyBuffer,
            uint dwReplyBufferSize);

        // https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle
        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool CloseHandle(IntPtr hObject);

        [StructLayout(LayoutKind.Sequential)]
        public struct FILTER_MESSAGE_HEADER{
            public uint ReplyLength;
            public ulong MessageId;
        }
}
}
