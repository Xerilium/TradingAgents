use process_wrap::std::*;
use std::{
    env,
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

pub struct Backend {
    child: Box<dyn ChildWrapper>,
    finished: bool,
    #[cfg(unix)]
    pgid: u32,
}

fn python(root: &Path) -> PathBuf {
    if cfg!(windows) { root.join("python.exe") } else { root.join("bin/python3") }
}

fn persistent_runtime(payload: &Path, profile: &Path, kind: &str) -> Result<PathBuf, String> {
    let destination = profile.join("runtimes").join(kind);
    if fs::symlink_metadata(&destination).is_err_and(|e| e.kind() == std::io::ErrorKind::NotFound) {
        let seed = payload.join(kind);
        if !python(&seed).is_file() {
            return Err("Dependencies are not installed. Run the full TradingAgents setup once, then reopen the app. App updates do not contain Python runtimes.".into());
        }
        fs::create_dir_all(profile.join("runtimes")).map_err(|e| e.to_string())?;
        let mut copy = Command::new(python(&seed));
        copy.args(["-I", "-c", "import pathlib,shutil,sys; s,d=map(pathlib.Path,sys.argv[1:]); t=d.with_name(d.name+'.staging'); shutil.copytree(s,t,symlinks=True,copy_function=shutil.copy2); t.rename(d)"])
            .arg(&seed).arg(&destination).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            copy.creation_flags(windows::Win32::System::Threading::CREATE_NO_WINDOW.0);
        }
        let result = copy.output().map_err(|e| format!("Cannot seed {kind} runtime: {e}"))?;
        if !result.status.success() {
            return Err(format!("Cannot seed {kind} runtime: {}. Existing files were not replaced.", String::from_utf8_lossy(&result.stderr)));
        }
    }
    let site = if cfg!(windows) { destination.join("Lib/site-packages") } else { destination.join("lib") };
    if !fs::symlink_metadata(&destination).is_ok_and(|m| m.file_type().is_dir())
        || !python(&destination).is_file() || !site.is_dir() {
        return Err(format!("The persistent {kind} runtime is incomplete at {}. It was not replaced.", destination.display()));
    }
    Ok(python(&destination))
}

