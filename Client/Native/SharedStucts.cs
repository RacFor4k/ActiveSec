using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace Client.Native
{
    public static class Constants
    {
        public const string PortName = "\\ActiveSecPort";
        public const string SharedMemName = "Global\\ActiveSecMem";
        public const int SharedMemSize = 16 * 1024 * 1024; //10 MB
        public const int KeyLength = 32;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct DRIVER_MSG_HEADER
    {
        public uint Type; // 1 - common; 2 - DataReady
        public uint DataSize;   
        public uint TotalSize;
        public uint CurrentOffset;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct USER_MSG_HEADER
    {
        public uint Command; // 1 - SignalAct
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct KEY_MSG
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = Constants.KeyLength)]
        public byte[] Key;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct USER_MESSAGE_SET_KEY
    {
        public USER_MSG_HEADER Header;
        public KEY_MSG KeyMsg;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct USER_MESSAGE_ACT
    {
        public USER_MSG_HEADER Header;
    }
}
