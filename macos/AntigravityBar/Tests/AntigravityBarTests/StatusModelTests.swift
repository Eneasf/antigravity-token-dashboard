import XCTest
import AppKit
import SwiftUI
@testable import AntigravityBar

final class StatusModelTests: XCTestCase {

    func testDeterministicIdentifiableIds() {
        let s1 = DegradedSession(
            convo_id: nil,
            title: "Refactor Telemetry",
            branch: "feat/m97",
            workspace: "Dashboard",
            tokens: 42000,
            compaction_epoch: 1
        )
        let s2 = DegradedSession(
            convo_id: nil,
            title: "Refactor Telemetry",
            branch: "feat/m97",
            workspace: "Dashboard",
            tokens: 42000,
            compaction_epoch: 1
        )
        XCTAssertEqual(s1.id, s2.id)
        XCTAssertEqual(s1.id, "Dashboard_feat/m97_Refactor Telemetry")

        let sub1 = ActiveSwarmSubagent(
            convo_id: nil,
            title: "Audit Worker",
            subagent_role: "challenger",
            tokens: 18000,
            compaction_epoch: 1
        )
        let sub2 = ActiveSwarmSubagent(
            convo_id: nil,
            title: "Audit Worker",
            subagent_role: "challenger",
            tokens: 18000,
            compaction_epoch: 1
        )
        XCTAssertEqual(sub1.id, sub2.id)
        XCTAssertEqual(sub1.id, "challenger_Audit Worker")

        let grp1 = ActiveSwarmGroup(
            workspace: "Dashboard",
            branch: "main",
            worst_severity: "safe",
            orchestrator: nil,
            subagents: [sub1]
        )
        let grp2 = ActiveSwarmGroup(
            workspace: "Dashboard",
            branch: "main",
            worst_severity: "safe",
            orchestrator: nil,
            subagents: [sub2]
        )
        XCTAssertEqual(grp1.id, grp2.id)
        XCTAssertEqual(grp1.id, "Dashboard_main_standalone")
    }

    func testFormatCompactTokens() {
        XCTAssertEqual(StatusModel.formatCompactTokens(nil), "0")
        XCTAssertEqual(StatusModel.formatCompactTokens(0), "0")
        XCTAssertEqual(StatusModel.formatCompactTokens(850), "850")
        XCTAssertEqual(StatusModel.formatCompactTokens(1500), "1.5k")
        XCTAssertEqual(StatusModel.formatCompactTokens(42000), "42k")
        XCTAssertEqual(StatusModel.formatCompactTokens(250000), "250k")
        XCTAssertEqual(StatusModel.formatCompactTokens(1250000), "1.2M")
    }

    func testQuotaHealthAndWarningThresholds() {
        var model = StatusModel()
        model.status = "SAFE_IN_QUOTA"
        model.gemini_5h_remaining_pct = 85.0
        model.gemini_weekly_remaining_pct = 75.0
        model.bvi = 1.0
        XCTAssertTrue(model.isHealthy)
        XCTAssertFalse(model.isWarning)
        XCTAssertFalse(model.isCritical)

        // 5h warning at <= 35%
        model.gemini_5h_remaining_pct = 30.0
        XCTAssertTrue(model.is5hWarning)
        XCTAssertFalse(model.isWeeklyWarning)
        XCTAssertTrue(model.isWarning)

        // Weekly warning via BVI > 1.3 even when remaining % is high
        model.gemini_5h_remaining_pct = 85.0
        model.bvi = 1.45
        XCTAssertFalse(model.is5hWarning)
        XCTAssertTrue(model.isWeeklyWarning)
        XCTAssertTrue(model.isWarning)

        // Critical when 5h < 15%
        model.gemini_5h_remaining_pct = 10.0
        XCTAssertTrue(model.is5hCritical)
        XCTAssertTrue(model.isCritical)
    }

