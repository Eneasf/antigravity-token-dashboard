import AppKit
import Darwin

// Enforce single-instance execution via non-blocking POSIX file lock
let lockPath = "/tmp/antigravitybar_\(getuid()).lock"
let lockFd = open(lockPath, O_CREAT | O_RDWR, 0o666)
if lockFd >= 0 {
    if flock(lockFd, LOCK_EX | LOCK_NB) != 0 {
        // Another instance is already running; terminate silently
        exit(0)
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var store: StatusStore?
    var statusBarController: StatusBarController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Run as accessory app (no Dock icon, menu bar only)
        NSApp.setActivationPolicy(.accessory)

        let store = StatusStore()
        self.store = store
        self.statusBarController = StatusBarController(store: store)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
