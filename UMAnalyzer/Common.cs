using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

//Все константы первоначально определены в common.h в проекте ActiveSec

namespace UMAnalyzer.Common
{
    static class ConstProvider
    {
        public const string PortName = @"\ActiveSec";
        public const int MaxLogWriteBufferLen = 10 * 1024;
        public const string ThreatsPath = @"threats.json";
        public const string ProcessesPath = @"processes.json";
    }
}
