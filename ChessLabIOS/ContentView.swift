import SwiftUI

// First native iPhone UI prototype. Chess legality and the original Python
// analysis engine are NOT yet ported; this is intentionally not a playable release.
struct ContentView: View {
    @State private var flipped = false
    @State private var selected: Int? = nil
    @State private var board: [String] = [
        "♜","♞","♝","♛","♚","♝","♞","♜",
        "♟","♟","♟","♟","♟","♟","♟","♟",
        "","","","","","","","",
        "","","","","","","","",
        "","","","","","","","",
        "","","","","","","","",
        "♙","♙","♙","♙","♙","♙","♙","♙",
        "♖","♘","♗","♕","♔","♗","♘","♖"
    ]
    private let start = [
        "♜","♞","♝","♛","♚","♝","♞","♜",
        "♟","♟","♟","♟","♟","♟","♟","♟",
        "","","","","","","","",
        "","","","","","","","",
        "","","","","","","","",
        "","","","","","","","",
        "♙","♙","♙","♙","♙","♙","♙","♙",
        "♖","♘","♗","♕","♔","♗","♘","♖"
    ]
    var body: some View {
        VStack(spacing: 18) {
            Text("ChessLab").font(.largeTitle.bold())
            Text("iPhone interface prototype").foregroundStyle(.secondary)
            GeometryReader { geometry in
                let side = min(geometry.size.width, geometry.size.height)
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 0), count: 8), spacing: 0) {
                    ForEach(0..<64, id: \.self) { shownIndex in
                        let idx = flipped ? 63 - shownIndex : shownIndex
                        let row = shownIndex / 8
                        let col = shownIndex % 8
                        Button { selected = idx } label: {
                            ZStack {
                                Rectangle()
                                    .fill(selected == idx ? Color.orange.opacity(0.7) :
                                        (row + col).isMultiple(of: 2)
                                        ? Color(red: 0.78, green: 0.87, blue: 0.96)
                                        : Color(red: 0.23, green: 0.42, blue: 0.62))
                                Text(board[idx])
                                    .font(.system(size: side / 11))
                                    .foregroundColor(board[idx].unicodeScalars.first.map { $0.value <= 0x2659 } == true
                                        ? .black : .white)
                                    .shadow(color: .black.opacity(0.6), radius: 1)
                            }
                            .frame(width: side / 8, height: side / 8)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(width: side, height: side)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .aspectRatio(1, contentMode: .fit)
            HStack {
                Button("New game") { board = start; selected = nil }
                Spacer()
                Button("Flip board") { flipped.toggle(); selected = nil }
            }
            .buttonStyle(.borderedProminent)
            Text("Board preview only — no legal moves or engine analysis yet.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .padding()
    }
}
