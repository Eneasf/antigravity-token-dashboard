import Foundation
import SwiftUI

enum PopoverDesignTokens {
    static let popoverWidth: CGFloat = 385
    static let outerPadding: CGFloat = 14
    static let sectionSpacing: CGFloat = 10
    static let maxVisibleSwarmGroups: Int = 2
    static let maxVisibleSubagentsPerGroup: Int = 2
    static let maxVisibleHistoricalSessions: Int = 3
    static let cardCornerRadius: CGFloat = 7
    static let badgeFontSize: CGFloat = 10
    static let captionFontSize: CGFloat = 11
    static let bodyFontSize: CGFloat = 11.5
    static let sectionTitleFontSize: CGFloat = 12.5
    static let emeraldAccent = Color(red: 16/255.0, green: 185/255.0, blue: 129/255.0)
}

public struct PopoverContentView: View {
    @ObservedObject var store: StatusStore
    @State private var isSessionsExpanded: Bool = false
    @State private var isSwarmsExpanded: Bool = false
    @State private var isCopied: Bool = false

    private static let isoFormatterWithFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let isoFormatterStandard: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    public static func parseDate(epoch: Double?, utc: String?) -> Date? {
        if let epoch = epoch, epoch > 0 {
            return Date(timeIntervalSince1970: epoch)
        }
        guard let utc = utc, !utc.isEmpty else { return nil }
        return isoFormatterWithFractional.date(from: utc) ?? isoFormatterStandard.date(from: utc)
    }

    public static func formatRelativeReset(epoch: Double?, utc: String?) -> String? {
        guard let date = parseDate(epoch: epoch, utc: utc) else { return nil }
        let diff = date.timeIntervalSinceNow
        if diff <= 0 { return "Refreshing now" }
        let hours = Int(diff) / 3600
        let minutes = (Int(diff) % 3600) / 60
        if hours >= 24 {
            let days = hours / 24
            let remH = hours % 24
            return "\(days)d \(remH)h remaining"
        } else if hours > 0 {
            return "\(hours)h \(minutes)m remaining"
        } else {
            return "\(max(1, minutes))m remaining"
        }
    }

