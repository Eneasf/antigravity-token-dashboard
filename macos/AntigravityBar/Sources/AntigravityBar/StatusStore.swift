import Foundation
import SwiftUI
import AppKit

public class StatusStore: ObservableObject {
    @Published public var status: StatusModel = StatusModel()
    @Published public var lastUpdated: Date = Date()
    @Published public var isRefreshing: Bool = false
    @Published public var isWatcherRunning: Bool = false

    public let statusPath: URL
    public var customSignalURL: URL? = nil
    private var fileSource: DispatchSourceFileSystemObject?
    private var fileDescriptor: Int32 = -1
    private var timer: Timer?

    public var signalPath: URL {
        return customSignalURL ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".antigravity_refresh_requested")
    }

    public init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        self.statusPath = home.appendingPathComponent(".antigravity_quota_status.json")

        loadStatus()
        checkWatcherStatus()
        startFileWatcher()

        // Fallback heartbeat timer on main loop (re-arms file watcher if started before file existed)
        self.timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.loadStatus()
            self.checkWatcherStatus()
            if self.fileSource == nil || self.fileDescriptor < 0 {
                self.startFileWatcher()
            }
        }
    }

    public init(initialStatus: StatusModel, customStatusPath: URL? = nil) {
        let home = FileManager.default.homeDirectoryForCurrentUser
        self.statusPath = customStatusPath ?? home.appendingPathComponent(".antigravity_quota_status.json")
        self.status = initialStatus
        self.lastUpdated = Date()
        self.isWatcherRunning = (initialStatus.watcher?.pid ?? 0) > 0
    }

    deinit {
        stopFileWatcher()
        timer?.invalidate()
    }

    private static let isoFormatterWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let isoFormatterStandard: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    public static func parseISO8601Date(_ string: String) -> Date? {
        return isoFormatterWithFractional.date(from: string) ?? isoFormatterStandard.date(from: string)
    }

    public func checkWatcherStatus() {
        guard let heartbeatStr = status.watcher?.heartbeat_utc,
              let heartbeatDate = Self.parseISO8601Date(heartbeatStr) else {
            let update = { self.isWatcherRunning = false }
            if Thread.isMainThread {
                update()
            } else {
                DispatchQueue.main.async(execute: update)
            }
            return
        }

        let diff = Date().timeIntervalSince(heartbeatDate)
        let running = (diff <= 30.0 && diff >= -5.0)
        let update = { self.isWatcherRunning = running }
        if Thread.isMainThread {
            update()
        } else {
            DispatchQueue.main.async(execute: update)
        }
    }

    public func loadStatus() {
        checkWatcherStatus()
        guard FileManager.default.fileExists(atPath: statusPath.path) else { return }
        do {
            let data = try Data(contentsOf: statusPath)
            let decoder = JSONDecoder()
            let newStatus = try decoder.decode(StatusModel.self, from: data)
            let apply = {
                self.status = newStatus
                self.lastUpdated = Date()
                self.checkWatcherStatus()
            }
            if Thread.isMainThread {
                apply()
            } else {
                DispatchQueue.main.async(execute: apply)
            }
        } catch {
            // Tolerate transient lock or partial write
        }
    }

    public func startFileWatcher() {
        stopFileWatcher()

        guard FileManager.default.fileExists(atPath: statusPath.path) else { return }

        let fd = open(statusPath.path, O_EVTONLY)
        guard fd >= 0 else { return }
        self.fileDescriptor = fd

        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fd,
            eventMask: [.write, .delete, .rename, .extend, .attrib],
            queue: DispatchQueue.main
        )

        source.setEventHandler { [weak self] in
            guard let self = self else { return }
            self.loadStatus()
            let events = source.data
            if events.contains(.delete) || events.contains(.rename) {
                // File was replaced atomically (e.g. via os.replace); re-arm watcher immediately on new inode
                self.startFileWatcher()
            }
        }

        source.setCancelHandler {
            close(fd)
        }

        self.fileSource = source
        source.resume()
    }

    public func stopFileWatcher() {
        if let s = fileSource {
            s.cancel()
            fileSource = nil
        }
        fileDescriptor = -1
    }

    public func refreshNow() {
        guard !isRefreshing else { return }
        DispatchQueue.main.async { self.isRefreshing = true }

        let targetSignalURL = self.signalPath
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }

            // Signal the watcher daemon via ~/.antigravity_refresh_requested (C1 / AGENTS.md §2.5)
            // Never touch ~/Documents from AntigravityBar to avoid macOS TCC main-thread blocks.
            try? "".write(to: targetSignalURL, atomically: true, encoding: .utf8)

            Thread.sleep(forTimeInterval: 0.8)

            DispatchQueue.main.async {
                self.loadStatus()
                self.isRefreshing = false
            }
        }
    }

    public static func constructDashboardURL(targetPath: String, tab: String? = nil) -> String {
        var fileUrlStr = URL(fileURLWithPath: targetPath).absoluteString
        if let tab = tab, !tab.isEmpty {
            let cleanTab = tab.hasPrefix("#") ? String(tab.dropFirst()) : tab
            fileUrlStr += "#\(cleanTab)"
        }
        return fileUrlStr
    }

    public func openDashboard(tab: String? = nil) {
        let rawPath = status.dashboard_path
        DispatchQueue.global(qos: .userInitiated).async {
            let targetPath: String
            if let p = rawPath, !p.isEmpty {
                targetPath = p
            } else if let envRepo = ProcessInfo.processInfo.environment["ANTIGRAVITY_DASHBOARD_REPO"], !envRepo.isEmpty {
                targetPath = URL(fileURLWithPath: envRepo).appendingPathComponent("dashboard/index.html").path
            } else {
                return
            }

            let fileUrlStr = Self.constructDashboardURL(targetPath: targetPath, tab: tab)
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/open")
            proc.arguments = [fileUrlStr]
            try? proc.run()
        }
    }
}
