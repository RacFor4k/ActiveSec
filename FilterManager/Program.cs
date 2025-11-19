// Compile: dotnet new winforms -n MiniFilterTool -f net8.0-windows
// Replace Program.cs with this file content, then: dotnet build / run
// Requires <TargetFramework>net8.0-windows</TargetFramework> and <UseWindowsForms>true</UseWindowsForms>

using System;
using System.Diagnostics;
using System.IO;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

public class MainForm : Form
{
    TextBox txtInf, txtFilterName, txtPrefix, txtLog, txtOutput;
    Button btnBrowseInf, btnInstall, btnStart, btnStop, btnDelete, btnStatus, btnPickDbgLog, btnStartDbgView, btnStopDbgView, btnOpenLogFolder;
    ListBox lstDbgLines;
    CheckBox chkAutoStatus;
    System.Windows.Forms.Timer statusTimer;

    CancellationTokenSource tailCts;
    Process dbgviewProc;
    string autoDbgLogPath = null;

    public MainForm()
    {
        this.Text = "Minifilter Manager (.NET 8 / WinForms)";
        this.Width = 1050;
        this.Height = 720;

        var lblInf = new Label { Text = "INF:", Left = 10, Top = 15, Width = 40 };
        txtInf = new TextBox { Left = 60, Top = 10, Width = 720 };
        btnBrowseInf = new Button { Left = 790, Top = 8, Width = 110, Text = "Обзор..." };
        btnInstall = new Button { Left = 910, Top = 8, Width = 115, Text = "Установить" };

        var lblFilter = new Label { Text = "Имя фильтра (ServiceName):", Left = 10, Top = 50, Width = 220 };
        txtFilterName = new TextBox { Left = 230, Top = 45, Width = 240 };
        btnStart = new Button { Left = 480, Top = 43, Width = 110, Text = "Запуск + attach" };
        btnStop = new Button { Left = 600, Top = 43, Width = 110, Text = "Остановить" };
        btnDelete = new Button { Left = 720, Top = 43, Width = 110, Text = "Удалить" };
        btnStatus = new Button { Left = 840, Top = 43, Width = 90, Text = "Статус" };
        chkAutoStatus = new CheckBox { Left = 940, Top = 47, Width = 90, Text = "Авто" };

        var grpDbg = new GroupBox { Left = 10, Top = 85, Width = 1015, Height = 260, Text = "DBGView (фильтруется по префиксу)" };
        var lblPrefix = new Label { Parent = grpDbg, Text = "Префикс (напр. ActiveSec):", Left = 10, Top = 25, Width = 200 };
        txtPrefix = new TextBox { Parent = grpDbg, Left = 210, Top = 20, Width = 200 };
        var lblDbgLog = new Label { Parent = grpDbg, Text = "Файл лога DbgView:", Left = 420, Top = 25, Width = 130 };
        txtLog = new TextBox { Parent = grpDbg, Left = 550, Top = 20, Width = 295 };
        btnPickDbgLog = new Button { Parent = grpDbg, Left = 850, Top = 18, Width = 70, Text = "Файл..." };
        btnOpenLogFolder = new Button { Parent = grpDbg, Left = 925, Top = 18, Width = 75, Text = "Папка" };

        lstDbgLines = new ListBox { Parent = grpDbg, Left = 10, Top = 55, Width = 990, Height = 165, HorizontalScrollbar = true };

        btnStartDbgView = new Button { Parent = grpDbg, Left = 10, Top = 225, Width = 220, Text = "Старт DbgView рядом с EXE" };
        btnStopDbgView = new Button { Parent = grpDbg, Left = 240, Top = 225, Width = 160, Text = "Стоп DbgView" };

        var lblOut = new Label { Text = "Вывод команд:", Left = 10, Top = 355, Width = 150 };
        txtOutput = new TextBox { Left = 10, Top = 380, Width = 1015, Height = 290, Multiline = true, ScrollBars = ScrollBars.Both, ReadOnly = true, Font = new System.Drawing.Font("Consolas", 9), WordWrap = false };

        this.Controls.AddRange(new Control[] {
            lblInf, txtInf, btnBrowseInf, btnInstall,
            lblFilter, txtFilterName, btnStart, btnStop, btnDelete, btnStatus, chkAutoStatus,
            grpDbg,
            lblOut, txtOutput
        });

        btnBrowseInf.Click += (_, __) => BrowseInf();
        btnInstall.Click += async (_, __) => await InstallInfAsync();
        btnStart.Click += async (_, __) => await StartFilterAsync();
        btnStop.Click += async (_, __) => await StopFilterAsync();
        btnDelete.Click += async (_, __) => await DeleteDriverAsync();
        btnStatus.Click += async (_, __) => await ShowStatusAsync();
        chkAutoStatus.CheckedChanged += (_, __) => ToggleAutoStatus();

        btnPickDbgLog.Click += (_, __) => PickDbgLog();
        btnOpenLogFolder.Click += (_, __) => OpenLogFolder();
        btnStartDbgView.Click += async (_, __) => await StartDbgViewAndTailAsync();
        btnStopDbgView.Click += (_, __) => StopDbgViewAndTail();

        statusTimer = new System.Windows.Forms.Timer();
        statusTimer.Interval = 2500;
        statusTimer.Tick += async (_, __) => await ShowStatusAsync();

        this.Load += (_, __) => CheckAdmin();
        this.FormClosing += (_, __) => { StopDbgViewAndTail(); };
    }

