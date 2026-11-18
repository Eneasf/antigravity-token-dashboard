import Foundation
import SwiftUI

public struct DegradedSession: Codable, Identifiable {
    public var id: String {
        if let cid = convo_id, !cid.isEmpty { return cid }
        if let t = title, !t.isEmpty { return "\(workspace ?? "ws")_\(branch ?? "br")_\(t)" }
        return "\(workspace ?? "ws")_\(branch ?? "br")_\(tokens ?? 0)_\(compaction_epoch ?? 1)"
    }
    public var convo_id: String?
    public var title: String?
    public var branch: String?
    public var workspace: String?
    public var tokens: Int?
    public var severity: String?
    public var is_current: Bool?
    public var headroom_to_warning: Int?
    public var compaction_epoch: Int?
    public var compaction_threshold: Int?
    public var threshold: Int?
    public var drift_risk: String?
    public var drift_message: String?
    public var is_subagent: Bool?
    public var subagent_role: String?
    public var parent_convo_id: String?
    public var parent_title: String?
    public var is_weakest_link: Bool?
    public var turn_velocity: Int?
}

public struct ActiveSwarmSubagent: Codable, Identifiable {
    public var id: String {
        if let cid = convo_id, !cid.isEmpty { return cid }
        if let t = title, !t.isEmpty { return "\(subagent_role ?? "sub")_\(t)" }
        return "\(subagent_role ?? "sub")_\(tokens ?? 0)_\(compaction_epoch ?? 1)"
    }
    public var convo_id: String?
    public var title: String?
    public var subagent_role: String?
    public var tokens: Int?
    public var threshold: Int?
    public var compaction_threshold: Int?
    public var compaction_epoch: Int?
    public var severity: String?
    public var is_weakest_link: Bool?
    public var turn_velocity: Int?
}

public struct ActiveSwarmGroup: Codable, Identifiable {
    public var id: String {
        let orchId = orchestrator?.convo_id ?? orchestrator?.title ?? "standalone"
        return "\(workspace ?? "ws")_\(branch ?? "main")_\(orchId)"
    }
    public var workspace: String?
    public var branch: String?
    public var worst_severity: String?
    public var orchestrator: DegradedSession?
    public var subagents: [ActiveSwarmSubagent]?
}

public struct LiveTickerInfo: Codable {
    public var lastTurnTtftMs: Double?
    public var lastTurnLatencyMs: Double?
    public var sessionMedianTtftMs: Double?
    public var kvCacheWiped: Bool?

    enum CodingKeys: String, CodingKey {
        case lastTurnTtftMs = "last_turn_ttft_ms"
        case lastTurnLatencyMs = "last_turn_latency_ms"
        case sessionMedianTtftMs = "session_median_ttft_ms"
        case kvCacheWiped = "kv_cache_wiped"
    }

    public init(
        lastTurnTtftMs: Double? = nil,
        lastTurnLatencyMs: Double? = nil,
        sessionMedianTtftMs: Double? = nil,
        kvCacheWiped: Bool? = nil
    ) {
        self.lastTurnTtftMs = lastTurnTtftMs
        self.lastTurnLatencyMs = lastTurnLatencyMs
        self.sessionMedianTtftMs = sessionMedianTtftMs
        self.kvCacheWiped = kvCacheWiped
    }
}

public struct WatcherInfo: Codable {
    public var pid: Int?
    public var heartbeat_utc: String?

    public init(pid: Int? = nil, heartbeat_utc: String? = nil) {
        self.pid = pid
        self.heartbeat_utc = heartbeat_utc
    }
}

public struct PlanStatus: Codable, Equatable {
    public var tier_id: String?
    public var name: String?
    public var badge: String?
    public var credit_pool: Int?
    public var credits_remaining: Int?
    public var credit_balance_gbp: Double?