impl Backend {
    pub fn spawn(payload: &Path, profile: &Path, port: u16, development: bool)
        -> Result<(Self, mpsc::Receiver<()>), String>
    {
        let probe = TcpListener::bind(("127.0.0.1", port))
            .map_err(|e| format!("Port {port} is unavailable: {e}. Stop the other service and try again."))?;
        drop(probe);
        for name in ["application", "research", "private", "logs", "cache", "tmp"] {
            fs::create_dir_all(profile.join(name)).map_err(|e| e.to_string())?;
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(profile.join("private"), fs::Permissions::from_mode(0o700))
                .map_err(|e| e.to_string())?;
        }
        let source = if development && cfg!(debug_assertions) {
            Some(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize()
                .map_err(|e| format!("Cannot find the development checkout: {e}"))?)
        } else { None };
        let venv_python = |root: &Path| {
            if cfg!(windows) { root.join("Scripts/python.exe") } else { root.join("bin/python3") }
        };
        let (desk, native) = if let Some(root) = &source {
            (venv_python(&root.join(".venv")), venv_python(&root.join(".venv-nautilus-v1")))
        } else {
            (persistent_runtime(payload, profile, "desk")?, persistent_runtime(payload, profile, "native")?)
        };
        if !desk.is_file() || !native.is_file() {
            return Err("The packaged Python runtimes are missing. Reinstall TradingAgents.".into());
        }
        let log = OpenOptions::new().create(true).append(true).open(profile.join("logs/desk.log"))
            .map_err(|e| format!("Cannot open desk log: {e}"))?;
        let mut command = Command::new(desk);
        command.env_clear();
        for (key, value) in env::vars_os() {
            let name = key.to_string_lossy().to_ascii_uppercase();
            if matches!(name.as_str(), "PATH" | "SYSTEMROOT" | "WINDIR" | "COMSPEC" |
                "PATHEXT" | "USERPROFILE" | "HOME" | "APPDATA" | "LOCALAPPDATA" |
                "HOMEDRIVE" | "HOMEPATH" | "LANG" | "TZ" | "CODEX_HOME" | "MAENIFOLD_ROOT" |
                "HTTP_PROXY" | "HTTPS_PROXY" | "ALL_PROXY" | "NO_PROXY" | "SSL_CERT_FILE" |
                "SSL_CERT_DIR" | "REQUESTS_CA_BUNDLE" | "CURL_CA_BUNDLE") || name.starts_with("LC_")
            {
                command.env(key, value);
            }
        }
        if let Some(root) = source {
            command.args(["-I", "-u", "-c",
                "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('tradingagents.web.server',run_name='__main__')"])
                .arg(root);
        } else {
            let app = payload.join("app");
            if !app.join("tradingagents/web/server.py").is_file() {
                return Err("The packaged application code is missing. Reinstall TradingAgents.".into());
            }
            command.args(["-I", "-u", "-c",
                "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('tradingagents.web.server',run_name='__main__')"])
                .arg(app);
        }
        command.args(["--desktop-control", "--port", &port.to_string(), "--data-dir"])
            .arg(profile.join("application")).arg("--history-dir").arg(profile.join("research"))
            .arg("--nautilus-python").arg(native).arg("--credential-profile")
            .arg(if development { "development" } else { "production" }).current_dir(profile)
            .env("TRADINGAGENTS_DESKTOP_PROFILE", if development { "development" } else { "production" })
            .env("TRADINGAGENTS_RESULTS_DIR", profile.join("research/logs"))
            .env("TRADINGAGENTS_CACHE_DIR", profile.join("cache"))
            .env("TRADINGAGENTS_MEMORY_LOG_PATH", profile.join("private/trading_memory.md"))
            .env("TRADINGAGENTS_LAYA_CACHE", profile.join("cache/laya"))
            .env("HF_HOME", profile.join("cache/huggingface"))
            .env("TMP", profile.join("tmp")).env("TEMP", profile.join("tmp")).env("TMPDIR", profile.join("tmp"))
            .stdin(Stdio::piped()).stdout(Stdio::piped())
            .stderr(Stdio::from(log.try_clone().map_err(|e| e.to_string())?));
        let mut wrapped = CommandWrap::from(command);
        #[cfg(windows)]
        {
            wrapped.wrap(CreationFlags(windows::Win32::System::Threading::CREATE_NO_WINDOW));
            wrapped.wrap(JobObject);
        }
        #[cfg(unix)]
        wrapped.wrap(ProcessGroup::leader());
        let child = wrapped.spawn().map_err(|e| format!("Cannot start the desk: {e}"))?;
        #[cfg(unix)]
        let pgid = child.id();
        let mut backend = Self { child, finished: false, #[cfg(unix)] pgid };
        let stdout = backend.child.stdout().take().ok_or("Cannot read the desk startup pipe")?;
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let mut log = log;
            for line in BufReader::new(stdout).lines() {
                let Ok(line) = line else { break };
                let _ = writeln!(log, "{line}");
                let ready = serde_json::from_str::<serde_json::Value>(&line).ok().is_some_and(|v|
                    v.get("desktop_ready").and_then(|x| x.as_bool()) == Some(true)
                    && v.get("port").and_then(|x| x.as_u64()) == Some(port as u64));
                if ready { let _ = tx.send(()); }
            }
        });
        Ok((backend, rx))
    }

    pub fn exited(&mut self) -> Result<bool, String> {
        self.child.try_wait().map(|s| s.is_some()).map_err(|e| format!("Cannot inspect the desk process: {e}"))
    }

    pub fn stop(&mut self) -> Result<(), String> {
        if self.finished { return Ok(()); }
        if let Some(mut stdin) = self.child.stdin().take() { let _ = writeln!(stdin, "stop"); }
        let deadline = Instant::now() + Duration::from_secs(45);
        while !self.exited()? && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(200));
        }
        // Terminate the owned job/group even if its leader exited before a descendant.
        if let Err(e) = self.child.start_kill() {
            #[cfg(unix)]
            if e.raw_os_error() == Some(libc::ESRCH) { self.finished = true; return Ok(()); }
            return Err(format!("Cannot stop the owned process group: {e}"));
        }
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            let leader_exited = self.exited()?;
            #[cfg(windows)]
            let stopped = leader_exited;
            #[cfg(unix)]
            let stopped = {
                let result = unsafe { libc::kill(-(self.pgid as i32), 0) };
                if result == 0 { false } else {
                    let e = std::io::Error::last_os_error();
                    if e.raw_os_error() != Some(libc::ESRCH) {
                        return Err(format!("Cannot inspect the owned process group: {e}"));
                    }
                    leader_exited
                }
            };
            if stopped { self.finished = true; return Ok(()); }
            if Instant::now() >= deadline {
                return Err("The owned desk process did not exit. Try Quit again.".into());
            }
            thread::sleep(Duration::from_millis(100));
        }
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        if !self.finished { let _ = self.child.start_kill(); }
    }
}