    public init(store: StatusStore, isSessionsExpanded: Bool = false, isSwarmsExpanded: Bool = false) {
        self.store = store
        self._isSwarmsExpanded = State(initialValue: isSwarmsExpanded)
        self._isSessionsExpanded = State(initialValue: isSwarmsExpanded ? false : isSessionsExpanded)
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(alignment: .leading, spacing: PopoverDesignTokens.sectionSpacing) {
                headerSection
                stalenessWarningSection
                Divider()
                primaryTrackSection
                LiveTokenTickerCard(status: store.status)
                activeSessionContextSection
                activeSwarmsSection
                secondaryTracksSection
                activeContextSection
                historicalSessionsSection
                Divider()
                footerSection
            }
            .padding(PopoverDesignTokens.outerPadding)
        }
        .frame(width: PopoverDesignTokens.popoverWidth)
        .frame(maxHeight: 680)
    }

    // MARK: - Header
    private var headerSection: some View {
        HStack(alignment: .center, spacing: 8) {
            Image(systemName: "sparkles")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(.accentColor)

            VStack(alignment: .leading, spacing: 1) {
                Text("Antigravity Quota")
                    .font(.system(size: 13, weight: .bold))
                Text(store.status.resolvedPlan.name ?? store.status.plan_name ?? "Google AI Ultra (5x)")
                    .font(.system(size: PopoverDesignTokens.captionFontSize))
                    .foregroundColor(.secondary)
            }

            Spacer()

            creditPill

            // Refresh Button with live Activity Spinner
            Button(action: {
                store.refreshNow()
            }) {
                if store.isRefreshing {
                    ProgressView()
                        .controlSize(.small)
                        .frame(width: 14, height: 14)
                } else {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.secondary)
                }
            }
            .buttonStyle(.plain)
            .disabled(store.isRefreshing)
            .help("Refresh telemetry now (⌘R)")

            // Dynamic Epoch Badge Chip (E1..E5)
            let epoch = store.status.compaction_epoch ?? store.status.current_session?.compaction_epoch ?? 1
            Text("E\(epoch)")
                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                .padding(.horizontal, 5)
                .padding(.vertical, 2.5)
                .background(Color(NSColor.separatorColor).opacity(0.18))
                .foregroundColor(epoch <= 2 ? Color.green : (epoch == 3 ? Color.orange : Color.red))
                .cornerRadius(4)

            StatusBadgeView(status: store.status)
        }
    }

    // MARK: - Google One AI Credit Balance Pill (Linked to Primary / Header)
    @ViewBuilder
    private var creditPill: some View {
        let plan = store.status.resolvedPlan
        if let rem = plan.credits_remaining, let pool = plan.credit_pool {
            Button(action: {
                store.openDashboard(tab: "tab-billing")
            }) {
                HStack(spacing: 3) {
                    Image(systemName: "creditcard")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize))
                        .foregroundColor(.secondary)
                    Text("\(rem.formatted()) / \(pool.formatted())")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                    if let gbp = plan.credit_balance_gbp {
                        Text(String(format: "(£%.2f)", gbp))
                            .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .regular, design: .monospaced))
                            .foregroundColor(.secondary.opacity(0.8))
                    }
                }
                .padding(.horizontal, 5)
                .padding(.vertical, 2)
                .background(Color(NSColor.separatorColor).opacity(0.12))
                .cornerRadius(3.5)
            }
            .buttonStyle(.plain)
            .help("Google One AI Credit Balance. Click to open billing.")
        } else if let credStr = store.status.credit_balance, !credStr.isEmpty {
            Button(action: {
                store.openDashboard(tab: "tab-billing")
            }) {
                HStack(spacing: 3) {
                    Image(systemName: "creditcard")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize))
                        .foregroundColor(.secondary)
                    Text(credStr)
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                .padding(.horizontal, 5)
                .padding(.vertical, 2)
                .background(Color(NSColor.separatorColor).opacity(0.12))
                .cornerRadius(3.5)
            }
            .buttonStyle(.plain)
            .help("Google One AI Credit Balance. Click to open billing.")
        }
    }

    // MARK: - Staleness Warning
    @ViewBuilder
    private var stalenessWarningSection: some View {
        let age = dataAgeSeconds
        if age > 120.0 {
            HStack(spacing: 4) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize))
                    .foregroundColor(.orange)
                Text("Data updated \(formatAge(age)) ago")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                    .foregroundColor(.orange)
                Spacer()
                Button("Refresh") {
                    store.refreshNow()
                }
                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                .buttonStyle(.plain)
                .foregroundColor(.orange)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Color.orange.opacity(0.12))
            .cornerRadius(4)
        }
    }

    private var dataAgeSeconds: Double {
        if let epoch = store.status.generated_at_epoch, epoch > 0 {
            return max(0, Date().timeIntervalSince1970 - epoch)
        }
        if let d = PopoverContentView.parseDate(epoch: nil, utc: store.status.updated_at) {
            return max(0, Date().timeIntervalSince(d))
        }
        return 0
    }

    private func formatAge(_ sec: Double) -> String {
        let m = Int(sec) / 60
        if m >= 60 {
            return "\(m / 60)h"
        }
        return "\(m)m"
    }

    // MARK: - Primary Track (Dynamic Twin Quota / Windows)
    private var primaryTrackSection: some View {
        let primary = store.status.resolvedTracks.first(where: { $0.is_primary }) ?? store.status.resolvedTracks.first
        return Group {
            if let track = primary {
                VStack(alignment: .leading, spacing: 9) {
                    ForEach(Array(track.windows.enumerated()), id: \.element.id) { index, window in
                        if index > 0 {
                            Divider().opacity(0.5)
                        }
                        TrackWindowCard(window: window)
                    }
                }
                .padding(10)
                .background(
                    RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                        .fill(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                        .stroke(Color(NSColor.separatorColor).opacity(0.25), lineWidth: 1)
                )
                .cornerRadius(PopoverDesignTokens.cardCornerRadius)
            }
        }
    }

    // MARK: - Secondary Tracks Section (Dynamic ForEach with 0%-burn collapsing)
    private var secondaryTracksSection: some View {
        let secondaries = store.status.resolvedTracks.filter { !$0.is_primary }
        return ForEach(secondaries) { track in
            SecondaryTrackCard(track: track)
        }
    }

    @ViewBuilder
    private var activeSessionContextSection: some View {
        if let curr = store.status.current_session {
            PinnedActiveSessionCard(
                curr: curr,
                fallbackBranch: store.status.active_branch,
                fallbackEpoch: store.status.compaction_epoch
            )
        }
    }

    @ViewBuilder
    private var activeSwarmsSection: some View {
        if let swarms = store.status.active_swarms, !swarms.isEmpty {
            ActiveSwarmsSection(
                swarms: swarms,
                isExpanded: Binding(
                    get: { isSwarmsExpanded },
                    set: { newValue in
                        isSwarmsExpanded = newValue
                        if newValue { isSessionsExpanded = false }
                    }
                ),
                onOpenDashboard: {
                    store.openDashboard(tab: "tab-swarms")
                }
            )
        }
    }

    @ViewBuilder
    private var activeContextSection: some View {
        if store.status.current_session == nil {
            HStack(spacing: 8) {
                HStack(spacing: 4) {
                    Image(systemName: "folder")
                        .font(.system(size: PopoverDesignTokens.captionFontSize))
                        .foregroundColor(.secondary)
                    Text(store.status.active_project ?? "Default Project")
                        .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .medium))
                        .lineLimit(1)
                }

                Spacer(minLength: 6)

                if let branch = store.status.active_branch, !branch.isEmpty {
                    Text("(\(branch))")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(Color(NSColor.separatorColor).opacity(0.08))
            .cornerRadius(5)
        }
    }

    @ViewBuilder
    private var historicalSessionsSection: some View {
        if let sessions = store.status.degraded_sessions, !sessions.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        isSessionsExpanded.toggle()
                        if isSessionsExpanded { isSwarmsExpanded = false }
                    }
                }) {
                    HStack(spacing: 6) {
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.system(size: PopoverDesignTokens.captionFontSize))
                            .foregroundColor(.secondary)
                        Text("Historical Degraded Sessions (\(sessions.count))")
                            .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium))
                            .foregroundColor(.secondary)
                        Spacer()
                        Image(systemName: isSessionsExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 3)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                if isSessionsExpanded {
                    HistoricalOffendersList(
                        sessions: sessions,
                        onOpenSessions: {
                            store.openDashboard(tab: "tab-sessions")
                        }
                    )
                    .padding(.top, 4)
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color(NSColor.separatorColor).opacity(0.05))
            .cornerRadius(5)
        }
    }

    private var footerSection: some View {
        HStack {
            Button(action: {
                store.openDashboard()
            }) {
                HStack(spacing: 4) {
                    Image(systemName: "globe")
                    Text("Open Dashboard")
                }
                .font(.system(size: 11, weight: .medium))
            }
            .buttonStyle(.bordered)
            .controlSize(.small)

            Button(action: {
                copyStatusSummary()
            }) {
                HStack(spacing: 3) {
                    Image(systemName: isCopied ? "checkmark" : "doc.on.doc")
                    Text(isCopied ? "Copied" : "Copy")
                }
                .font(.system(size: 10.5, weight: .medium))
            }
            .buttonStyle(.borderless)
            .controlSize(.small)
            .foregroundColor(.secondary)

            Spacer()

            HStack(spacing: 5) {
                Circle()
                    .fill(store.isWatcherRunning ? Color.green : Color.orange)
                    .frame(width: 6, height: 6)
                Text(store.isWatcherRunning ? "Watcher Live" : "Watcher Inactive")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(store.isWatcherRunning ? .secondary : .orange)
            }
            .help(store.isWatcherRunning ? "Antigravity Telemetry Watcher Daemon is actively monitoring SQLite databases and updating quotas in real time." : "Watcher daemon is inactive. Run 'python3 scripts/setup_service.py restart' to start it.")
            .contentShape(Rectangle())
            .onTapGesture {
                store.checkWatcherStatus()
            }
        }
    }

    private func copyStatusSummary() {
        let s = store.status
        let primaryTrack = s.resolvedTracks.first(where: { $0.is_primary }) ?? s.resolvedTracks.first
        let primary5h = primaryTrack?.windows.first(where: { $0.window_id == "5h" })
        let primaryWk = primaryTrack?.windows.first(where: { $0.window_id == "weekly" })
        let gem5h = Int(round(primary5h?.remaining_pct ?? s.gemini5hRem))
        let gemWk = Int(round(primaryWk?.remaining_pct ?? s.geminiWkRem))
        let claudeTrack = s.resolvedTracks.first(where: { !$0.is_primary })
        let claudeWk = Int(round(claudeTrack?.windows.first?.remaining_pct ?? s.claudeWkRem))
        let summary = "AGY: G:\(gem5h)%/\(gemWk)% C:\(claudeWk)% (\(s.status ?? "SAFE"))"
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(summary, forType: .string)
        isCopied = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            isCopied = false
        }
    }
}

