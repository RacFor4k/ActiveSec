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
        private HashSet<Threat> _ThreatList = new HashSet<Threat>();
        private HashSet<Process> _ProcessesList = new HashSet<Process>();
        private void LoadThreats(string path)
        {
            _ThreatList = new HashSet<Threat>();

            foreach (var line in File.ReadLines(path))
            {
                if (string.IsNullOrWhiteSpace(line))
                    continue;

                try
                {
                    _ThreatList.Add(JsonSerializer.Deserialize<Threat>(line));
                }
                catch (JsonException ex)
                {
                    Console.WriteLine($"Ошибка парсинга строки: {line}\n{ex.Message}");
                }
            }
        }

        private void UpdateThreatsList(string path, Threat threat)
        {
            using (var fs = File.AppendText(path))
            {
                string json = JsonSerializer.Serialize(threat);
                fs.WriteLine(json); // автоматически добавляет перевод строки
            }
        }

        private void UpdateProcessesList(string path, Process threat)
        {
            using (var fs = File.AppendText(path))
            {
                string json = JsonSerializer.Serialize(threat);
                fs.WriteLine(json); // автоматически добавляет перевод строки
            }
        }

        private void LoadProcesses(string path)
        {
            _ProcessesList = new HashSet<Process>();

            foreach (var line in File.ReadLines(path))
            {
                if (string.IsNullOrWhiteSpace(line))
                    continue;

                try
                {
                    _ProcessesList.Add(JsonSerializer.Deserialize<Process>(line));
                }
                catch (JsonException ex)
                {
                    Console.WriteLine($"Ошибка парсинга строки: {line}\n{ex.Message}");
                }
            }
        }

        public BlackList()
        {
            LoadThreats(ConstProvider.ThreatsPath);
            LoadProcesses(ConstProvider.ProcessesPath);
        }

        public Process? GetProcess(string ProcessPath)
        {
            return _ProcessesList.First(t => t.Equals(new Process(ProcessPath)));
        }
        public void AddProcess(Process process)
        {
            if(_ProcessesList.Add(process))
                UpdateProcessesList(ConstProvider.ProcessesPath, process);
        }
        public void AddThreat(Process threatProcess)
        {
            Threat threat = new Threat { ProcessPath = threatProcess.GetProcessPath() };
            if(_ThreatList.Add(threat))
                UpdateThreatsList(ConstProvider.ThreatsPath, threat);
            _ProcessesList.Remove(threatProcess);
        }
    }
}
