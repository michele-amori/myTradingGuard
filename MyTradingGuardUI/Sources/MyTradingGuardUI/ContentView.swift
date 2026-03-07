import SwiftUI

// MARK: - Root view (handles launch state)

struct RootView: View {
    @StateObject private var launcher = LaunchManager()
    @StateObject private var model    = StatusModel()

    var body: some View {
        Group {
            switch launcher.launchState {

            case .checkingSetup:
                WaitingView(icon: "bolt.circle",
                            title: "MyTradingGuard",
                            message: "Checking setup…")

            case .notConfigured:
                WaitingView(icon: "exclamationmark.triangle",
                            title: "Setup required",
                            message: "Run setup_macos.sh once before using the app.\n\nOpen Terminal, go to the project folder and run:\n  bash setup_macos.sh",
                            isWarning: true)

            case .startingProxy:
                WaitingView(icon: "bolt.circle",
                            title: "Starting MyTradingGuard…",
                            message: "A Terminal window has opened to start the proxy and TradingView.\nThis window will update automatically when ready.")

            case .running:
                ContentView(model: model)

            case .error(let msg):
                WaitingView(icon: "xmark.circle",
                            title: "Error",
                            message: msg,
                            isWarning: true)
            }
        }
        .frame(minWidth: 680, minHeight: 520)
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear { launcher.start() }
    }
}

// MARK: - Root window

struct ContentView: View {
    @ObservedObject var model: StatusModel

    var body: some View {
        Group {
            if let state = model.state {
                DashboardView(state: state)
            } else {
                WaitingView(icon: "bolt.circle",
                            title: "MyTradingGuard",
                            message: model.connectionError ?? "Loading…")
            }
        }
        .frame(minWidth: 680, minHeight: 520)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - Waiting / connecting screen

struct WaitingView: View {
    var icon: String = "bolt.circle"
    var title: String = "MyTradingGuard"
    var message: String
    var isWarning: Bool = false

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 56))
                .foregroundStyle(isWarning ? Color.orange : Color.secondary)
            Text(title)
                .font(.title.bold())
            Text(message)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(40)
    }
}

// MARK: - Main dashboard

struct DashboardView: View {
    let state: UIState

    var body: some View {
        VStack(spacing: 0) {
            HeaderView(state: state)
            Divider()
            HStack(alignment: .top, spacing: 0) {
                RulesPanel(rules: state.rules)
                Divider()
                EventsPanel(events: state.events)
            }
            .frame(maxHeight: .infinity)
            Divider()
            FooterView(state: state)
        }
    }
}

// MARK: - Header

struct HeaderView: View {
    let state: UIState

    var body: some View {
        HStack(spacing: 16) {
            // Icon + title
            HStack(spacing: 8) {
                Image(systemName: "bolt.fill")
                    .foregroundStyle(.yellow)
                Text("MyTradingGuard")
                    .font(.title2.bold())
            }

            Spacer()

            // Timestamp
            Text(state.timestamp)
                .font(.callout)
                .foregroundStyle(.secondary)
                .monospacedDigit()

            Spacer()

            // Global status badge
            StatusBadge(blocked: state.tradingBlocked)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(Color(NSColor.controlBackgroundColor))
    }
}

struct StatusBadge: View {
    let blocked: Bool

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(blocked ? Color.red : Color.green)
                .frame(width: 10, height: 10)
                .shadow(color: blocked ? .red : .green, radius: 4)
            Text(blocked ? "TRADING BLOCKED" : "TRADING ENABLED")
                .font(.callout.bold())
                .foregroundStyle(blocked ? .red : .green)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill((blocked ? Color.red : Color.green).opacity(0.12))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke((blocked ? Color.red : Color.green).opacity(0.4), lineWidth: 1)
                )
        )
    }
}

// MARK: - Rules panel

struct RulesPanel: View {
    let rules: [RuleState]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            PanelHeader(title: "Active Rules", icon: "list.bullet.clipboard")
            Divider()
            ScrollView {
                VStack(spacing: 1) {
                    ForEach(rules) { rule in
                        RuleRow(rule: rule)
                        if rule.id != rules.last?.id {
                            Divider().padding(.leading, 44)
                        }
                    }
                }
                .padding(.vertical, 8)
            }
        }
        .frame(minWidth: 340)
    }
}

struct RuleRow: View {
    let rule: RuleState

    private var indicatorColor: Color {
        if !rule.active { return .gray }
        return rule.ok ? .green : .red
    }

    private var indicatorSymbol: String {
        if !rule.active { return "minus.circle" }
        return rule.ok ? "checkmark.circle.fill" : "xmark.circle.fill"
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: indicatorSymbol)
                .foregroundStyle(indicatorColor)
                .font(.system(size: 18))
                .frame(width: 24)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 4) {
                Text(rule.name)
                    .font(.callout.bold())
                    .foregroundStyle(rule.active ? .primary : .tertiary)

                Text(rule.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                // Progress bar (for count-based rules)
                if let p = rule.progress, let max = rule.progressMax, max > 0 {
                    ProgressView(value: Double(min(p, max)), total: Double(max))
                        .tint(p >= max ? .red : .green)
                        .frame(maxWidth: 180)
                }
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(
            rule.active && !rule.ok
                ? Color.red.opacity(0.06)
                : Color.clear
        )
    }
}

// MARK: - Events panel

struct EventsPanel: View {
    let events: [EventState]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            PanelHeader(title: "Recent Events", icon: "clock.arrow.circlepath")
            Divider()
            if events.isEmpty {
                VStack {
                    Spacer()
                    Text("No events yet")
                        .foregroundStyle(.tertiary)
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(events) { ev in
                            EventRow(event: ev)
                            if ev.id != events.last?.id {
                                Divider().padding(.leading, 44)
                            }
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(minWidth: 260)
    }
}

struct EventRow: View {
    let event: EventState

    private var icon: String {
        switch event.kind {
        case "BLOCKED": return "xmark.circle.fill"
        case "PASSED":  return "checkmark.circle.fill"
        case "LOSS":    return "arrow.down.circle.fill"
        case "WIN":     return "arrow.up.circle.fill"
        default:        return "circle.fill"
        }
    }

    private var color: Color {
        switch event.kind {
        case "BLOCKED", "LOSS": return .red
        case "PASSED", "WIN":   return .green
        default:                return .gray
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .font(.system(size: 16))
                .frame(width: 20)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(event.kind)
                        .font(.caption.bold())
                        .foregroundStyle(color)
                    Spacer()
                    Text(event.time)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .monospacedDigit()
                }
                Text(event.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }
}

// MARK: - Footer

struct FooterView: View {
    let state: UIState

    var body: some View {
        HStack(spacing: 20) {
            Label("Proxy ::\(state.proxyPort)", systemImage: "network")
            Label("\(state.broker) (\(state.brokerEnv))", systemImage: "building.columns")
            Label("\(state.dailyCount) trade(s) today", systemImage: "chart.bar")
            Label("\(state.dailyLosses) loss(es) today", systemImage: "minus.circle")
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.horizontal, 20)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.controlBackgroundColor))
    }
}

// MARK: - Shared panel header

struct PanelHeader: View {
    let title: String
    let icon: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .font(.callout)
            Text(title)
                .font(.callout.bold())
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.controlBackgroundColor))
    }
}