// MARK: - Track Window Card (Zero English Scraping)
struct TrackWindowCard: View {
    let window: QuotaWindow

    private var barColor: Color {
        if window.severity == "critical" { return .red }
        if window.severity == "warning" { return .orange }
        if window.window_id == "weekly" { return .blue }
        return Color(red: 5/255.0, green: 150/255.0, blue: 105/255.0)
    }

    private var textHealthColor: Color {
        if window.severity == "critical" { return .red }
        if window.severity == "warning" { return .orange }
        return .primary
    }

    private var resetText: String {
        if let rel = PopoverContentView.formatRelativeReset(epoch: window.reset_epoch, utc: window.reset_utc) {
            return rel
        }
        return window.window_id == "5h" ? "100% Headroom" : "Weekly reset"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Label(window.label, systemImage: window.icon ?? (window.window_id == "5h" ? "bolt.fill" : "calendar"))
                    .font(.system(size: PopoverDesignTokens.sectionTitleFontSize, weight: .semibold))
                Spacer()
                Text(String(format: "%.1f%%", window.remaining_pct))
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(textHealthColor)
            }

            QuotaProgressBar(
                percentage: window.remaining_pct,
                color: barColor
            )

            HStack(spacing: 4) {
                if let tok = window.used_tokens, tok > 0 {
                    Text("\(StatusModel.formatCompactTokens(tok)) tok")
                        .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                    Text("•")
                        .font(.system(size: PopoverDesignTokens.bodyFontSize))
                        .foregroundColor(.secondary.opacity(0.5))
                }

                Image(systemName: window.window_id == "5h" ? "clock.arrow.circlepath" : "calendar.badge.clock")
                    .font(.system(size: PopoverDesignTokens.captionFontSize))
                    .foregroundColor(.secondary)

                TimelineView(.periodic(from: .now, by: 60.0)) { _ in
                    Text(resetText)
                        .font(.system(size: PopoverDesignTokens.bodyFontSize))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }

                Spacer(minLength: 4)

                if let bviLbl = window.bvi_label ?? (window.bvi != nil ? String(format: "BVI %.2f", window.bvi!) : nil), !bviLbl.isEmpty {
                    HStack(spacing: 3) {
                        Image(systemName: "gauge.with.needle")
                            .font(.system(size: PopoverDesignTokens.captionFontSize))
                        Text(bviLbl)
                            .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .medium))
                            .lineLimit(1)
                    }
                    .foregroundColor(window.severity == "critical" ? .red : (window.severity == "warning" ? .orange : .secondary))
                }
            }
        }
    }
}

