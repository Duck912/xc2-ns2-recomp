// SPDX-License-Identifier: GPL-3.0-or-later
//! The DLSS files from NVIDIA. The runtime runs DLSS (and DLSS frame generation, Reflex) through NVIDIA Streamline, whose DLLs are not
//! part of the release package: this downloads NVIDIA's own Streamline SDK release from GitHub - the version the runtime's headers are
//! (runtime/third_party/nvidia_streamline/README.txt) - checks its size and SHA-256, and puts the DLLs the game loads, with NVIDIA's
//! licence texts, into upscalers/streamline next to the game, where the runtime and the file check (main.rs upscaler_files) look.
//! Only the files below are kept; the rest of the SDK (headers, samples, debug builds) and the zip are removed afterwards.

use serde::Serialize;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

/// NVIDIA-RTX/Streamline release v2.14.16 (2026-10-16): the SDK zip, as GitHub lists it.
pub const VERSION: &str = "2.14.16";
const URL: &str = "https://github.com/NVIDIA-RTX/Streamline/releases/download/v2.14.16/streamline-sdk-v2.14.16.zip";
const ZIP: &str = "streamline-sdk-v2.14.16.zip";
const SIZE: u64 = 276_016_170;
const SHA256: &str = "32041e51db0cab709a271b72a352281b690c2abbd669a827809401a5dd23956b";

/// What is taken from the zip: the DLLs the runtime loads (temporal_dlss.cpp: DLSS, DLSS-G, Reflex, PCL - the same set main.rs checks
/// for frame generation), and the licence texts that come with them. Paths inside the zip; they land flat in upscalers/streamline.
const FILES: [&str; 13] = [
    "bin/x64/sl.interposer.dll",
    "bin/x64/sl.common.dll",
    "bin/x64/sl.dlss.dll",
    "bin/x64/nvngx_dlss.dll",
    "bin/x64/sl.dlss_g.dll",
    "bin/x64/nvngx_dlssg.dll",
    "bin/x64/sl.reflex.dll",
    "bin/x64/sl.pcl.dll",
    "bin/x64/NvLowLatencyVk.dll",
    "bin/x64/nvngx_dlss.license.txt",
    "bin/x64/reflex.license.txt",
    "license.txt",
    "3rd-party-licenses.md",
];
const AGENT: &str = "xc2-launcher";
/// Downloads and the unpacked zip, inside the folder the files go to (removed when done).
const WORK: &str = ".download";

#[derive(Serialize, Clone, Default)]
pub struct Status {
    /// idle, running, done, error
    pub state: String,
    /// download, verify, unpack, install
    pub phase: String,
    pub done: u64,
    pub total: u64,
    pub message: String,
}

#[derive(Default)]
pub struct Shared {
    pub status: Mutex<Status>,
    pub cancel: AtomicBool,
}

/// upscalers/streamline next to the game: the first folder the runtime searches by default.
pub fn dest(game_dir: &Path) -> PathBuf {
    game_dir.join("upscalers").join("streamline")
}

fn system_tool(name: &str) -> PathBuf {
    if !cfg!(windows) {
        return PathBuf::from(name.trim_end_matches(".exe")); // from PATH
    }
    let root = std::env::var_os("SystemRoot").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(r"C:\Windows"));
    let p = root.join("System32").join(name);
    if p.is_file() { p } else { PathBuf::from(name) }
}

fn sha256_file(path: &Path) -> Result<String, String> {
    use sha2::{Digest, Sha256};
    let mut f = fs::File::open(path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 20];
    loop {
        let n = f.read(&mut buf).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    Ok(h.finalize().iter().map(|b| format!("{b:02x}")).collect())
}

pub struct Run<'a> {
    pub shared: &'a Shared,
    pub game_dir: PathBuf,
}

