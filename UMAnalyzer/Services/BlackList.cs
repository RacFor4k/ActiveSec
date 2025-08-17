using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using UMAnalyzer.Common;
using UMAnalyzer.Models.Threads;

namespace UMAnalyzer.Services
{
    internal class BlackList
    {
        private List<Threat> _ThreatList;
        private HashSet<Process> _ProcessesList = new HashSet<Process>();
        private void LoadThreats(string path)
        {
            foreach (var line in File.ReadLines(path))
            {
                if (string.IsNullOrWhiteSpace(line))
                    continue;

                try
                {
                    using var doc = JsonDocument.Parse(line);
                    if (doc.RootElement.TryGetProperty("ProcessPath", out var value))
                    {
                        _ThreatList.Add(new Threat { ProcessPath = value.GetString() });
                    }
                }
                catch (JsonException ex)
                {
                    Console.WriteLine($"Ошибка парсинга строки: {line} \n{ex.Message}");
                }
            }
        } 

        public BlackList()
        {
            _ThreatList = new List<Threat>();
            LoadThreats(ConstProvider.ThreatsPath);
        }

        public Process? GetProcess(string ProcessPath)
        {
            return _ProcessesList.First(t => t.Equals(new Process(ProcessPath)));
        }
    }
}