// MARK: - Secondary Track Card
struct SecondaryTrackCard: View {
    let track: QuotaTrack
    @State private var isExpanded: Bool = false

    private var isZeroBurn: Bool {
        track.windows.allSatisfy { $0.used_pct <= 0.001 }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.15)) {
                    isExpanded.toggle()
                }
            }) {
                HStack {
                    Label(track.name, systemImage: track.icon ?? "sparkle")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium))
                        .foregroundColor(.secondary)

                    Spacer()

                    if let primaryWin = track.windows.first {
                        Text(String(format: "%.0f%% remaining", primaryWin.remaining_pct))
                            .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .bold, design: .monospaced))
                            .foregroundColor(.primary)
                    }

                    if isZeroBurn {
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .foregroundColor(.secondary)
                    }
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if !isZeroBurn || isExpanded {
                ForEach(track.windows) { win in
                    let barColor: Color = win.remaining_pct < 20 ? .red : (win.remaining_pct < 40 ? .orange : Color.purple.opacity(0.75))
                    QuotaProgressBar(
                        percentage: win.remaining_pct,
                        color: barColor
                    )
                }
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .stroke(Color(NSColor.separatorColor).opacity(0.2), lineWidth: 1)
        )
        .cornerRadius(PopoverDesignTokens.cardCornerRadius)
    }
}

// MARK: - Pinned Active Session Card
struct PinnedActiveSessionCard: View {
    let curr: DegradedSession
    let fallbackBranch: String?
    var fallbackEpoch: Int? = nil

    private var cardColor: Color {
        if curr.severity == "critical" { return .red }
        if curr.severity == "warning" { return .orange }
        return PopoverDesignTokens.emeraldAccent
    }

    private var formattedTokens: String {
        return StatusModel.formatCompactTokens(curr.tokens)
    }

    private var effectiveThreshold: Int {
        return curr.compaction_threshold ?? curr.threshold ?? 200_000
    }

