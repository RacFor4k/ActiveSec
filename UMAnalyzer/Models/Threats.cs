using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Windows.Devices.Usb;

namespace UMAnalyzer.Models.Threads
{
    internal struct Threat : IComparable<Threat>
    {
        public ulong pid;
        public string Destination;
        
        public int CompareTo(Threat other)
        {
            return pid.CompareTo(other.pid);
        }

    }

    internal struct Proccess : IComparable<Proccess>, IEquatable<Proccess>
    {
        private ulong _pid;
        private double _distrust;
        public List<Action> actions { get; }
        public Proccess(ulong pid)
        {
            _pid = pid;
            actions = new List<Action>();
        }
        public ulong GetPid()
        {
            return _pid;
        }
        public void AddAction(Action action)
        {
            actions.Add(action);
            _distrust += action.distrust;
        }
        public double GetDistrust()
        {
            return _distrust;
        }
        public int CompareTo(Proccess other)
        {
            return _pid.CompareTo(other._pid);
        }
        public bool Equals(Proccess other)
        {
            return _pid.Equals(other._pid);
        }
    }

    internal struct Action : IComparable<Action>, IEquatable<Action>
    {
        public ushort type;
        public float distrust;
        public string path;
        public int CompareTo(Action other)
        {
            return distrust.CompareTo(other.distrust);
        }
        public bool Equals(Action other)
        {
            return other.type == type && other.path == path;
        }
    }


}
