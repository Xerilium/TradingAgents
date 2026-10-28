#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod backend;

use backend::Backend;
use std::{
    path::PathBuf,
    sync::{atomic::{AtomicBool, Ordering}, mpsc, Arc},
    thread,
    time::{Duration, Instant},
};
use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_updater::UpdaterExt;

struct Host {
    tx: mpsc::Sender<Action>,
    exiting: Arc<AtomicBool>,
    updating: Arc<AtomicBool>,
}
enum Action { Open, Restart, StopForUpdate(mpsc::Sender<Result<(), String>>), Resume, Quit }
struct UpdateGuard(Arc<AtomicBool>);
impl Drop for UpdateGuard {
    fn drop(&mut self) { self.0.store(false, Ordering::SeqCst); }
}
fn notice(app: &tauri::AppHandle, text: impl Into<String>, error: bool) {
    app.dialog().message(text.into()).title("TradingAgents")
        .kind(if error { MessageDialogKind::Error } else { MessageDialogKind::Info }).show(|_| {});
}
fn status(item: &MenuItem<tauri::Wry>, text: &str) { let _ = item.set_text(text); }
fn open(app: &tauri::AppHandle, port: u16) {
    if let Err(e) = app.opener().open_url(format!("http://127.0.0.1:{port}/"), None::<&str>) {
        notice(app, format!("Cannot open the browser: {e}"), true);
    }
}
fn stop(backend: &mut Option<Backend>) -> Result<(), String> {
    if let Some(child) = backend.as_mut() { child.stop()?; }
    *backend = None;
    Ok(())
}