    func testLiveTickerDecodingAndFormatting() throws {
        let json = """
        {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_remaining_pct": 92.5,
            "gemini_weekly_remaining_pct": 81.0,
            "live_ticker": {
                "last_turn_ttft_ms": 420.0,
                "last_turn_latency_ms": 1800.0,
                "session_median_ttft_ms": 390.0,
                "kv_cache_wiped": true
            }
        }
        """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(StatusModel.self, from: json)
        XCTAssertEqual(decoded.lastTurnTtftMs, 420.0)
        XCTAssertEqual(decoded.lastTurnLatencyMs, 1800.0)
        XCTAssertEqual(decoded.sessionMedianTtftMs, 390.0)
        XCTAssertTrue(decoded.kvCacheWiped)
        XCTAssertEqual(decoded.formattedTtftLatency, "TTFT 420ms · 1.8s")
    }

    func testV2TracksAndPlanDecoding() throws {
        let v2Json = """
        {
            "schema_version": 2,
            "generated_at_utc": "2026-11-11T12:00:00Z",
            "generated_at_epoch": 1794405600.0,
            "plan": {
                "tier_id": "ultra_5x",
                "name": "Google AI Ultra (5x)",
                "badge": "Ultra 5x",
                "credit_pool": 7500,
                "credits_remaining": 2350,
                "credit_balance_gbp": 22.55
            },
            "tracks": [
                {
                    "id": "gemini",
                    "name": "Gemini 4 / 3.8",
                    "short_name": "Gemini",
                    "icon": "sparkles",
                    "is_primary": true,
                    "credit_spillover": true,
                    "windows": [
                        {
                            "window_id": "5h",
                            "label": "5-Hour Burst Limit",
                            "icon": "bolt.fill",
                            "used_pct": 1.3,
                            "remaining_pct": 98.7,
                            "used_tokens": 3416400,
                            "reset_utc": "2026-11-11T14:12:00Z",
                            "reset_epoch": 1794413520.0,
                            "is_cooldown": false,
                            "severity": "safe"
                        },
                        {
                            "window_id": "weekly",
                            "label": "Weekly Quota Runway",
                            "icon": "calendar",
                            "used_pct": 71.6,
                            "remaining_pct": 28.4,
                            "reset_utc": "2026-11-14T09:00:28Z",
                            "reset_epoch": 1794646828.0,
                            "bvi": 1.17,
                            "bvi_status": "deficit",
                            "bvi_pacing_pct": -0.1,
                            "bvi_label": "Day 5: -0.1% deficit",
                            "severity": "warning"
                        }
                    ]
                },
                {
                    "id": "claude_gpt",
                    "name": "Claude & GPT Track",
                    "short_name": "Claude/GPT",
                    "icon": "sparkle",
                    "is_primary": false,
                    "credit_spillover": false,
                    "windows": [
                        {
                            "window_id": "weekly",
                            "label": "Claude/GPT Weekly Runway",
                            "used_pct": 50.1,
                            "remaining_pct": 49.9,
                            "severity": "safe"
                        }
                    ]
                },
                {
                    "id": "openai_custom",
                    "name": "OpenAI Custom Track",
                    "short_name": "OpenAI",
                    "icon": "cpu",
                    "is_primary": false,
                    "credit_spillover": false,
                    "windows": [
                        {
                            "window_id": "weekly",
                            "label": "OpenAI Allowance",
                            "used_pct": 0.0,
                            "remaining_pct": 100.0,
                            "severity": "safe"
                        }
                    ]
                }
            ]
        }
        """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(StatusModel.self, from: v2Json)
        XCTAssertEqual(decoded.schema_version, 2)
        XCTAssertEqual(decoded.resolvedPlan.name, "Google AI Ultra (5x)")
        XCTAssertEqual(decoded.resolvedPlan.credits_remaining, 2350)
        XCTAssertEqual(decoded.resolvedPlan.credit_balance_gbp, 22.55)

        XCTAssertEqual(decoded.resolvedTracks.count, 3)
        let primary = decoded.resolvedTracks.first(where: { $0.is_primary })
        XCTAssertNotNil(primary)
        XCTAssertEqual(primary?.id, "gemini")
        XCTAssertEqual(primary?.windows.count, 2)

        let weeklyWin = primary?.windows.first(where: { $0.window_id == "weekly" })
        XCTAssertEqual(weeklyWin?.remaining_pct, 28.4)
        XCTAssertEqual(weeklyWin?.severity, "warning")
        XCTAssertEqual(weeklyWin?.bvi_status, "deficit")

        // 3rd track is decoded cleanly
        let thirdTrack = decoded.resolvedTracks.first(where: { $0.id == "openai_custom" })
        XCTAssertNotNil(thirdTrack)
        XCTAssertEqual(thirdTrack?.name, "OpenAI Custom Track")
        XCTAssertEqual(thirdTrack?.windows.first?.used_pct, 0.0)
    }