    private var formattedThreshold: String {
        return StatusModel.formatCompactTokens(effectiveThreshold)
    }

    private var loadPercentage: Double {
        let tok = Double(curr.tokens ?? 0)
        let thresh = Double(effectiveThreshold)
        guard thresh > 0 else { return 0 }
        return min(100.0, (tok / thresh) * 100.0)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4.5) {
            HStack(spacing: 5) {
                if curr.is_weakest_link == true && curr.severity != "safe" {
                    Text("Weakest Link")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1.5)
                        .background(cardColor.opacity(0.2))
                        .foregroundColor(cardColor)
                        .cornerRadius(3)
                } else if curr.is_subagent == true {
                    Text("Subagent [\(curr.subagent_role ?? "worker")]")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1.5)
                        .background(cardColor.opacity(0.18))
                        .foregroundColor(cardColor)
                        .cornerRadius(3)
                } else if curr.severity != "safe" {
                    Text(curr.severity == "critical" ? "Context Critical" : "Context Warning")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1.5)
                        .background(cardColor.opacity(0.2))
                        .foregroundColor(cardColor)
                        .cornerRadius(3)
                } else {
                    Text("Active Context")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .bold))
                        .foregroundColor(.primary)
                }

                if let ws = curr.workspace, !ws.isEmpty {
                    Text(ws)
                        .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .bold))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                }

                if let branch = curr.branch ?? fallbackBranch, !branch.isEmpty {
                    Text("(\(branch))")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                HStack(spacing: 2) {
                    Text("\(formattedTokens) / \(formattedThreshold)")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .bold, design: .monospaced))
                        .foregroundColor(curr.severity == "safe" ? .primary : cardColor)
                    if loadPercentage > 0 {
                        Text("(\(Int(round(loadPercentage)))%)")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                }
            }

            // Lineage
            HStack(spacing: 4) {
                Text("↳")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                    .foregroundColor(cardColor)

                if curr.is_subagent == true {
                    Text("[\(curr.subagent_role ?? "subagent")]")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                        .padding(.horizontal, 3)
                        .padding(.vertical, 0.5)
                        .background(Color(NSColor.separatorColor).opacity(0.15))
                        .foregroundColor(cardColor)
                        .cornerRadius(2)
                    Text(curr.title ?? "Subagent Task")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                    if let pt = curr.parent_title, !pt.isEmpty {
                        Text("• child of \(pt)")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize))
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                } else {
                    Text(curr.title ?? "Main Orchestrator Task")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                }
            }

            // Inset Capsule progress bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2.5)
                        .fill(Color(NSColor.separatorColor).opacity(0.35))
                        .frame(height: 5)

                    RoundedRectangle(cornerRadius: 2.5)
                        .fill(cardColor)
                        .frame(width: max(0, min(geo.size.width, geo.size.width * CGFloat(loadPercentage / 100.0))), height: 5)
                }
            }
            .frame(height: 5)
            .padding(.vertical, 1)

            // Diagnosis & Epoch status
            HStack {
                HStack(spacing: 3) {
                    if curr.severity != "safe" {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize))
                            .foregroundColor(cardColor)
                    }
                    if let msg = curr.drift_message {
                        Text(msg)
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: curr.severity == "safe" ? .medium : .bold))
                            .foregroundColor(curr.severity == "safe" ? .secondary : cardColor)
                            .lineLimit(1)
                    } else if curr.severity == "safe" {
                        Text("Safe (+\(StatusModel.formatCompactTokens(curr.headroom_to_warning)) tok to warning)")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    } else {
                        Text(curr.severity == "critical" ? "Compaction Imminent" : "Near Compaction")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .foregroundColor(cardColor)
                    }
                }

                Spacer()

                let ep = curr.compaction_epoch ?? fallbackEpoch ?? 1
                Text("Epoch \(ep)")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                    .padding(.horizontal, 4)
                    .padding(.vertical, 1)
                    .background(Color(NSColor.separatorColor).opacity(0.2))
                    .foregroundColor(ep <= 2 ? .primary : cardColor)
                    .cornerRadius(2.5)
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .stroke(cardColor.opacity(curr.severity == "safe" ? 0.2 : 0.35), lineWidth: 1)
        )
    }
}

typealias PinnedActiveBranchCard = PinnedActiveSessionCard

// MARK: - Active Swarms Section
struct ActiveSwarmsSection: View {
    let swarms: [ActiveSwarmGroup]
    @Binding var isExpanded: Bool
    var onOpenDashboard: (() -> Void)? = nil

