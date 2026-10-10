import SwiftUI

enum MS {
    static let background = Color(red: 0.026, green: 0.065, blue: 0.116)
    static let panel = Color(red: 0.060, green: 0.134, blue: 0.213)
    static let panel2 = Color(red: 0.092, green: 0.191, blue: 0.288)
    static let cyan = Color(red: 0.025, green: 0.795, blue: 0.950)
    static let muted = Color(red: 0.670, green: 0.756, blue: 0.825)
}

struct MSCard<Content: View>: View {
    @ViewBuilder let content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12, content: content)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(MS.panel, in: RoundedRectangle(cornerRadius: 16))
    }
}

struct MSButton: View {
    let title: String
    var systemImage: String? = nil
    var prominent: Bool = true
    var action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                Text(title).fontWeight(.semibold)
                if let systemImage { Image(systemName: systemImage) }
            }
            .frame(maxWidth: .infinity, minHeight: 51)
            .foregroundStyle(prominent ? Color.black : Color.white)
            .background(prominent ? MS.cyan : MS.panel2, in: RoundedRectangle(cornerRadius: 12))
        }
        .accessibilityLabel(title)
    }
}

struct SectionTitle: View {
    let text: String
    var body: some View { Text(text).font(.title3.bold()).frame(maxWidth: .infinity, alignment: .leading) }
}

struct Notice: View {
    let text: String
    var symbol: String = "info.circle"
    var body: some View {
        Label(text, systemImage: symbol)
            .font(.footnote)
            .foregroundStyle(MS.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(MS.panel2, in: RoundedRectangle(cornerRadius: 12))
    }
}

extension View {
    func msScreen() -> some View {
        self
            .foregroundStyle(.white)
            .background(MS.background.ignoresSafeArea())
            .toolbarBackground(MS.background, for: .navigationBar)
            .tint(MS.cyan)
    }
}
