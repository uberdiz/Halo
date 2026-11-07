import Foundation

/// One of the PC's screens, from the host's `monitors` control message (docs/REMOTE_DESKTOP.md). The same rules as
/// the browser client's `screenChoices` (web/remote/js/client.js).
public struct RemoteMonitor: Equatable, Identifiable {
    public var id: Int { index }
    public let index: Int
    public let name: String
    public let width: Int
    public let height: Int

    public var label: String { width > 0 && height > 0 ? "\(name) (\(width)×\(height))" : name }

    /// `{type: "monitors", active, screens: [{index, name, w, h, x, y}]}` -> the screens and the one streamed.
    public static func parse(_ m: [String: Any]) -> (screens: [RemoteMonitor], active: Int)? {
        guard m["type"] as? String == "monitors", let list = m["screens"] as? [[String: Any]] else { return nil }
        let screens = list.compactMap { s -> RemoteMonitor? in
            guard let i = intValue(s["index"]) else { return nil }
            return RemoteMonitor(index: i, name: (s["name"] as? String) ?? "Screen \(i + 1)",
                                 width: intValue(s["w"]) ?? 0, height: intValue(s["h"]) ?? 0)
        }
        return (screens, intValue(m["active"]) ?? 0)
    }

    public static func select(_ index: Int) -> [String: Any] { ["type": "monitor.select", "index": index] }

    /// JSON numbers arrive as NSNumber; a Bool is an NSNumber too and must not count as an index.
    private static func intValue(_ v: Any?) -> Int? {
        guard let n = v as? NSNumber, RemoteProtocol.numberKind(n) != "b" else { return nil }
        let d = n.doubleValue
        return d == d.rounded() ? n.intValue : nil
    }
}

/// When a remote-desktop session that ended reconnects by itself (same policy as `shouldRetry` in client.js).
public enum RemoteReconnect {
    public static let limit = 5

    public static func shouldRetry(_ reason: String, wasConnected: Bool, retries: Int) -> Bool {
        if retries >= limit { return false }
        if reason == "connection_lost" { return true }
        return wasConnected && ["offline", "timeout", "connect_timeout"].contains(reason)
    }

    /// Seconds before attempt number `retries` (1-based): 2, 4, 8, then 15.
    public static func delay(_ retries: Int) -> Double { min(pow(2.0, Double(retries)), 15) }
}