    private var totalAgents: Int {
        var count = 0
        for s in swarms {
            if s.orchestrator != nil { count += 1 }
            count += s.subagents?.count ?? 0
        }
        return count
    }

    private var worstColor: Color {
        let sevs = swarms.map { $0.worst_severity ?? "safe" }
        if sevs.contains("critical") { return .red }
        if sevs.contains("warning") { return .orange }
        return PopoverDesignTokens.emeraldAccent
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            }) {
                HStack(spacing: 6) {
                    Image(systemName: "square.stack.3d.up.fill")
                        .font(.system(size: PopoverDesignTokens.captionFontSize))
                        .foregroundColor(worstColor)
                    Text("Active Swarms & Projects (\(swarms.count) \(swarms.count == 1 ? "project" : "projects"), \(totalAgents) \(totalAgents == 1 ? "agent" : "agents"))")
                        .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .semibold))
                        .foregroundColor(.primary)
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .foregroundColor(.secondary)
                }
                .padding(.vertical, 3.5)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if isExpanded {
                let visibleSwarms = Array(swarms.prefix(PopoverDesignTokens.maxVisibleSwarmGroups))
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(visibleSwarms) { grp in
                        SwarmGroupCard(group: grp)
                    }
                    if swarms.count > PopoverDesignTokens.maxVisibleSwarmGroups {
                        Button(action: {
                            onOpenDashboard?()
                        }) {
                            Text("+ \(swarms.count - PopoverDesignTokens.maxVisibleSwarmGroups) more projects in Dashboard")
                                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                                .foregroundColor(.accentColor)
                                .padding(.leading, 6)
                                .padding(.top, 1)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.top, 4)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .fill(.ultraThinMaterial)
        )
        .cornerRadius(PopoverDesignTokens.cardCornerRadius)
    }
}

struct SwarmGroupCard: View {
    let group: ActiveSwarmGroup

    private func formatK(_ val: Int?) -> String {
        return StatusModel.formatCompactTokens(val)
    }