    public init(
        tier_id: String? = nil,
        name: String? = nil,
        badge: String? = nil,
        credit_pool: Int? = nil,
        credits_remaining: Int? = nil,
        credit_balance_gbp: Double? = nil
    ) {
        self.tier_id = tier_id
        self.name = name
        self.badge = badge
        self.credit_pool = credit_pool
        self.credits_remaining = credits_remaining
        self.credit_balance_gbp = credit_balance_gbp
    }
}

public struct QuotaWindow: Codable, Identifiable, Equatable {
    public var id: String { window_id }
    public var window_id: String
    public var label: String
    public var icon: String?
    public var used_pct: Double
    public var remaining_pct: Double
    public var used_tokens: Int?
    public var reset_utc: String?
    public var reset_epoch: Double?
    public var is_cooldown: Bool?
    public var severity: String?
    public var bvi: Double?
    public var bvi_status: String?
    public var bvi_pacing_pct: Double?
    public var bvi_label: String?

    enum CodingKeys: String, CodingKey {
        case window_id, label, icon, used_pct, remaining_pct, used_tokens
        case reset_utc, reset_epoch, is_cooldown, severity, status_severity
        case bvi, bvi_status, bvi_pacing_pct, bvi_label
    }

    public init(
        window_id: String,
        label: String,
        icon: String? = nil,
        used_pct: Double,
        remaining_pct: Double,
        used_tokens: Int? = nil,
        reset_utc: String? = nil,
        reset_epoch: Double? = nil,
        is_cooldown: Bool? = nil,
        severity: String? = nil,
        bvi: Double? = nil,
        bvi_status: String? = nil,
        bvi_pacing_pct: Double? = nil,
        bvi_label: String? = nil
    ) {
        self.window_id = window_id
        self.label = label
        self.icon = icon
        self.used_pct = used_pct
        self.remaining_pct = remaining_pct
        self.used_tokens = used_tokens
        self.reset_utc = reset_utc
        self.reset_epoch = reset_epoch
        self.is_cooldown = is_cooldown
        self.severity = severity
        self.bvi = bvi
        self.bvi_status = bvi_status
        self.bvi_pacing_pct = bvi_pacing_pct
        self.bvi_label = bvi_label
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.window_id = try container.decode(String.self, forKey: .window_id)
        self.label = try container.decode(String.self, forKey: .label)
        self.icon = try container.decodeIfPresent(String.self, forKey: .icon)
        self.used_pct = try container.decode(Double.self, forKey: .used_pct)
        self.remaining_pct = try container.decode(Double.self, forKey: .remaining_pct)
        self.used_tokens = try container.decodeIfPresent(Int.self, forKey: .used_tokens)
        self.reset_utc = try container.decodeIfPresent(String.self, forKey: .reset_utc)
        self.reset_epoch = try container.decodeIfPresent(Double.self, forKey: .reset_epoch)
        self.is_cooldown = try container.decodeIfPresent(Bool.self, forKey: .is_cooldown)
        self.severity = try container.decodeIfPresent(String.self, forKey: .severity)
            ?? container.decodeIfPresent(String.self, forKey: .status_severity)
        self.bvi = try container.decodeIfPresent(Double.self, forKey: .bvi)
        self.bvi_status = try container.decodeIfPresent(String.self, forKey: .bvi_status)
        self.bvi_pacing_pct = try container.decodeIfPresent(Double.self, forKey: .bvi_pacing_pct)
        self.bvi_label = try container.decodeIfPresent(String.self, forKey: .bvi_label)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(window_id, forKey: .window_id)
        try container.encode(label, forKey: .label)
        try container.encodeIfPresent(icon, forKey: .icon)
        try container.encode(used_pct, forKey: .used_pct)
        try container.encode(remaining_pct, forKey: .remaining_pct)
        try container.encodeIfPresent(used_tokens, forKey: .used_tokens)
        try container.encodeIfPresent(reset_utc, forKey: .reset_utc)
        try container.encodeIfPresent(reset_epoch, forKey: .reset_epoch)
        try container.encodeIfPresent(is_cooldown, forKey: .is_cooldown)
        try container.encodeIfPresent(severity, forKey: .severity)
        try container.encodeIfPresent(bvi, forKey: .bvi)
        try container.encodeIfPresent(bvi_status, forKey: .bvi_status)
        try container.encodeIfPresent(bvi_pacing_pct, forKey: .bvi_pacing_pct)
        try container.encodeIfPresent(bvi_label, forKey: .bvi_label)
    }
}