    void CheckAdmin()
    {
        var wi = WindowsIdentity.GetCurrent();
        var wp = new WindowsPrincipal(wi);
        if (!wp.IsInRole(WindowsBuiltInRole.Administrator))
        {
            AppendOut("[!] Внимание: приложение НЕ запущено от имени администратора — команды могут не выполниться.\r\n");
        }
    }

    void BrowseInf()
    {
        using var ofd = new OpenFileDialog
        {
            Filter = "INF files (*.inf)|*.inf|All files (*.*)|*.*",
            Title = "Выберите INF драйвера"
        };
        if (ofd.ShowDialog() == DialogResult.OK)
            txtInf.Text = ofd.FileName;
    }

    void PickDbgLog()
    {
        using var ofd = new OpenFileDialog
        {
            Filter = "Log files (*.log;*.txt)|*.log;*.txt|All files (*.*)|*.*",
            Title = "Укажите файл лога DebugView (если уже ведётся)"
        };
        if (ofd.ShowDialog() == DialogResult.OK)
        {
            txtLog.Text = ofd.FileName;
            StartTailing(ofd.FileName);
        }
    }

    void OpenLogFolder()
    {
        try
        {
            string path = txtLog.Text;
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                AppendOut("Укажите корректный путь к файлу лога DebugView.\r\n");
                return;
            }
            Process.Start("explorer.exe", "/select,\"" + path + "\"");
        }
        catch (Exception ex)
        {
            AppendOut("Ошибка открытия папки: " + ex.Message + "\r\n");
        }
    }

    async Task InstallInfAsync()
    {
        string inf = txtInf.Text.Trim();
        if (!File.Exists(inf))
        {
            AppendOut("INF не найден. Укажите корректный путь.\r\n");
            return;
        }

        // pnputil /add-driver "X.inf" /install
        string cmd = $"pnputil /add-driver \"{inf}\" /install";
        AppendOut($"> {cmd}\r\n");
        var r = await RunShellAsync(cmd);
        AppendOut(r);
        AppendOut("\r\nПодсказка: если драйвер неподписан — требуются TestSigning и отключенный Secure Boot.\r\n");
    }

    async Task StartFilterAsync()
    {
        string name = txtFilterName.Text.Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            AppendOut("Укажите имя фильтра (ServiceName из INF).\r\n");
            return;
        }

        // fltmc load <name>
        string loadCmd = $"fltmc load \"{name}\"";
        AppendOut($"> {loadCmd}\r\n");
        var r1 = await RunShellAsync(loadCmd);
        AppendOut(r1);

        // fltmc attach <name> C:
        string attachCmd = $"fltmc attach \"{name}\" c:";
        AppendOut($"> {attachCmd}\r\n");
        var r2 = await RunShellAsync(attachCmd);
        AppendOut(r2);
    }

    async Task StopFilterAsync()
    {
        string name = txtFilterName.Text.Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            AppendOut("Укажите имя фильтра.\r\n");
            return;
        }

        // detach от C:
        string detachCmd = $"fltmc detach \"{name}\" C:";
        AppendOut($"> {detachCmd}\r\n");
        var r1 = await RunShellAsync(detachCmd);
        AppendOut(r1);

        // unload
        string unloadCmd = $"fltmc unload \"{name}\"";
        AppendOut($"> {unloadCmd}\r\n");
        var r2 = await RunShellAsync(unloadCmd);
        AppendOut(r2);
    }

    async Task DeleteDriverAsync()
    {
        // Найти oemXX.inf по исходному имени INF
        string inf = txtInf.Text.Trim();
        if (string.IsNullOrWhiteSpace(inf))
        {
            AppendOut("Для удаления укажите исходный INF (чтобы найти oemXX.inf).\r\n");
            return;
        }

        string baseInfName = Path.GetFileName(inf);

        AppendOut("> pnputil /enum-drivers\r\n");
        var list = await RunShellAsync("pnputil /enum-drivers");
        AppendOut(list);

        // Ищем Published Name (oem*.inf) для Original Name == baseInfName
        // Пример блоков:
        // Published Name : oem42.inf
        // Original Name  : mydriver.inf
        string oem = FindOemByOriginalName(list, baseInfName);

        if (oem == null)
        {
            AppendOut($"Не найден oemXX.inf для Original Name = {baseInfName}. Удаление по INF невозможно.\r\n");
            return;
        }

        string delCmd = $"pnputil /delete-driver {oem} /uninstall /force";
        AppendOut($"> {delCmd}\r\n");
        var r = await RunShellAsync(delCmd);
        AppendOut(r);
    }

    static string FindOemByOriginalName(string pnputilEnum, string originalInf)
    {
        var lines = pnputilEnum.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
        string currentOem = null;
        foreach (var line in lines)
        {
            var l = line.Trim();
            if (l.StartsWith("Published Name", StringComparison.OrdinalIgnoreCase))
            {
                var m = Regex.Match(l, @"Published Name\s*:\s*(\S+)", RegexOptions.IgnoreCase);
                if (m.Success) currentOem = m.Groups[1].Value.Trim();
            }
            else if (l.StartsWith("Original Name", StringComparison.OrdinalIgnoreCase) && currentOem != null)
            {
                var m = Regex.Match(l, @"Original Name\s*:\s*(\S+)", RegexOptions.IgnoreCase);
                if (m.Success)
                {
                    var orig = m.Groups[1].Value.Trim();
                    if (string.Equals(orig, originalInf, StringComparison.OrdinalIgnoreCase))
                        return currentOem;
                }
            }
        }
        return null;
    }

    async Task ShowStatusAsync()
    {
        string name = txtFilterName.Text.Trim();
        var r = await RunShellAsync("fltmc filters");
        AppendOut("> fltmc filters\r\n" + r);

        if (!string.IsNullOrWhiteSpace(name))
        {
            // Подсветим строку конкретного фильтра
            var found = false;
            foreach (var line in r.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None))
            {
                if (line.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    AppendOut("[FILTER] " + line + "\r\n");
                    found = true;
                }
            }
            if (!found)
                AppendOut($"[FILTER] '{name}' не найден среди активных фильтров.\r\n");
        }
    }

    void ToggleAutoStatus()
    {
        statusTimer.Enabled = chkAutoStatus.Checked;
    }

    // --- DBGVIEW: авто-запуск и «хвост» лога ---
    async Task StartDbgViewAndTailAsync()
    {
        try
        {
            // Ожидаем, что dbgview64.exe лежит рядом с нашим EXE
            string exeDir = AppDomain.CurrentDomain.BaseDirectory;
            string dbg = Path.Combine(exeDir, "dbgview64.exe");
            if (!File.Exists(dbg))
            {
                AppendOut("dbgview64.exe не найден рядом с приложением. Можно указать готовый лог через кнопку «Файл...» и приложение будет его читать с фильтрацией.\r\n");
                return;
            }

            // создаём временный лог
            autoDbgLogPath = Path.Combine(Path.GetTempPath(), "dbgview_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".log");
            txtLog.Text = autoDbgLogPath;

            // ВАЖНО: у разных версий DebugView набор ключей может отличаться.
            // Здесь: /accepteula — автопринятие EULA,
            // /k — захват kernel, /t — метки времени,
            // /o <file> — лог в файл (если ключ не поддерживается вашей версией — откройте лог вручную через меню и укажите этот же файл).
            var args = $"/k /l \"{autoDbgLogPath}\"";
            AppendOut($"> Запуск DbgView: {Path.GetFileName(dbg)} {args}\r\n");

            var si = new ProcessStartInfo
            {
                FileName = dbg,
                Arguments = args,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = false,
                RedirectStandardError = false
            };
            dbgviewProc = Process.Start(si);

            await Task.Delay(800); // дать создать файл
            if (File.Exists(autoDbgLogPath))
            {
                StartTailing(autoDbgLogPath);
                AppendOut("DbgView запущен, начинается чтение лога...\r\n");
            }
            else
            {
                AppendOut("DbgView запущен, но файл лога ещё не создан. Можно выбрать лог вручную кнопкой «Файл...». \r\n");
            }
        }
        catch (Exception ex)
        {
            AppendOut("Ошибка запуска DbgView: " + ex.Message + "\r\n");
        }
    }

    void StopDbgViewAndTail()
    {
        try
        {
            tailCts?.Cancel();
            tailCts = null;
        }
        catch { }
        try
        {
            if (dbgviewProc != null && !dbgviewProc.HasExited)
            {
                dbgviewProc.Kill(true);
                dbgviewProc.Dispose();
            }
            dbgviewProc = null;
            AppendOut("DbgView остановлен.\r\n");
        }
        catch (Exception ex)
        {
            AppendOut("Ошибка остановки DbgView: " + ex.Message + "\r\n");
        }
    }

    void StartTailing(string path)
    {
        tailCts?.Cancel();
        tailCts = new CancellationTokenSource();
        var token = tailCts.Token;

        Task.Run(async () =>
        {
            try
            {
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                using var sr = new StreamReader(fs, DetectEncoding(path) ?? Encoding.UTF8, true);

                // Перематываем в конец и читаем новые строки (tail -f)
                fs.Seek(0, SeekOrigin.End);
                long lastLen = fs.Position;

                string prefix = "";
                while (!token.IsCancellationRequested)
                {
                    await Task.Delay(300, token);
                    // если файл вырос — читаем хвост
                    if (fs.Length < lastLen)
                    {
                        // ротация/очистка — начинаем заново
                        fs.Seek(0, SeekOrigin.Begin);
                        lastLen = 0;
                    }
                    if (fs.Length > lastLen)
                    {
                        fs.Seek(lastLen, SeekOrigin.Begin);
                        string chunk = await sr.ReadToEndAsync();
                        lastLen = fs.Position;
                        if (!string.IsNullOrEmpty(chunk))
                        {
                            var lines = chunk.Replace("\r\n", "\n").Split('\n');
                            prefix = this.txtPrefix.InvokeRequired
                                ? (string)this.txtPrefix.Invoke(new Func<string>(() => this.txtPrefix.Text.Trim()))
                                : this.txtPrefix.Text.Trim();

                            foreach (var line in lines)
                            {
                                var text = line.TrimEnd();
                                if (string.IsNullOrEmpty(text)) continue;
                                if (string.IsNullOrWhiteSpace(prefix) || text.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                                {
                                    AddDbgLine(text);
                                }
                            }
                        }
                    }
                }
            }
            catch (TaskCanceledException) { }
            catch (Exception ex)
            {
                AppendOut("Ошибка чтения лога DbgView: " + ex.Message + "\r\n");
            }
        }, token);
    }

    static Encoding DetectEncoding(string file)
    {
        // Простой хак: если в начале BOM UTF-8 — используем UTF-8; иначе Windows-1251 как распространённый вариант.
        try
        {
            using var fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            if (fs.Length >= 3)
            {
                byte[] bom = new byte[3];
                fs.Read(bom, 0, 3);
                if (bom[0] == 0xEF && bom[1] == 0xBB && bom[2] == 0xBF)
                    return new UTF8Encoding(true);
            }
        }
        catch { }
        try { return Encoding.GetEncoding(1251); } catch { return Encoding.UTF8; }
    }

    void AddDbgLine(string line)
    {
        if (lstDbgLines.InvokeRequired)
        {
            lstDbgLines.BeginInvoke(new Action<string>(AddDbgLine), line);
            return;
        }
        if (lstDbgLines.Items.Count > 5000)
            lstDbgLines.Items.RemoveAt(0);
        lstDbgLines.Items.Add(line);
        lstDbgLines.TopIndex = lstDbgLines.Items.Count - 1;
    }

    // --- оболочка для запуска внешних утилит с корректной кодировкой ---
    async Task<string> RunShellAsync(string command)
    {
        // Будем выполнять через PowerShell, выставив UTF-8 чтобы русский не «ломался»
        // Также читаем как stdout, так и stderr, и возвращаем всё в один буфер.
        string psCmd =
            "$ErrorActionPreference='Continue';" +
            "$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding;" +
            "Try { " +
            "  " + EscapeForPowerShell(command) + " | Out-String -Width 4096 " +
            "} Catch { $_ | Out-String -Width 4096 }";
        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command {QuoteForCmd(psCmd)}",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        var sb = new StringBuilder();
        await Task.Run(() =>
        {
            using var p = new Process();
            p.StartInfo = psi;

            p.OutputDataReceived += (s, e) => { if (e.Data != null) sb.AppendLine(e.Data); };
            p.ErrorDataReceived += (s, e) => { if (e.Data != null) sb.AppendLine(e.Data); };
            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            p.WaitForExit();
        });

        return sb.ToString();
    }

    static string QuoteForCmd(string s)
    {
        // Оборачиваем строку для cmd-парсинга (powershell -Command "<строка>")
        return "\"" + s.Replace("\"", "`\"") + "\"";
    }

    string EscapeForPowerShell(string raw)
    {
        // Встраиваем произвольную команду в PowerShell-скрипт безопасно
        // Превратим в: & cmd.exe /c "<raw>"
        return $"& cmd.exe /c {raw.Replace("\"","\'")}";
    }

    void AppendOut(string text)
    {
        if (txtOutput.InvokeRequired)
        {
            txtOutput.BeginInvoke(new Action<string>(AppendOut), text);
            return;
        }
        txtOutput.AppendText(text);
        if (!text.EndsWith("\r\n")) txtOutput.AppendText("\r\n");
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm());
    }
}
