using Client.Native;
using System;
using System.Collections.Generic;
using System.IO.MemoryMappedFiles;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Client.IO
{
    public static class SharedMemoryManager
    {
        private static MemoryMappedFile _nmf;
        private static MemoryMappedViewAccessor _accessor;

        public static void Initialize()
        {
            try
            {
                _nmf = MemoryMappedFile.OpenExisting(Constants.SharedMemName, MemoryMappedFileRights.Read);
                _accessor = _nmf.CreateViewAccessor(0, Constants.SharedMemSize, MemoryMappedFileAccess.Read);
#if DEBUG
                Console.WriteLine("[IO] Shared memory mapped successfully.");
#endif
            }
            catch (Exception ex)
            {
#if DEBUG
                Console.WriteLine($"[IO] Failed to map shared memory: {ex.Message}");
#endif
                throw;
            }
        }

        public static byte[] ReadChunk(int length)
        {
            if(_accessor == null)
            {
                throw new InvalidOperationException("Shared memory not initialized.");
            }
            if(length <= 0 || length > Constants.SharedMemSize)
            {
                throw new ArgumentOutOfRangeException(nameof(length), "Length must be positive and less than the size of the shared memory.");
            }

            byte[] buffer = new byte[length];
            _accessor.ReadArray(0, buffer, 0, length);
            return buffer;
        }

        public static void Dispose()
        {
            _accessor?.Dispose();
            _nmf?.Dispose();
        }
    }
}