public struct QuotaTrack: Codable, Identifiable, Equatable {
    public var id: String
    public var name: String
    public var short_name: String?
    public var icon: String?
    public var is_primary: Bool
    public var credit_spillover: Bool?
    public var windows: [QuotaWindow]

    public init(
        id: String,
        name: String,
        short_name: String? = nil,
        icon: String? = nil,
        is_primary: Bool = false,
        credit_spillover: Bool? = nil,
        windows: [QuotaWindow] = []
    ) {
        self.id = id
        self.name = name
        self.short_name = short_name
        self.icon = icon
        self.is_primary = is_primary
        self.credit_spillover = credit_spillover
        self.windows = windows
    }
}

public struct StatusModel: Codable {
    public var schema_version: Int?
    public var generated_at_utc: String?
    public var generated_at_epoch: Double?
    public var plan: PlanStatus?
    public var tracks: [QuotaTrack]?

    public var status: String?
    public var gemini_5h_pct: Double?
    public var gemini_5h_remaining_pct: Double?
    public var gemini_weekly_pct: Double?
    public var gemini_weekly_remaining_pct: Double?
    public var claude_5h_pct: Double?
    public var claude_5h_remaining_pct: Double?
    public var claude_weekly_pct: Double?
    public var claude_weekly_remaining_pct: Double?
    public var cooldown_active: Bool?
    public var weekly_reset_utc: String?
    public var weekly_reset_desc: String?
    public var gemini_5h_recovery_desc: String?
    public var bvi: Double?
    public var bvi_verdict: String?
    public var plan_name: String?
    public var active_project: String?
    public var active_branch: String?
    public var degraded_count: Int?
    public var critical_count: Int?
    public var active_session_severity: String?
    public var compaction_epoch: Int?
    public var current_session: DegradedSession?
    public var degraded_sessions: [DegradedSession]?
    public var credit_balance: String?
    public var dashboard_path: String?
    public var updated_at: String?
    public var recent_burn_rate_tok_per_min: Int?
    public var recent_burn_rate_tok_per_sec: Double?
    public var last_turn_tokens: Int?
    public var last_turn_model: String?
    public var last_turn_ts: String?
    public var is_streaming: Bool?
    public var seconds_since_last_turn: Int?
    public var gemini_5h_tokens: Int?
    public var last_turn_cache_pct: Double?
    public var watcher: WatcherInfo?
    public var active_swarms: [ActiveSwarmGroup]?
    public var last_turn_ttft_ms: Double?
    public var last_turn_latency_ms: Double?
    public var session_median_ttft_ms: Double?
    public var kv_cache_wiped: Bool?
    public var live_ticker: LiveTickerInfo?

    public init() {}

    public var resolvedPlan: PlanStatus {
        if let p = plan { return p }
        return PlanStatus(
            tier_id: "ultra_5x",
            name: plan_name ?? "Google AI Ultra (5x)",
            badge: plan_name?.contains("Ultra") == true ? "Ultra 5x" : "Pro",
            credit_pool: 7500,
            credits_remaining: nil,
            credit_balance_gbp: nil
        )
    }

