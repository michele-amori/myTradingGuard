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

// MARK: - TradingView proxy status

enum TVProxyStatus {
    case notRunning          // TradingView is not open
    case runningWithProxy    // TradingView is open and routed through the proxy
    case runningWithoutProxy // TradingView is open but NOT using the proxy
}

// MARK: - Observable model

@MainActor
final class StatusModel: ObservableObject {

    @Published var state: UIState? = nil
    @Published var lastUpdated: Date = .distantPast
    @Published var connectionError: String? = nil
    @Published var tvProxyStatus: TVProxyStatus = .notRunning

    private let stateFile: URL
    private var stateTimer: Timer?
    private var tvCheckTimer: Timer?

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        stateFile = home
            .appendingPathComponent(".mytradingguard")
            .appendingPathComponent("ui_state.json")
        start()
    }

    func start() {
        // Reload ui_state.json every second
        stateTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.reload() }
        }
        // Check TradingView proxy status every 10 seconds
        tvCheckTimer = Timer.scheduledTimer(withTimeInterval: 10.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.checkTradingView() }
        }
        reload()
        checkTradingView()
    }

    // Called once at startup, then every 10 seconds
    private func checkTradingView() {
        let task = Process()
        task.launchPath = "/bin/ps"
        task.arguments = ["aux"]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            let lines = output.components(separatedBy: "\n")
            let tvLines = lines.filter {
                $0.contains("TradingView") && !$0.contains("grep") && !$0.contains("MyTradingGuard")
            }
            if tvLines.isEmpty {
                tvProxyStatus = .notRunning
            } else if tvLines.contains(where: { $0.contains("proxy-server") }) {
                tvProxyStatus = .runningWithProxy
            } else {
                tvProxyStatus = .runningWithoutProxy
            }
        } catch {
            tvProxyStatus = .notRunning
        }
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