impl Run<'_> {
    fn set(&self, phase: &str, done: u64, total: u64, message: &str) {
        let mut st = self.shared.status.lock().unwrap();
        st.state = "running".into();
        st.phase = phase.into();
        st.done = done;
        st.total = total;
        st.message = message.into();
    }

    fn cancelled(&self) -> Result<(), String> {
        if self.shared.cancel.load(Ordering::SeqCst) { Err("Download cancelled.".into()) } else { Ok(()) }
    }

    pub fn run(&self) -> Result<Status, String> {
        let dest = dest(&self.game_dir);
        let work = dest.join(WORK);
        fs::create_dir_all(&work).map_err(|e| format!("cannot create {}: {e}", work.display()))?;
        let result = self.download(&work).and_then(|zip| {
            self.cancelled()?;
            self.unpack(&zip, &work.join("stage"))?;
            self.cancelled()?;
            self.set("install", 0, 0, "Installing");
            for f in FILES {
                let name = Path::new(f).file_name().unwrap();
                let from = work.join("stage").join(f);
                fs::copy(&from, dest.join(name)).map_err(|e| format!("cannot copy {} to {}: {e}", from.display(), dest.display()))?;
            }
            Ok(())
        });
        let _ = fs::remove_dir_all(&work);   // the zip and the unpacked SDK, whatever happened
        result?;
        Ok(Status {
            state: "done".into(),
            phase: "done".into(),
            message: format!("NVIDIA Streamline {VERSION} is installed in {}.", dest.display()),
            ..Default::default()
        })
    }

    fn download(&self, work: &Path) -> Result<PathBuf, String> {
        let zip = work.join(ZIP);
        let part = work.join(format!("{ZIP}.part"));
        let _ = fs::remove_file(&part);
        let mut c = Command::new(system_tool("curl.exe"));
        c.args(["--fail", "--location", "--silent", "--show-error", "--user-agent", AGENT]);
        c.args(["--retry", "3", "--speed-limit", "1024", "--speed-time", "60", "--output"]);   // a stalled connection fails after a minute
        c.arg(&part).arg(URL);
        crate::setup::quiet(&mut c);
        let mut child = c.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped()).spawn().map_err(|e| format!("cannot run curl.exe: {e}"))?;
        let mb = |b: u64| b as f64 / (1024.0 * 1024.0);
        let status = loop {
            if let Some(s) = child.try_wait().map_err(|e| e.to_string())? {
                break s;
            }
            if self.shared.cancel.load(Ordering::SeqCst) {
                let _ = child.kill();
                let _ = child.wait();
                return Err("Download cancelled.".into());
            }
            let got = fs::metadata(&part).map(|m| m.len()).unwrap_or(0);
            self.set("download", got, SIZE, &format!("Downloading NVIDIA Streamline {VERSION} ({:.0} of {:.0} MiB)", mb(got), mb(SIZE)));
            std::thread::sleep(Duration::from_millis(250));
        };
        if !status.success() {
            let mut err = String::new();
            if let Some(mut e) = child.stderr.take() {
                let _ = e.read_to_string(&mut err);
            }
            return Err(format!("The download failed: {}", err.trim()));
        }
        self.set("verify", 0, 0, "Checking the download");
        let size = fs::metadata(&part).map(|m| m.len()).unwrap_or(0);
        if size != SIZE {
            return Err(format!("The download has {size} bytes, NVIDIA's file has {SIZE}. Try again."));
        }
        let got = sha256_file(&part)?;
        if got != SHA256 {
            return Err(format!("The download is damaged (SHA-256 {got}, expected {SHA256}). Try again."));
        }
        fs::rename(&part, &zip).map_err(|e| format!("cannot rename {}: {e}", part.display()))?;
        Ok(zip)
    }

    /// Unpacks only FILES from the zip into `stage`.
    fn unpack(&self, zip: &Path, stage: &Path) -> Result<(), String> {
        self.set("unpack", 0, 0, "Unpacking");
        fs::create_dir_all(stage).map_err(|e| format!("cannot create {}: {e}", stage.display()))?;
        // Windows' tar (bsdtar) reads zips; GNU tar on Linux does not, unzip does. Only the files the game needs are taken.
        let mut c = if cfg!(windows) {
            let mut c = Command::new(system_tool("tar.exe"));
            c.arg("-xmf").arg(zip).arg("-C").arg(stage).args(FILES);   // -m: no file times (one the file system cannot hold must not fail it)
            c
        } else {
            let mut c = Command::new("unzip");
            c.arg("-o").arg("-q").arg(zip).args(FILES).arg("-d").arg(stage);
            c
        };
        crate::setup::quiet(&mut c);
        let out = c.stdin(Stdio::null()).output().map_err(|e| format!("cannot unpack (tar.exe / unzip): {e}"))?;
        for f in FILES {
            if !stage.join(f).is_file() {
                return Err(format!("Unpacking failed ({f} is missing): {}", String::from_utf8_lossy(&out.stderr).trim()));
            }
        }
        Ok(())
    }
}