    public var resolvedTracks: [QuotaTrack] {
        if let t = tracks, !t.isEmpty {
            return t
        }

        // Seamless fallback synthesizing structured tracks from legacy v1 flat payload
        var geminiWindows: [QuotaWindow] = []
        let gem5hSev = is5hCritical ? "critical" : (is5hWarning ? "warning" : "safe")
        geminiWindows.append(
            QuotaWindow(
                window_id: "5h",
                label: "5-Hour Burst Limit",
                icon: "bolt.fill",
                used_pct: gemini_5h_pct ?? max(0.0, 100.0 - gemini5hRem),
                remaining_pct: gemini5hRem,
                used_tokens: gemini_5h_tokens,
                reset_utc: nil,
                reset_epoch: nil,
                is_cooldown: cooldown_active,
                severity: gem5hSev
            )
        )
        let gemWkSev = isWeeklyCritical ? "critical" : (isWeeklyWarning ? "warning" : "safe")
        let bviStat = (bvi ?? 1.0) > 1.3 ? "deficit" : "on_track"
        geminiWindows.append(
            QuotaWindow(
                window_id: "weekly",
                label: "Weekly Quota Runway",
                icon: "calendar",
                used_pct: gemini_weekly_pct ?? max(0.0, 100.0 - geminiWkRem),
                remaining_pct: geminiWkRem,
                reset_utc: weekly_reset_utc,
                reset_epoch: nil,
                severity: gemWkSev,
                bvi: bvi,
                bvi_status: bviStat,
                bvi_label: bvi_verdict
            )
        )
        let geminiTrack = QuotaTrack(
            id: "gemini",
            name: "Gemini 4 / 3.8",
            short_name: "Gemini",
            icon: "sparkles",
            is_primary: true,
            credit_spillover: true,
            windows: geminiWindows
        )

        var claudeWindows: [QuotaWindow] = []
        let claudeSev = claudeWkRem < 20.0 ? "critical" : (claudeWkRem < 40.0 ? "warning" : "safe")
        claudeWindows.append(
            QuotaWindow(
                window_id: "weekly",
                label: "Claude/GPT Weekly Runway",
                icon: "calendar",
                used_pct: claude_weekly_pct ?? max(0.0, 100.0 - claudeWkRem),
                remaining_pct: claudeWkRem,
                reset_utc: nil,
                reset_epoch: nil,
                severity: claudeSev
            )
        )
        let claudeTrack = QuotaTrack(
            id: "claude_gpt",
            name: "Claude & GPT Track",
            short_name: "Claude/GPT",
            icon: "sparkle",
            is_primary: false,
            credit_spillover: false,
            windows: claudeWindows
        )

        return [geminiTrack, claudeTrack]
    }

    public var lastTurnTtftMs: Double? {
        return last_turn_ttft_ms ?? live_ticker?.lastTurnTtftMs
    }

    public var lastTurnLatencyMs: Double? {
        return last_turn_latency_ms ?? live_ticker?.lastTurnLatencyMs
    }

    public var sessionMedianTtftMs: Double? {
        return session_median_ttft_ms ?? live_ticker?.sessionMedianTtftMs
    }

    public var kvCacheWiped: Bool {
        return (kv_cache_wiped ?? false) || (live_ticker?.kvCacheWiped ?? false)
    }

    public var formattedTtftLatency: String? {
        guard let ttft = lastTurnTtftMs, ttft > 0 else {
            if let lat = lastTurnLatencyMs, lat > 0 {
                let latStr = lat >= 1000.0 ? String(format: "%.1fs", lat / 1000.0) : "\(Int(round(lat)))ms"
                return latStr
            }
            return nil
        }
        let ttftStr = ttft >= 1000.0 ? String(format: "%.1fs", ttft / 1000.0) : "\(Int(round(ttft)))ms"
        if let lat = lastTurnLatencyMs, lat > 0 {
            let latStr = lat >= 1000.0 ? String(format: "%.1fs", lat / 1000.0) : "\(Int(round(lat)))ms"
            return "TTFT \(ttftStr) · \(latStr)"
        }
        return "TTFT \(ttftStr)"
    }

    public var totalActiveAgentsCount: Int {
        guard let swarms = active_swarms else { return 0 }
        var count = 0
        for s in swarms {
            if s.orchestrator != nil { count += 1 }
            count += s.subagents?.count ?? 0
        }
        return count
    }

    public var isStreamingActive: Bool {
        return (is_streaming ?? false) || (recent_burn_rate_tok_per_min ?? 0) > 0
    }