    private func colorForSeverity(_ sev: String?) -> Color {
        if sev == "critical" { return .red }
        if sev == "warning" { return .orange }
        return PopoverDesignTokens.emeraldAccent
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: "folder")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize))
                    .foregroundColor(.secondary)
                Text(group.workspace ?? "Workspace")
                    .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .bold))
                    .lineLimit(1)
                if let b = group.branch, !b.isEmpty {
                    Text("(\(b))")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Circle()
                    .fill(colorForSeverity(group.worst_severity))
                    .frame(width: 5, height: 5)
            }

            if let orch = group.orchestrator {
                HStack(spacing: 4.5) {
                    Text("Orchestrator")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .padding(.horizontal, 3.5)
                        .padding(.vertical, 1)
                        .background(Color(NSColor.separatorColor).opacity(0.18))
                        .foregroundColor(.primary)
                        .cornerRadius(2)

                    Text(orch.title ?? "Main Orchestrator")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                        .lineLimit(1)

                    Spacer(minLength: 4)

                    let ep = orch.compaction_epoch ?? 1
                    Text("E\(ep)")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                        .padding(.horizontal, 3)
                        .padding(.vertical, 0.5)
                        .background(ep <= 1 ? Color(NSColor.separatorColor).opacity(0.1) : (ep == 2 ? Color.orange.opacity(0.18) : Color.red.opacity(0.18)))
                        .foregroundColor(ep <= 1 ? .secondary : (ep == 2 ? .orange : .red))
                        .cornerRadius(2)

                    let orchThresh = orch.compaction_threshold ?? orch.threshold ?? 200_000
                    Text("\(formatK(orch.tokens)) / \(formatK(orchThresh))")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)

                    Text(orch.severity?.uppercased() ?? "SAFE")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        .padding(.horizontal, 3.5)
                        .padding(.vertical, 1)
                        .background(colorForSeverity(orch.severity).opacity(0.15))
                        .foregroundColor(colorForSeverity(orch.severity))
                        .cornerRadius(2.5)
                }
                .padding(.leading, 6)
            }

            if let subagents = group.subagents, !subagents.isEmpty {
                let cap = PopoverDesignTokens.maxVisibleSubagentsPerGroup
                let visibleSubs = Array(subagents.prefix(cap))
                ForEach(visibleSubs) { sub in
                    let rawRole = sub.subagent_role ?? "worker"
                    let rawTitle = sub.title ?? "Subagent"
                    let isGenericHexTitle = rawTitle.hasPrefix("Conversation ") && !rawRole.isEmpty
                    let displayBadge = (isGenericHexTitle && (rawRole.contains(" ") || rawRole.count > 14)) ? "subagent" : rawRole
                    let displayTitle = isGenericHexTitle ? rawRole : rawTitle

                    HStack(spacing: 4) {
                        Text("↳")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .foregroundColor(sub.is_weakest_link == true ? colorForSeverity(sub.severity) : .secondary)

                        Text("[\(displayBadge)]")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                            .padding(.horizontal, 3)
                            .padding(.vertical, 0.5)
                            .background(Color(NSColor.separatorColor).opacity(0.15))
                            .foregroundColor(sub.is_weakest_link == true ? colorForSeverity(sub.severity) : .primary)
                            .cornerRadius(2)

                        Text(displayTitle)
                            .font(.system(size: PopoverDesignTokens.badgeFontSize))
                            .foregroundColor(sub.is_weakest_link == true ? .primary : .secondary)
                            .lineLimit(1)

                        Spacer(minLength: 4)

                        if sub.is_weakest_link == true {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: PopoverDesignTokens.badgeFontSize))
                                .foregroundColor(.red)
                        }

                        let ep = sub.compaction_epoch ?? 1
                        Text("E\(ep)")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold, design: .monospaced))
                            .padding(.horizontal, 3)
                            .padding(.vertical, 0.5)
                            .background(ep <= 1 ? Color(NSColor.separatorColor).opacity(0.1) : (ep == 2 ? Color.orange.opacity(0.18) : Color.red.opacity(0.18)))
                            .foregroundColor(ep <= 1 ? .secondary : (ep == 2 ? .orange : .red))
                            .cornerRadius(2)

                        let subThresh = sub.compaction_threshold ?? sub.threshold ?? 200_000
                        Text("\(formatK(sub.tokens)) / \(formatK(subThresh))")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                            .foregroundColor(.secondary)

                        Text(sub.severity?.uppercased() ?? "SAFE")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .padding(.horizontal, 3)
                            .padding(.vertical, 1)
                            .background(colorForSeverity(sub.severity).opacity(0.15))
                            .foregroundColor(colorForSeverity(sub.severity))
                            .cornerRadius(2.5)
                    }
                    .padding(.leading, 12)
                }
                if subagents.count > cap {
                    Text("+ \(subagents.count - cap) more subagents...")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                        .foregroundColor(.secondary)
                        .padding(.leading, 16)
                        .padding(.top, 2)
                }
            }
        }
        .padding(6)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.35))
        .cornerRadius(5)
    }
}

// MARK: - Historical Sessions Section
struct HistoricalOffendersList: View {
    let sessions: [DegradedSession]
    var onOpenSessions: (() -> Void)? = nil

    var body: some View {
        let cap = PopoverDesignTokens.maxVisibleHistoricalSessions
        let visibleSessions = Array(sessions.prefix(cap))
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("HISTORICAL SESSIONS (PAST 24H)")
                    .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding(.top, 2)

            ForEach(visibleSessions) { s in
                HStack(spacing: 5) {
                    Circle()
                        .fill(s.severity == "critical" ? Color.red : Color.orange)
                        .frame(width: 4, height: 4)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(s.title ?? "Unknown Session")
                            .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium))
                            .lineLimit(1)
                            .truncationMode(.middle)
                        HStack(spacing: 3) {
                            if let b = s.branch, !b.isEmpty {
                                Text(b)
                                    .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                                    .padding(.horizontal, 3)
                                    .padding(.vertical, 0.5)
                                    .background(Color(NSColor.controlBackgroundColor))
                                    .cornerRadius(2)
                            }
                            if let ws = s.workspace, !ws.isEmpty {
                                Text("• \(ws)")
                                    .font(.system(size: PopoverDesignTokens.badgeFontSize))
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                        }
                    }
                    Spacer(minLength: 6)
                    Text("\(StatusModel.formatCompactTokens(s.tokens)) tok")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium, design: .monospaced))
                        .foregroundColor(.secondary)
                }
            }

            if sessions.count > cap {
                Button(action: {
                    onOpenSessions?()
                }) {
                    Text("+ \(sessions.count - cap) more sessions in Dashboard")
                        .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .medium))
                        .foregroundColor(.accentColor)
                        .padding(.top, 1)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

