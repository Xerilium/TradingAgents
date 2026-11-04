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

fn venv_python(root: &Path) -> PathBuf {
    if cfg!(windows) { root.join("Scripts/python.exe") } else { root.join("bin/python3") }
}

fn site_dir(root: &Path) -> PathBuf {
    if cfg!(windows) { root.join("Lib/site-packages") } else { root.join("lib") }
}

/// What the packaged plan says an environment is made of. The interpreter minor
/// comes from the reviewed lock at build time, so the wheels and the created
/// environment can never disagree.
struct Plan {
    minor: String,
    wheelhouse: PathBuf,
    requirements: PathBuf,
}

fn plan(payload: &Path, kind: &str) -> Result<Plan, String> {
    let text = fs::read_to_string(payload.join("provenance.json"))
        .map_err(|_| "The packaged dependency plan is missing. Reinstall TradingAgents.".to_string())?;
    let value: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| format!("Cannot read the packaged dependency plan: {e}"))?;
    let spec = value.get("environments").and_then(|items| items.get(kind))
        .ok_or_else(|| format!("The packaged dependency plan does not describe the {kind} environment. Reinstall TradingAgents."))?;
    let field = |key: &str| spec.get(key).and_then(|v| v.as_str()).map(str::to_string)
        .ok_or_else(|| format!("The packaged {kind} plan is missing {key}. Reinstall TradingAgents."));
    Ok(Plan { minor: field("python_minor")?, wheelhouse: payload.join(field("wheelhouse")?),
              requirements: payload.join(field("requirements")?) })
}

/// Find a host interpreter for the requested minor. The app never ships one.
fn host_interpreter(minor: &str) -> Result<PathBuf, String> {
    #[cfg(windows)]
    {
        if let Ok(output) = Command::new("py").args(["--list-paths"]).output() {
            for line in String::from_utf8_lossy(&output.stdout).lines() {
                if line.contains(&format!("-V:{minor}")) {
                    if let Some(path) = line.split_whitespace().last() {
                        let path = PathBuf::from(path);
                        if path.is_file() { return Ok(path); }
                    }
                }
            }
        }
        if let Some(local) = env::var_os("LOCALAPPDATA") {
            let candidate = Path::new(&local).join(format!(r"Python\pythoncore-{minor}-64\python.exe"));
            if candidate.is_file() { return Ok(candidate); }
        }
        Err(format!("Python {minor} is not installed. Install it with the Python Manager: py install {minor}"))
    }
    #[cfg(not(windows))]
    {
        let candidate = format!("python{minor}");
        if Command::new(&candidate).arg("--version").output().is_ok_and(|o| o.status.success()) {
            return Ok(PathBuf::from(candidate));
        }
        Err(format!("Python {minor} is not installed. Install it first, for example: brew install python@{minor}"))
    }
}

/// True when a virtual environment still points at an interpreter that exists.
fn environment_intact(environment: &Path) -> bool {
    let config = match fs::read_to_string(environment.join("pyvenv.cfg")) {
        Ok(text) => text,
        Err(_) => return false,
    };
    let mut base: Option<String> = None;
    for line in config.lines() {
        if let Some((key, value)) = line.split_once('=') {
            let (key, value) = (key.trim(), value.trim());
            if key == "executable" { base = Some(value.split_whitespace().next().unwrap_or(value).to_string()); }
            else if key == "home" && base.is_none() { base = Some(value.to_string()); }
        }
    }
    base.is_some_and(|path| Path::new(&path).is_file())
        && venv_python(environment).is_file() && site_dir(environment).is_dir()
}

fn move_aside(destination: &Path, suffix: &str) -> Result<(), String> {
    let kept = destination.with_file_name(format!("{suffix}"));
    fs::rename(destination, &kept)
        .map_err(|e| format!("Cannot move the unusable {} environment aside: {e}. Nothing was deleted; rename {} manually.",
                             destination.file_name().and_then(|n| n.to_str()).unwrap_or("runtime"), destination.display()))
}

fn run_step(python: &Path, args: &[&str], log: &mut fs::File, what: &str) -> Result<(), String> {
    let mut command = Command::new(python);
    command.args(args).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(windows::Win32::System::Threading::CREATE_NO_WINDOW.0);
    }
    let output = command.output().map_err(|e| format!("Cannot {what}: {e}"))?;
    let _ = writeln!(log, "{what}: {} {}", python.display(), args.join(" "));
    let _ = log.write_all(&output.stdout);
    let _ = log.write_all(&output.stderr);
    if !output.status.success() {
        let reason = String::from_utf8_lossy(&output.stderr).lines().last().unwrap_or("").trim().to_string();
        return Err(format!("Cannot {what}: {reason}"));
    }
    Ok(())
}

