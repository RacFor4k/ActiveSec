using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using UMAnalyzer.Common;

namespace UMAnalyzer.Models
{
    [StructLayout(LayoutKind.Sequential)]
    public struct FILTER_MESSAGE_HEADER
    {
        public uint replyLength;
        public ulong messageId;
    }

    public unsafe struct Headed_KM_Message
    {
        public FILTER_MESSAGE_HEADER header;
        public KM_Message KM_Message;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1, CharSet = CharSet.Unicode)]
    public unsafe struct KM_Message
    {
        public uint Type;
        public fixed char ProcessPath[260]; // inline WCHAR[260]
        public fixed char FilePath[260]; // inline WCHAR[260]
        public uint Offset;
        public uint BufferLength;
        public fixed byte Buffer[ConstProvider.MaxLogWriteBufferLen]; // inline CHAR[]
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct UM_Message
    {
        public ulong Pid; // UINT64
        public uint Type; // ULONG
    }
}
