import AppKit
import SwiftUI
import Combine

public enum MenuBarDensity: String, CaseIterable {
    case adaptive = "adaptive"
    case compact = "compact"
    case nano = "nano"
    case gauge = "gauge"
    case pro = "pro"

    public var displayName: String {
        switch self {
        case .adaptive: return "Adaptive (Dynamic Ticker)"
        case .compact: return "Compact (~110px)"
        case .nano: return "Nano (~65px)"
        case .gauge: return "Gauge / Minimal (~45px)"
        case .pro: return "Pro / Full Ticker (~190px)"
        }
    }
}

public class StatusBarController {
    private var statusItem: NSStatusItem
    private var popover: NSPopover
    private var store: StatusStore
    private var cancellable: AnyCancellable?

    public var density: MenuBarDensity {
        get {
            let val = UserDefaults.standard.string(forKey: "AntigravityBarDensity") ?? MenuBarDensity.adaptive.rawValue
            return MenuBarDensity(rawValue: val) ?? .adaptive
        }
        set {
            UserDefaults.standard.set(newValue.rawValue, forKey: "AntigravityBarDensity")
            updateTitle()
        }
    }

    public init(store: StatusStore) {
        self.store = store
        self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        self.popover = NSPopover()

        setupPopover()
        setupStatusButton()
        bindStore()
    }

    private func setupPopover() {
        popover.behavior = .transient
        popover.animates = true
        let contentView = PopoverContentView(store: store)
        popover.contentViewController = NSHostingController(rootView: contentView)
    }

    private func setupStatusButton() {
        guard let button = statusItem.button else { return }
        button.target = self
        button.action = #selector(handleStatusBarClick(_:))
        button.sendAction(on: [.leftMouseUp, .rightMouseUp])

        let rightClick = NSClickGestureRecognizer(target: self, action: #selector(handleRightClickGesture(_:)))
        rightClick.buttonMask = 0x2
        button.addGestureRecognizer(rightClick)

        updateTitle()
    }

    private func bindStore() {
        cancellable = store.$status
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                self?.updateTitle()
            }
    }