/// Create one runtime environment from the packaged wheels, offline. This happens
/// the first time the profile needs it; app updates never touch the result.
fn create_environment(payload: &Path, profile: &Path, kind: &str, log: &mut fs::File) -> Result<PathBuf, String> {
    let spec = plan(payload, kind)?;
    for required in [&spec.wheelhouse, &spec.requirements] {
        if !required.exists() {
            return Err(format!("The packaged {kind} dependencies are missing at {}. Reinstall TradingAgents.", required.display()));
        }
    }
    let base = host_interpreter(&spec.minor)?;
    let destination = profile.join("runtimes").join(kind);
    let staging = destination.with_file_name(format!("{kind}.staging"));
    if staging.exists() { let _ = fs::remove_dir_all(&staging); }
    fs::create_dir_all(destination.parent().unwrap_or(profile)).map_err(|e| e.to_string())?;
    let _ = writeln!(log, "Creating the {kind} environment with python {} (first run only).", spec.minor);
    run_step(&base, &["-m", "venv", &staging.to_string_lossy()], log, &format!("create the {kind} environment"))
        .map_err(|e| { let _ = fs::remove_dir_all(&staging); e })?;
    let staged_python = venv_python(&staging);
    run_step(&staged_python, &["-m", "pip", "install", "--no-index", "--disable-pip-version-check",
        "--find-links", &spec.wheelhouse.to_string_lossy(), "--require-hashes", "-r", &spec.requirements.to_string_lossy()],
        log, &format!("install the {kind} dependencies"))
        .map_err(|e| { let _ = fs::remove_dir_all(&staging); e })?;
    fs::rename(&staging, &destination).map_err(|e| {
        let _ = fs::remove_dir_all(&staging);
        format!("Cannot place the new {kind} environment: {e}")
    })?;
    let _ = writeln!(log, "Created the {kind} environment at {}.", destination.display());
    // The staging directory is gone after the rename, so report the placed path.
    Ok(venv_python(&destination))
}

/// The interpreter for one runtime, creating its environment when the profile
/// does not have a usable one yet. Anything unusable is moved aside, never deleted.
fn runtime(payload: &Path, profile: &Path, kind: &str, log: &mut fs::File) -> Result<PathBuf, String> {
    let destination = profile.join("runtimes").join(kind);
    match fs::symlink_metadata(&destination) {
        Ok(meta) if meta.file_type().is_dir() => {
            if destination.join("pyvenv.cfg").is_file() {
                if environment_intact(&destination) { return Ok(venv_python(&destination)); }
                let _ = writeln!(log, "The {kind} environment at {} cannot run: its interpreter is gone. Rebuilding it from the packaged wheels.", destination.display());
                move_aside(&destination, &format!("{kind}-broken"))?;
            } else {
                let _ = writeln!(log, "The {kind} runtime at {} is not a virtual environment; moving it aside.", destination.display());
                move_aside(&destination, &format!("{kind}-previous"))?;
            }
        }
        Ok(_) => return Err(format!("{} is not a directory and was left in place. Fix it manually.", destination.display())),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(e) => return Err(format!("Cannot inspect the {kind} runtime: {e}")),
    }
    create_environment(payload, profile, kind, log)
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
        let log = OpenOptions::new().create(true).append(true).open(profile.join("logs/desk.log"))
            .map_err(|e| format!("Cannot open desk log: {e}"))?;
        let mut log = log;
        let (desk, native) = if let Some(root) = &source {
            for name in [".venv", ".venv-nautilus-v1"] {
                let environment = root.join(name);
                if !environment.join("pyvenv.cfg").is_file() || !environment_intact(&environment) {
                    return Err(format!("The development environment {} is missing or was built from an interpreter that is no longer installed. Recreate it: python -m venv {}",
                        environment.display(), environment.display()));
                }
            }
            (venv_python(&root.join(".venv")), venv_python(&root.join(".venv-nautilus-v1")))
        } else {
            (runtime(payload, profile, "desk", &mut log)?, runtime(payload, profile, "native", &mut log)?)
        };
        if !desk.is_file() {
            return Err(format!("The desk interpreter is missing at {}. Reopen the app to rebuild the environment.", desk.display()));
        }
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