fn supervisor(app: tauri::AppHandle, rx: mpsc::Receiver<Action>, item: MenuItem<tauri::Wry>,
              payload: PathBuf, profile: PathBuf, port: u16, development: bool, exiting: Arc<AtomicBool>) {
    let mut backend: Option<Backend> = None;
    let mut readiness: Option<(mpsc::Receiver<()>, Instant)> = None;
    let mut running = false;
    let mut suspended = false;
    let mut start = true;
    loop {
        if start {
            start = false;
            status(&item, "Starting…");
            match Backend::spawn(&payload, &profile, port, development) {
                Ok((child, ready)) => {
                    backend = Some(child);
                    readiness = Some((ready, Instant::now() + Duration::from_secs(90)));
                }
                Err(e) => { status(&item, "Failed"); notice(&app, e, true); }
            }
        }
        let mut failure = None;
        if running || readiness.is_some() {
            if let Some(child) = backend.as_mut() {
                match child.exited() {
                    Ok(true) => failure = Some("The desk stopped. Open logs for details.".to_string()),
                    Err(e) => failure = Some(e),
                    _ => (),
                }
            }
        }
        if failure.is_none() {
            if let Some((ready, deadline)) = readiness.as_ref() {
                if ready.try_recv().is_ok() {
                    readiness = None;
                    running = true;
                    status(&item, "Running");
                    open(&app, port);
                } else if Instant::now() >= *deadline {
                    failure = Some("The desk did not become ready in time. Open logs for details.".into());
                }
            }
        }
        if let Some(detail) = failure {
            running = false;
            readiness = None;
            status(&item, "Failed");
            let result = stop(&mut backend);
            notice(&app, match result { Ok(()) => detail, Err(e) => format!("{detail}\n{e}") }, true);
        }
        match rx.recv_timeout(Duration::from_millis(300)) {
            Ok(Action::Open) => {
                if running { open(&app, port); }
                else { notice(&app, "The desk is not ready. Check its tray status or open the logs.", false); }
            }
            Ok(Action::Restart) => {
                if suspended { notice(&app, "An update is being installed. Wait for it to finish.", false); continue; }
                status(&item, "Stopping…");
                running = false;
                readiness = None;
                match stop(&mut backend) {
                    Ok(()) => start = true,
                    Err(e) => { status(&item, "Failed"); notice(&app, e, true); }
                }
            }
            Ok(Action::StopForUpdate(reply)) => {
                suspended = true;
                running = false;
                readiness = None;
                status(&item, "Stopping…");
                let result = stop(&mut backend);
                status(&item, if result.is_ok() { "Stopped" } else { "Failed" });
                let _ = reply.send(result);
            }
            Ok(Action::Resume) => { suspended = false; }
            Ok(Action::Quit) | Err(mpsc::RecvTimeoutError::Disconnected) => {
                if suspended { notice(&app, "An update is being installed. Wait for it to finish.", false); continue; }
                status(&item, "Stopping…");
                running = false;
                readiness = None;
                match stop(&mut backend) {
                    Ok(()) => { exiting.store(true, Ordering::SeqCst); app.exit(0); break; }
                    Err(e) => { status(&item, "Failed"); notice(&app, e, true); }
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => (),
        }
    }
}

fn check_updates(app: tauri::AppHandle) {
    let flag = app.state::<Host>().updating.clone();
    if flag.swap(true, Ordering::SeqCst) { notice(&app, "An update check is already in progress.", false); return; }
    let guard = UpdateGuard(flag);
    tauri::async_runtime::spawn(async move {
        let config = app.config().plugins.0.get("updater");
        let configured = config.and_then(|c| c.get("pubkey")).and_then(|v| v.as_str()).is_some_and(|v| !v.is_empty())
            && config.and_then(|c| c.get("endpoints")).and_then(|v| v.as_array()).is_some_and(|v| !v.is_empty());
        if !configured { notice(&app, "Updates are not configured for this build.", true); return; }
        let updater = match app.updater_builder().timeout(Duration::from_secs(30)).build() {
            Ok(value) => value,
            Err(e) => { notice(&app, format!("Cannot check for updates: {e}"), true); return; }
        };
        let update = match updater.check().await {
            Ok(Some(value)) => value,
            Ok(None) => { notice(&app, "TradingAgents is up to date.", false); return; }
            Err(e) => { notice(&app, format!("Cannot check for updates: {e}"), true); return; }
        };
        let bytes = match update.download(|_, _| {}, || {}).await {
            Ok(value) => value,
            Err(e) => { notice(&app, format!("Cannot download and verify the update: {e}"), true); return; }
        };
        let app2 = app.clone();
        app.dialog().message(format!("Version {} is ready. Stop the desk and install it now?", update.version))
            .title("TradingAgents update").buttons(MessageDialogButtons::OkCancel)
            .show(move |approved| {
                if !approved { drop(guard); return; }
                thread::spawn(move || {
                    let _guard = guard;
                    let host = app2.state::<Host>();
                    let (tx, rx) = mpsc::channel();
                    if host.tx.send(Action::StopForUpdate(tx)).is_err() {
                        notice(&app2, "Cannot stop the desk for the update.", true); return;
                    }
                    match rx.recv_timeout(Duration::from_secs(150)) {
                        Ok(Ok(())) => (),
                        result => {
                            let _ = host.tx.send(Action::Resume);
                            let detail = match result { Ok(Err(e)) => e, Err(e) => e.to_string(), _ => unreachable!() };
                            notice(&app2, format!("Cannot stop the desk for the update: {detail}"), true);
                            return;
                        }
                    }
                    host.exiting.store(true, Ordering::SeqCst);
                    match update.install(bytes) {
                        Ok(()) => { app2.restart(); }
                        Err(e) => {
                            host.exiting.store(false, Ordering::SeqCst);
                            let _ = host.tx.send(Action::Resume);
                            notice(&app2, format!("Cannot install the update: {e}. Choose Restart to start the desk again."), true);
                        }
                    }
                });
            });
    });
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(host) = app.try_state::<Host>() { let _ = host.tx.send(Action::Open); }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            if app.config().plugins.0.contains_key("updater") {
                app.handle().plugin(tauri_plugin_updater::Builder::new().build())?;
            }
            let development = app.config().identifier == "com.tradingagents.desktop.dev";
            let port = if development { 8099 } else { 8098 };
            let profile = app.path().app_local_data_dir()?;
            let payload = app.path().resource_dir()?.join("payload");
            let (tx, rx) = mpsc::channel();
            let exiting = Arc::new(AtomicBool::new(false));
            app.manage(Host { tx, exiting: exiting.clone(), updating: Arc::new(AtomicBool::new(false)) });
            let item = MenuItem::with_id(app, "status", "Starting…", false, None::<&str>)?;
            let open_item = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
            let restart = MenuItem::with_id(app, "restart", "Restart", true, None::<&str>)?;
            let update = MenuItem::with_id(app, "update", "Check for updates", true, None::<&str>)?;
            let logs = MenuItem::with_id(app, "logs", "Open logs", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&item, &open_item, &restart, &update, &logs, &quit])?;
            let log_dir = profile.join("logs");
            let icon = app.default_window_icon().ok_or("The packaged tray icon is missing")?.clone();
            TrayIconBuilder::new().icon(icon).menu(&menu)
                .tooltip(if development { "TradingAgents Development" } else { "TradingAgents" })
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {
                        "open" => { let _ = app.state::<Host>().tx.send(Action::Open); }
                        "restart" => { let _ = app.state::<Host>().tx.send(Action::Restart); }
                        "update" => check_updates(app.clone()),
                        "logs" => {
                            if let Err(e) = std::fs::create_dir_all(&log_dir) {
                                notice(app, e.to_string(), true);
                            } else if let Err(e) = app.opener().open_path(log_dir.to_string_lossy().to_string(), None::<&str>) {
                                notice(app, e.to_string(), true);
                            }
                        }
                        "quit" => { let _ = app.state::<Host>().tx.send(Action::Quit); }
                        _ => (),
                    }
                }).build(app)?;
            let handle = app.handle().clone();
            thread::spawn(move || supervisor(handle, rx, item, payload, profile, port, development, exiting));
            Ok(())
        }).build(tauri::generate_context!()).expect("Cannot start TradingAgents desktop host");
    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            let host = app.state::<Host>();
            if !host.exiting.load(Ordering::SeqCst) {
                api.prevent_exit();
                let _ = host.tx.send(Action::Quit);
            }
        }
    });
}
