using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Security.Cryptography;

namespace Client.Security
{
    public static class CryptoHelper
    {
        private const uint SaltMask = 0xC0000003;
        private static readonly Random _random = new Random();
        private static readonly byte[] _key = Convert.FromHexString("759ae9b3780b26a0b3b4370719b845f27c27cccfc9e0c83a15baeb01fa960eb6");

        private static bool GetBit(uint value, int bitIndex)
        {
            return ((value >> bitIndex) & 1) != 0;
        }

        public static uint ApplySalt(byte[] data)
        {
            uint salt = (uint)_random.Next();
            for (int i = 0; i < data.Length; i++)
            {
                if (GetBit(SaltMask, i % 32))
                {
                    data[i] = (byte)_random.Next(256);
                }
            }
            return salt;
        }

        //AES256 ECB Encryption
        public static byte[] Encrypt(byte[] data, byte[]? key = null)
        {
            if(key == null)
            {
                key = _key;
            }
            using (Aes aes = Aes.Create())
            {
                aes.KeySize = 256;
                aes.BlockSize = 128;
                aes.Key = key;
                aes.Mode = CipherMode.ECB;
                aes.Padding = PaddingMode.None;
                using (ICryptoTransform encryptor = aes.CreateEncryptor())
                {
                    return encryptor.TransformFinalBlock(data, 0, data.Length);
                }
            }
        }
    }
}