    public var formattedBurnRate: String {
        let rate = recent_burn_rate_tok_per_min ?? 0
        if rate >= 1_000_000 {
            return String(format: "%.1fM/m", Double(rate) / 1_000_000.0)
        } else if rate >= 1_000 {
            return String(format: "%.0fk/m", Double(rate) / 1_000.0)
        } else if rate > 0 {
            return "\(rate)/m"
        } else {
            return "0/m"
        }
    }

    public static func formatCompactTokens(_ value: Int?) -> String {
        let tok = value ?? 0
        if tok >= 1_000_000 {
            return String(format: "%.1fM", Double(tok) / 1_000_000.0)
        } else if tok >= 1_000 {
            let k = Double(tok) / 1_000.0
            if tok >= 100_000 || tok % 1_000 == 0 {
                return String(format: "%.0fk", k)
            }
            return String(format: "%.1fk", k)
        } else {
            return "\(tok)"
        }
    }

    public var formattedLastTurnTokens: String {
        let tok = last_turn_tokens ?? 0
        if tok >= 1_000_000 {
            return String(format: "%.2fM", Double(tok) / 1_000_000.0)
        } else if tok >= 1_000 {
            return String(format: "%.1fk", Double(tok) / 1_000.0)
        } else {
            return "\(tok)"
        }
    }

    public var formatted5hTokens: String {
        return StatusModel.formatCompactTokens(gemini_5h_tokens)
    }

    public var formattedLastTurnCache: String {
        let pct = last_turn_cache_pct ?? 0.0
        return String(format: "%.1f%% Cache", pct)
    }

    public var gemini5hRem: Double {
        if let rem = gemini_5h_remaining_pct { return rem }
        if let used = gemini_5h_pct { return max(0.0, min(100.0, 100.0 - used)) }
        return 100.0
    }

    public var geminiWkRem: Double {
        if let rem = gemini_weekly_remaining_pct { return rem }
        if let used = gemini_weekly_pct { return max(0.0, min(100.0, 100.0 - used)) }
        return 100.0
    }

    public var claudeWkRem: Double {
        if let rem = claude_weekly_remaining_pct { return rem }
        if let used = claude_weekly_pct { return max(0.0, min(100.0, 100.0 - used)) }
        return 100.0
    }

    public var is5hCritical: Bool {
        if (cooldown_active ?? false) { return true }
        if let primaryTrack = tracks?.first(where: { $0.is_primary }),
           let burstWin = primaryTrack.windows.first(where: { $0.window_id == "5h" }) {
            if burstWin.is_cooldown == true { return true }
            if burstWin.severity == "critical" { return true }
            if burstWin.remaining_pct < 15.0 { return true }
        }
        if gemini5hRem < 15.0 { return true }
        if let s = status, (s == "BURNING_AI_CREDITS" || s == "BURNING_OVERAGE") && gemini5hRem <= 0.0 {
            return true
        }
        return false
    }

    public var is5hWarning: Bool {
        if is5hCritical { return false }
        if let primaryTrack = tracks?.first(where: { $0.is_primary }),
           let burstWin = primaryTrack.windows.first(where: { $0.window_id == "5h" }) {
            if burstWin.severity == "warning" { return true }
            return burstWin.remaining_pct <= 35.0
        }
        if let s = status, s == "RECOVERED_COOLDOWN" { return true }
        return gemini5hRem <= 35.0
    }

    public var isWeeklyCritical: Bool {
        if let primaryTrack = tracks?.first(where: { $0.is_primary }),
           let weeklyWin = primaryTrack.windows.first(where: { $0.window_id == "weekly" }) {
            if weeklyWin.severity == "critical" { return true }
            if weeklyWin.remaining_pct < 20.0 { return true }
        }
        if geminiWkRem < 20.0 { return true }
        if let s = status {
            if s == "WEEKLY_EXHAUSTED" || s.contains("EXHAUSTED") { return true }
            if (s == "BURNING_AI_CREDITS" || s == "BURNING_OVERAGE") && geminiWkRem <= 0.0 { return true }
        }
        return false
    }

