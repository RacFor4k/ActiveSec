using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Windows.Devices.Usb;

namespace UMAnalyzer.Models.Threads
{
    internal struct Threat : IComparable<Threat>, IEquatable<Threat>
    {
        public string ProcessPath;

        public int CompareTo(Threat other)
        {
            return ProcessPath.CompareTo(other.ProcessPath);
        }
        public bool Equals(Threat other)
        {
            return ProcessPath == other.ProcessPath;
        }
         
    }

    internal struct Process : IEquatable<Process>
    {
        private string _processPath;
        private double _distrust;
        public List<Action> Actions { get; }
        public Process(string _processPath)
        {
            _processPath = _processPath;
            Actions = new List<Action>();
        }
        public string GetProcessPath()
        {
            return _processPath;
        }
        public void AddAction(Action action)
        {
            Actions.Add(action);
            _distrust += action.Distrust;
        }
        public double GetDistrust()
        {
            return _distrust;
        }
        public bool Equals(Process other)
        {
            return _processPath.Equals(other._processPath);
        }
    }

    internal struct Action : IComparable<Action>, IEquatable<Action>
    {
        public ushort Type;
        public float Distrust;
        public string Path;
        public int CompareTo(Action other)
        {
            return Distrust.CompareTo(other.Distrust);
        }
        public bool Equals(Action other)
        {
            return other.Type == Type && other.Path == Path;
        }
    }


}
