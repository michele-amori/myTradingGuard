import Foundation
import Combine

// MARK: - Data models

struct RuleState: Identifiable, Decodable {
    let id = UUID()
    let name: String
    let active: Bool
    let ok: Bool
    let detail: String
    let progress: Int?
    let progressMax: Int?

    enum CodingKeys: String, CodingKey {
        case name, active, ok, detail, progress
        case progressMax = "progress_max"
    }
}

struct EventState: Identifiable, Decodable {
    let id = UUID()
    let time: String
    let kind: String
    let detail: String

    enum CodingKeys: String, CodingKey {
        case time, kind, detail
    }
}

struct UIState: Decodable {
    let timestamp: String
    let timezone: String
    let tradingBlocked: Bool
    let blockReason: String
    let broker: String
    let brokerEnv: String
    let proxyPort: Int
    let dailyCount: Int
    let dailyLosses: Int
    let rules: [RuleState]
    let events: [EventState]

    enum CodingKeys: String, CodingKey {
        case timestamp, timezone, broker, events, rules
        case tradingBlocked  = "trading_blocked"
        case blockReason     = "block_reason"
        case brokerEnv       = "broker_env"
        case proxyPort       = "proxy_port"
        case dailyCount      = "daily_count"
        case dailyLosses     = "daily_losses"
    }
}

// MARK: - Observable model

@MainActor
final class StatusModel: ObservableObject {

    @Published var state: UIState? = nil
    @Published var lastUpdated: Date = .distantPast
    @Published var connectionError: String? = nil

    private let stateFile: URL
    private var timer: Timer?

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        stateFile = home
            .appendingPathComponent(".mytradingguard")
            .appendingPathComponent("ui_state.json")
        start()
    }

    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.reload()
            }
        }
        reload()
    }

    private func reload() {
        guard FileManager.default.fileExists(atPath: stateFile.path) else {
            connectionError = "Waiting for MyTradingGuard to start…"
            return
        }
        do {
            let data = try Data(contentsOf: stateFile)
            let decoded = try JSONDecoder().decode(UIState.self, from: data)
            state = decoded
            lastUpdated = Date()
            connectionError = nil
        } catch {
            connectionError = "Parse error: \(error.localizedDescription)"
        }
    }
}