    func testV1LegacyFlatFallbackSynthesis() throws {
        let v1Json = """
        {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_pct": 10.0,
            "gemini_5h_remaining_pct": 90.0,
            "gemini_weekly_pct": 30.0,
            "gemini_weekly_remaining_pct": 70.0,
            "claude_weekly_pct": 20.0,
            "claude_weekly_remaining_pct": 80.0,
            "bvi": 0.95,
            "bvi_verdict": "On Track",
            "plan_name": "Google One AI Pro"
        }
        """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(StatusModel.self, from: v1Json)
        XCTAssertNil(decoded.tracks)
        XCTAssertEqual(decoded.resolvedTracks.count, 2)

        let gemini = decoded.resolvedTracks[0]
        XCTAssertEqual(gemini.id, "gemini")
        XCTAssertTrue(gemini.is_primary)
        XCTAssertEqual(gemini.windows.count, 2)
        XCTAssertEqual(gemini.windows[0].remaining_pct, 90.0)
        XCTAssertEqual(gemini.windows[1].remaining_pct, 70.0)

        let claude = decoded.resolvedTracks[1]
        XCTAssertEqual(claude.id, "claude_gpt")
        XCTAssertFalse(claude.is_primary)
        XCTAssertEqual(claude.windows[0].remaining_pct, 80.0)

        XCTAssertEqual(decoded.resolvedPlan.name, "Google One AI Pro")
    }

    func testOpenDashboardURLConstructionWithoutCorruptedHash() {
        let basePath = "/Users/test/Documents/dashboard/index.html"
        let normalUrl = StatusStore.constructDashboardURL(targetPath: basePath)
        XCTAssertTrue(normalUrl.hasPrefix("file:///"))
        XCTAssertFalse(normalUrl.contains("#"))

        let tabSwarmsUrl = StatusStore.constructDashboardURL(targetPath: basePath, tab: "tab-swarms")
        XCTAssertTrue(tabSwarmsUrl.hasSuffix("#tab-swarms"))
        XCTAssertFalse(tabSwarmsUrl.contains("%23"), "URL must NOT percent-encode '#' into '%23'!")

        let hashPrefixedUrl = StatusStore.constructDashboardURL(targetPath: basePath, tab: "#tab-billing")
        XCTAssertTrue(hashPrefixedUrl.hasSuffix("#tab-billing"))
        XCTAssertFalse(hashPrefixedUrl.contains("%23"))
    }

    func testRefreshNowWritesSignalFileInCustomPath() {
        let tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let signalFile = tempDir.appendingPathComponent(".antigravity_refresh_requested")
        let store = StatusStore(initialStatus: StatusModel())
        store.customSignalURL = signalFile

        XCTAssertFalse(FileManager.default.fileExists(atPath: signalFile.path))

        let exp = expectation(description: "Signal file written")
        store.refreshNow()

        DispatchQueue.global().asyncAfter(deadline: .now() + 0.3) {
            if FileManager.default.fileExists(atPath: signalFile.path) {
                exp.fulfill()
            }
        }

        waitForExpectations(timeout: 2.0)
        XCTAssertTrue(FileManager.default.fileExists(atPath: signalFile.path))
    }