    public var isWeeklyWarning: Bool {
        if isWeeklyCritical { return false }
        if let primaryTrack = tracks?.first(where: { $0.is_primary }),
           let weeklyWin = primaryTrack.windows.first(where: { $0.window_id == "weekly" }) {
            if weeklyWin.severity == "warning" { return true }
            if weeklyWin.bvi_status == "deficit" || weeklyWin.bvi_status == "overburn" { return true }
            if (weeklyWin.bvi ?? 1.0) > 1.3 { return true }
            return weeklyWin.remaining_pct < 40.0
        }
        if geminiWkRem < 40.0 { return true }
        if (bvi ?? 1.0) > 1.3 { return true }
        if let v = bvi_verdict?.lowercased(), v.contains("deficit") || v.contains("overburn") {
            return true
        }
        return false
    }

    public var isCritical: Bool {
        if is5hCritical || isWeeklyCritical { return true }
        if let s = status {
            if s == "WEEKLY_EXHAUSTED" || s.contains("EXHAUSTED") || s == "BURNING_AI_CREDITS" || s == "BURNING_OVERAGE" {
                return true
            }
        }
        return false
    }

    public var isWarning: Bool {
        if isCritical { return false }
        return is5hWarning || isWeeklyWarning
    }

    public var isHealthy: Bool {
        return !isCritical && !isWarning
    }

    public var healthColor: Color {
        if isCritical { return .red }
        if isWarning { return .orange }
        return Color(red: 5/255.0, green: 150/255.0, blue: 105/255.0) // Deep Forest Emerald
    }

    /// High-contrast primary text color for 5h burst metric; shifts to amber/red only during 5h warning/critical states.
    public var textHealthColor: Color {
        if is5hCritical { return .red }
        if is5hWarning { return .orange }
        return .primary
    }

    /// Calm, high-contrast forest emerald for the 5h burst progress bar (Option A / Milestone 41).
    public var burstBarColor: Color {
        if is5hCritical { return .red }
        if is5hWarning { return .orange }
        return Color(red: 5/255.0, green: 150/255.0, blue: 105/255.0) // Deep Forest Emerald (#059669)
    }

    /// High-contrast primary text color for Weekly Quota Runway percentage; shifts to amber/red on weekly warning/critical.
    public var weeklyTextHealthColor: Color {
        if isWeeklyCritical { return .red }
        if isWeeklyWarning { return .orange }
        return .primary
    }

    /// Progress bar color for Weekly Quota Runway, reflecting both remaining quota and BVI pacing deficit.
    public var weeklyBarColor: Color {
        if isWeeklyCritical { return .red }
        if isWeeklyWarning { return .orange }
        return .blue
    }

    /// Sub-label color for Weekly BVI pacing verdict.
    public var weeklyVerdictColor: Color {
        if isWeeklyCritical { return .red }
        if isWeeklyWarning { return .orange }
        return .secondary
    }

    /// Clean live streaming indicator dot accent.
    public var streamingDotColor: Color {
        return Color(red: 16/255.0, green: 185/255.0, blue: 129/255.0) // Vibrant Mint Emerald (#10B981)
    }

    public var healthNSColor: NSColor {
        if isCritical { return .systemRed }
        if isWarning { return .systemOrange }
        return .labelColor // Adaptive monochrome for menu bar
    }

    /// Independent Menu Bar NSColor for Weekly Quota indicator (turns amber/red only on weekly risk).
    public var weeklyHealthNSColor: NSColor {
        if isWeeklyCritical { return .systemRed }
        if isWeeklyWarning { return .systemOrange }
        return .labelColor
    }

    /// Independent Menu Bar NSColor for 5-Hour Burst indicator (turns amber/red only on 5h burst risk).
    public var burstHealthNSColor: NSColor {
        if is5hCritical { return .systemRed }
        if is5hWarning { return .systemOrange }
        return .labelColor
    }
}