    public func updateTitle() {
        guard let button = statusItem.button else { return }

        let s = store.status
        let primaryTrack = s.resolvedTracks.first(where: { $0.is_primary }) ?? s.resolvedTracks.first
        let primary5h = primaryTrack?.windows.first(where: { $0.window_id == "5h" })
        let primaryWk = primaryTrack?.windows.first(where: { $0.window_id == "weekly" })

        let gem5h = Int(round(primary5h?.remaining_pct ?? s.gemini5hRem))
        let gemWk = Int(round(primaryWk?.remaining_pct ?? s.geminiWkRem))

        let font = NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .medium)
        let weeklyAttrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: s.weeklyHealthNSColor
        ]
        let burstAttrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: s.burstHealthNSColor
        ]
        let neutralAttrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: NSColor.labelColor
        ]

        let fullAttr = NSMutableAttributedString()

        // Dynamic Epoch Number Badge (E1..E5) (Milestone 86)
        let epoch = s.compaction_epoch ?? s.current_session?.compaction_epoch ?? 1
        let badgeFont = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .bold)
        let epochColor: NSColor
        if epoch <= 2 {
            // Epoch 1 & 2: Green (#34D399 / systemGreen)
            epochColor = NSColor(srgbRed: 52/255.0, green: 211/255.0, blue: 153/255.0, alpha: 1.0)
        } else if epoch == 3 {
            // Epoch 3: Amber/Orange (#FBBF24 / systemOrange)
            epochColor = NSColor(srgbRed: 251/255.0, green: 191/255.0, blue: 36/255.0, alpha: 1.0)
        } else {
            // Epoch 4+: Red (#EF4444 / systemRed)
            epochColor = NSColor(srgbRed: 239/255.0, green: 68/255.0, blue: 68/255.0, alpha: 1.0)
        }

        let showStreamingDot = s.isStreamingActive

        switch density {
        case .gauge:
            // Minimal ~45px: Epoch + 5h Headroom
            if showStreamingDot {
                let dotAttrs: [NSAttributedString.Key: Any] = [
                    .font: NSFont.systemFont(ofSize: 8, weight: .bold),
                    .foregroundColor: NSColor.systemGreen
                ]
                fullAttr.append(NSAttributedString(string: "● ", attributes: dotAttrs))
            }
            fullAttr.append(NSAttributedString(string: "E\(epoch) ", attributes: [
                .font: badgeFont,
                .foregroundColor: epochColor
            ]))
            if let boltImg = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: "5h Burst") {
                let config = NSImage.SymbolConfiguration(pointSize: 10, weight: .bold)
                let configuredBolt = boltImg.withSymbolConfiguration(config) ?? boltImg
                let boltAttachment = NSTextAttachment()
                boltAttachment.image = configuredBolt
                let boltStr = NSMutableAttributedString(attachment: boltAttachment)
                boltStr.addAttributes(burstAttrs, range: NSRange(location: 0, length: boltStr.length))
                fullAttr.append(boltStr)
            }
            fullAttr.append(NSAttributedString(string: "\(gem5h)%", attributes: burstAttrs))

        case .nano:
            // Nano ~65px: E1 60% ⚡85%
            if showStreamingDot {
                let dotAttrs: [NSAttributedString.Key: Any] = [
                    .font: NSFont.systemFont(ofSize: 8, weight: .bold),
                    .foregroundColor: NSColor.systemGreen
                ]
                fullAttr.append(NSAttributedString(string: "● ", attributes: dotAttrs))
            }
            fullAttr.append(NSAttributedString(string: "E\(epoch) ", attributes: [
                .font: badgeFont,
                .foregroundColor: epochColor
            ]))
            fullAttr.append(NSAttributedString(string: "\(gemWk)% ", attributes: weeklyAttrs))
            if let boltImg = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: "5h Burst") {
                let config = NSImage.SymbolConfiguration(pointSize: 10, weight: .bold)
                let configuredBolt = boltImg.withSymbolConfiguration(config) ?? boltImg
                let boltAttachment = NSTextAttachment()
                boltAttachment.image = configuredBolt
                let boltStr = NSMutableAttributedString(attachment: boltAttachment)
                boltStr.addAttributes(burstAttrs, range: NSRange(location: 0, length: boltStr.length))
                fullAttr.append(boltStr)
            }
            fullAttr.append(NSAttributedString(string: "\(gem5h)%", attributes: burstAttrs))

        case .compact:
            // Compact ~110px: E1 · 🗓 60% ⚡ 85% (no parenthetical raw tokens)
            if showStreamingDot {
                let dotAttrs: [NSAttributedString.Key: Any] = [
                    .font: NSFont.systemFont(ofSize: 8.5, weight: .bold),
                    .foregroundColor: NSColor.systemGreen
                ]
                fullAttr.append(NSAttributedString(string: "● ", attributes: dotAttrs))
            }
            fullAttr.append(NSAttributedString(string: "E\(epoch)  ", attributes: [
                .font: badgeFont,
                .foregroundColor: epochColor
            ]))
            if let calImg = NSImage(systemSymbolName: "calendar", accessibilityDescription: "Weekly Allowance") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .medium)
                let configuredCal = calImg.withSymbolConfiguration(config) ?? calImg
                let calAttachment = NSTextAttachment()
                calAttachment.image = configuredCal
                let calStr = NSMutableAttributedString(attachment: calAttachment)
                calStr.addAttributes(weeklyAttrs, range: NSRange(location: 0, length: calStr.length))
                fullAttr.append(calStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gemWk)%  ", attributes: weeklyAttrs))
            if let boltImg = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: "5h Burst") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .bold)
                let configuredBolt = boltImg.withSymbolConfiguration(config) ?? boltImg
                let boltAttachment = NSTextAttachment()
                boltAttachment.image = configuredBolt
                let boltStr = NSMutableAttributedString(attachment: boltAttachment)
                boltStr.addAttributes(burstAttrs, range: NSRange(location: 0, length: boltStr.length))
                fullAttr.append(boltStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gem5h)%", attributes: burstAttrs))

        case .adaptive:
            // Adaptive (Default): Compact when idle (~110px); reveals live velocity ticker only when actively streaming (~145px)
            if showStreamingDot {
                let dotAttrs: [NSAttributedString.Key: Any] = [
                    .font: NSFont.systemFont(ofSize: 8.5, weight: .bold),
                    .foregroundColor: NSColor.systemGreen
                ]
                fullAttr.append(NSAttributedString(string: "● ", attributes: dotAttrs))
            }
            fullAttr.append(NSAttributedString(string: "E\(epoch)  ", attributes: [
                .font: badgeFont,
                .foregroundColor: epochColor
            ]))
            if let calImg = NSImage(systemSymbolName: "calendar", accessibilityDescription: "Weekly Allowance") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .medium)
                let configuredCal = calImg.withSymbolConfiguration(config) ?? calImg
                let calAttachment = NSTextAttachment()
                calAttachment.image = configuredCal
                let calStr = NSMutableAttributedString(attachment: calAttachment)
                calStr.addAttributes(weeklyAttrs, range: NSRange(location: 0, length: calStr.length))
                fullAttr.append(calStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gemWk)%  ", attributes: weeklyAttrs))
            if let boltImg = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: "5h Burst") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .bold)
                let configuredBolt = boltImg.withSymbolConfiguration(config) ?? boltImg
                let boltAttachment = NSTextAttachment()
                boltAttachment.image = configuredBolt
                let boltStr = NSMutableAttributedString(attachment: boltAttachment)
                boltStr.addAttributes(burstAttrs, range: NSRange(location: 0, length: boltStr.length))
                fullAttr.append(boltStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gem5h)%", attributes: burstAttrs))

            if s.isStreamingActive {
                fullAttr.append(NSAttributedString(string: "  ", attributes: neutralAttrs))
                if let speedImg = NSImage(systemSymbolName: "arrow.up.right", accessibilityDescription: "Burn Speed") {
                    let config = NSImage.SymbolConfiguration(pointSize: 9.5, weight: .semibold)
                    let configuredSpeed = speedImg.withSymbolConfiguration(config) ?? speedImg
                    let speedAttachment = NSTextAttachment()
                    speedAttachment.image = configuredSpeed
                    fullAttr.append(NSAttributedString(attachment: speedAttachment))
                }
                let rateColor = (s.is_streaming ?? false) ? NSColor.systemGreen : NSColor.secondaryLabelColor
                let rateFont = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .semibold)
                let rateAttrs: [NSAttributedString.Key: Any] = [
                    .font: rateFont,
                    .foregroundColor: rateColor
                ]
                fullAttr.append(NSAttributedString(string: " \(s.formattedBurnRate)", attributes: rateAttrs))
            }

        case .pro:
            // Pro / Full Ticker (~180px): Always shows Epoch, Weekly, 5h, and Burn Speed if available
            if showStreamingDot {
                let dotAttrs: [NSAttributedString.Key: Any] = [
                    .font: NSFont.systemFont(ofSize: 8.5, weight: .bold),
                    .foregroundColor: NSColor.systemGreen
                ]
                fullAttr.append(NSAttributedString(string: "● ", attributes: dotAttrs))
            }
            fullAttr.append(NSAttributedString(string: "E\(epoch)  ", attributes: [
                .font: badgeFont,
                .foregroundColor: epochColor
            ]))
            if let calImg = NSImage(systemSymbolName: "calendar", accessibilityDescription: "Weekly Allowance") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .medium)
                let configuredCal = calImg.withSymbolConfiguration(config) ?? calImg
                let calAttachment = NSTextAttachment()
                calAttachment.image = configuredCal
                let calStr = NSMutableAttributedString(attachment: calAttachment)
                calStr.addAttributes(weeklyAttrs, range: NSRange(location: 0, length: calStr.length))
                fullAttr.append(calStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gemWk)%  ", attributes: weeklyAttrs))
            if let boltImg = NSImage(systemSymbolName: "bolt.fill", accessibilityDescription: "5h Burst") {
                let config = NSImage.SymbolConfiguration(pointSize: 10.5, weight: .bold)
                let configuredBolt = boltImg.withSymbolConfiguration(config) ?? boltImg
                let boltAttachment = NSTextAttachment()
                boltAttachment.image = configuredBolt
                let boltStr = NSMutableAttributedString(attachment: boltAttachment)
                boltStr.addAttributes(burstAttrs, range: NSRange(location: 0, length: boltStr.length))
                fullAttr.append(boltStr)
            }
            fullAttr.append(NSAttributedString(string: " \(gem5h)%", attributes: burstAttrs))

            let rate = s.recent_burn_rate_tok_per_min ?? 0
            if rate > 0 || (s.is_streaming ?? false) {
                fullAttr.append(NSAttributedString(string: "  ", attributes: neutralAttrs))
                if let speedImg = NSImage(systemSymbolName: "arrow.up.right", accessibilityDescription: "Burn Speed") {
                    let config = NSImage.SymbolConfiguration(pointSize: 9.5, weight: .semibold)
                    let configuredSpeed = speedImg.withSymbolConfiguration(config) ?? speedImg
                    let speedAttachment = NSTextAttachment()
                    speedAttachment.image = configuredSpeed
                    fullAttr.append(NSAttributedString(attachment: speedAttachment))
                }
                let rateColor = (s.is_streaming ?? false) ? NSColor.systemGreen : NSColor.secondaryLabelColor
                let rateFont = NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .semibold)
                let rateAttrs: [NSAttributedString.Key: Any] = [
                    .font: rateFont,
                    .foregroundColor: rateColor
                ]
                fullAttr.append(NSAttributedString(string: " \(s.formattedBurnRate)", attributes: rateAttrs))
            }
        }

        button.attributedTitle = fullAttr
    }

    @objc private func handleStatusBarClick(_ sender: AnyObject?) {
        guard let event = NSApp.currentEvent else {
            togglePopover(sender)
            return
        }

        if event.type == .rightMouseUp || (event.type == .leftMouseUp && event.modifierFlags.contains(.control)) {
            showContextMenu(with: event)
        } else {
            togglePopover(sender)
        }
    }

    @objc private func handleRightClickGesture(_ recognizer: NSClickGestureRecognizer) {
        guard let event = NSApp.currentEvent else { return }
        showContextMenu(with: event)
    }

    private func showContextMenu(with event: NSEvent) {
        guard let button = statusItem.button else { return }

        if popover.isShown {
            popover.performClose(nil)
        }

        store.checkWatcherStatus()

        let menu = NSMenu()

        let openDashboardItem = NSMenuItem(title: "Open Dashboard", action: #selector(openDashboardAction), keyEquivalent: "d")
        openDashboardItem.target = self
        if let globe = NSImage(systemSymbolName: "globe", accessibilityDescription: nil) {
            openDashboardItem.image = globe
        }
        menu.addItem(openDashboardItem)

        let reloadItem = NSMenuItem(title: "Reload Telemetry", action: #selector(reloadTelemetryAction), keyEquivalent: "r")
        reloadItem.target = self
        if let arrow = NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil) {
            reloadItem.image = arrow
        }
        menu.addItem(reloadItem)

        menu.addItem(NSMenuItem.separator())

        // Menu Bar Style Submenu (Milestone Density Switcher)
        let densityMenu = NSMenu()
        for mode in MenuBarDensity.allCases {
            let item = NSMenuItem(title: mode.displayName, action: #selector(changeDensityAction(_:)), keyEquivalent: "")
            item.target = self
            item.representedObject = mode.rawValue
            item.state = (mode == density) ? .on : .off
            densityMenu.addItem(item)
        }
        let densityItem = NSMenuItem(title: "Menu Bar Style", action: nil, keyEquivalent: "")
        if let sliderIcon = NSImage(systemSymbolName: "slider.horizontal.3", accessibilityDescription: nil) {
            densityItem.image = sliderIcon
        }
        densityItem.submenu = densityMenu
        menu.addItem(densityItem)

        menu.addItem(NSMenuItem.separator())

        let watcherStatusTitle = store.isWatcherRunning ? "● Watcher Daemon: Live" : "⚠️ Watcher Daemon: Inactive"
        let watcherItem = NSMenuItem(title: watcherStatusTitle, action: nil, keyEquivalent: "")
        watcherItem.isEnabled = false
        menu.addItem(watcherItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit AntigravityBar", action: #selector(quitAppAction), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        NSMenu.popUpContextMenu(menu, with: event, for: button)
    }

    @objc private func changeDensityAction(_ sender: NSMenuItem) {
        if let raw = sender.representedObject as? String, let mode = MenuBarDensity(rawValue: raw) {
            self.density = mode
        }
    }

    @objc private func openDashboardAction() {
        store.openDashboard()
    }

    @objc private func reloadTelemetryAction() {
        store.refreshNow()
        updateTitle()
    }

    @objc private func quitAppAction() {
        NSApplication.shared.terminate(nil)
    }

    @objc private func togglePopover(_ sender: AnyObject?) {
        guard let button = statusItem.button else { return }

        if popover.isShown {
            popover.performClose(sender)
        } else {
            store.loadStatus()
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }
}