    func testAbsenceOfEnglishProseScrapingInSwiftSource() throws {
        // Verify that PopoverContentView.swift has 0 NSRegularExpression and 0 replacingOccurrences
        let fileURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Sources/AntigravityBar/PopoverContentView.swift")

        let source = try String(contentsOf: fileURL, encoding: .utf8)
        XCTAssertFalse(source.contains("replacingOccurrences"), "PopoverContentView must have 0 .replacingOccurrences string hacks!")
        XCTAssertFalse(source.contains("NSRegularExpression"), "PopoverContentView must have 0 NSRegularExpression prose scraping!")
        XCTAssertFalse(source.contains("You have used some of your"), "PopoverContentView must not hardcode raw Gemini prose scraping!")
    }

    @MainActor
    func testPopoverLayoutSizingInNSHostingView() {
        var model = StatusModel()
        model.status = "SAFE_IN_QUOTA"
        model.gemini_5h_remaining_pct = 85.0
        model.gemini_weekly_remaining_pct = 75.0
        model.claude_weekly_remaining_pct = 90.0
        model.credit_balance = "4,850 / 5,000 credits (£38.32)"
        model.current_session = DegradedSession(
            convo_id: "c-root",
            title: "Main Orchestrator Session",
            branch: "main",
            workspace: "Antigravity Workspace",
            tokens: 64000,
            severity: "safe",
            is_current: true,
            headroom_to_warning: 123500,
            compaction_epoch: 1,
            compaction_threshold: 250000,
            is_weakest_link: false
        )
        let subagents = (1...8).map { i in
            ActiveSwarmSubagent(
                convo_id: "sub-\(i)",
                title: "Subagent Worker \(i)",
                subagent_role: "implementer",
                tokens: 45000 + i * 5000,
                threshold: 250000,
                compaction_epoch: 1,
                severity: "safe",
                is_weakest_link: false
            )
        }
        model.active_swarms = [
            ActiveSwarmGroup(
                workspace: "Project Alpha",
                branch: "main",
                worst_severity: "safe",
                orchestrator: model.current_session,
                subagents: subagents
            ),
            ActiveSwarmGroup(
                workspace: "Project Beta",
                branch: "feat/ui",
                worst_severity: "warning",
                orchestrator: model.current_session,
                subagents: subagents
            )
        ]
        model.degraded_sessions = (1...10).map { i in
            DegradedSession(
                convo_id: "hist-\(i)",
                title: "Historical Degraded Session \(i)",
                branch: "main",
                workspace: "Workspace \(i)",
                tokens: 210000 + i * 2000,
                severity: i % 2 == 0 ? "critical" : "warning",
                compaction_epoch: 2,
                compaction_threshold: 250000
            )
        }

        let store = StatusStore(initialStatus: model)
        let collapsedView = NSHostingView(rootView: PopoverContentView(store: store, isSessionsExpanded: false, isSwarmsExpanded: false))
        collapsedView.layoutSubtreeIfNeeded()
        let collapsedSize = collapsedView.fittingSize

        let expandedView = NSHostingView(rootView: PopoverContentView(store: store, isSessionsExpanded: true, isSwarmsExpanded: true))
        expandedView.layoutSubtreeIfNeeded()
        let expandedSize = expandedView.fittingSize

        // Verify a single small swarm group does not greedily inflate to 220pt when expanded
        var smallSwarmModel = model
        smallSwarmModel.active_swarms = [
            ActiveSwarmGroup(
                workspace: "Project Solo",
                branch: "main",
                worst_severity: "safe",
                orchestrator: model.current_session,
                subagents: []
            )
        ]
        let smallSwarmStore = StatusStore(initialStatus: smallSwarmModel)
        let smallSwarmExpandedView = NSHostingView(rootView: PopoverContentView(store: smallSwarmStore, isSessionsExpanded: false, isSwarmsExpanded: true))
        smallSwarmExpandedView.layoutSubtreeIfNeeded()
        let smallSwarmSize = smallSwarmExpandedView.fittingSize

        XCTAssertEqual(collapsedSize.width, 385, accuracy: 1.0)
        XCTAssertEqual(expandedSize.width, 385, accuracy: 1.0)
        XCTAssertGreaterThan(smallSwarmSize.height, collapsedSize.height)
        XCTAssertLessThan(smallSwarmSize.height - collapsedSize.height, 90.0)
        XCTAssertLessThanOrEqual(expandedSize.height, 725.0)
    }
}