// MARK: - Status Badge View
struct StatusBadgeView: View {
    let status: StatusModel

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(status.healthColor)
                .frame(width: 7, height: 7)
            Text(badgeText)
                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                .foregroundColor(status.isHealthy ? .secondary : status.healthColor)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(status.isHealthy ? Color(NSColor.separatorColor).opacity(0.15) : status.healthColor.opacity(0.12))
        .cornerRadius(4)
    }

    private var badgeText: String {
        if status.isCritical { return "CRITICAL" }
        if status.status == "RECOVERED_COOLDOWN" { return "RECOVERED" }
        if status.isWarning { return "QUOTA WARN" }
        return "QUOTA SAFE"
    }
}

// MARK: - Quota Progress Bar
struct QuotaProgressBar: View {
    let percentage: Double
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(Color(NSColor.separatorColor).opacity(0.3))
                    .frame(height: 6)

                RoundedRectangle(cornerRadius: 3)
                    .fill(color)
                    .frame(width: max(0, min(geo.size.width, geo.size.width * CGFloat(percentage / 100.0))), height: 6)
            }
        }
        .frame(height: 6)
    }
}

// MARK: - Live Token Ticker Card
struct LiveTokenTickerCard: View {
    let status: StatusModel

    var body: some View {
        VStack(spacing: 5) {
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "sparkle")
                        .font(.system(size: PopoverDesignTokens.captionFontSize))
                        .foregroundColor(.accentColor)
                    Text(status.last_turn_model ?? "Gemini Engine")
                        .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .semibold))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                }

                Spacer(minLength: 6)

                Text(status.formattedLastTurnCache)
                    .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .semibold, design: .monospaced))
                    .padding(.horizontal, 4.5)
                    .padding(.vertical, 1.5)
                    .background(Color(NSColor.separatorColor).opacity(0.18))
                    .foregroundColor(.secondary)
                    .cornerRadius(3)
            }

            HStack {
                HStack(spacing: 5) {
                    Circle()
                        .fill(status.isStreamingActive ? status.streamingDotColor : Color.secondary)
                        .frame(width: 6, height: 6)
                    if status.isStreamingActive {
                        Text("\(status.formattedBurnRate) active")
                            .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .bold, design: .monospaced))
                            .foregroundColor(.primary)
                    } else {
                        Text("Engine Idle")
                            .font(.system(size: PopoverDesignTokens.bodyFontSize, weight: .medium))
                            .foregroundColor(.secondary)
                    }
                }

                Spacer(minLength: 6)

                if let tokens = status.last_turn_tokens, tokens > 0 {
                    HStack(spacing: 2) {
                        Text(status.isStreamingActive ? "▲" : "+")
                            .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                            .foregroundColor(status.isStreamingActive ? Color.green : .secondary)
                        Text("\(status.formattedLastTurnTokens) tok/turn")
                            .font(.system(size: PopoverDesignTokens.captionFontSize, weight: .medium, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                }
            }

            if status.formattedTtftLatency != nil || status.kvCacheWiped {
                HStack(spacing: 5) {
                    if let ttftText = status.formattedTtftLatency {
                        HStack(spacing: 3) {
                            Image(systemName: "timer")
                                .font(.system(size: PopoverDesignTokens.badgeFontSize))
                            Text(ttftText)
                                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .semibold, design: .monospaced))
                        }
                        .padding(.horizontal, 4.5)
                        .padding(.vertical, 1.5)
                        .background(Color.accentColor.opacity(0.12))
                        .foregroundColor(.accentColor)
                        .cornerRadius(3)
                    }

                    Spacer(minLength: 4)

                    if status.kvCacheWiped {
                        HStack(spacing: 2.5) {
                            Image(systemName: "bolt.fill")
                                .font(.system(size: PopoverDesignTokens.badgeFontSize))
                            Text("KV Cache Evicted (0% Hit)")
                                .font(.system(size: PopoverDesignTokens.badgeFontSize, weight: .bold))
                        }
                        .padding(.horizontal, 4.5)
                        .padding(.vertical, 1.5)
                        .background(Color.orange.opacity(0.2))
                        .foregroundColor(.orange)
                        .cornerRadius(3)
                    }
                }
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: PopoverDesignTokens.cardCornerRadius)
                .stroke(Color(NSColor.separatorColor).opacity(0.25), lineWidth: 1)
        )
        .cornerRadius(PopoverDesignTokens.cardCornerRadius)
    }
}
