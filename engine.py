"""Original educational engine; python-chess supplies rules only."""
import time
from dataclasses import dataclass
import chess

VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 335,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
MATE = 100000

@dataclass
class Result:
    move: object
    score: int
    depth: int
    nodes: int
    seconds: float

class Engine:
    def evaluate(self, board):
        score = 0
        endgame = len(board.piece_map()) <= 12
        for color in (chess.WHITE, chess.BLACK):
            sign = 1 if color else -1
            pawns = board.pieces(chess.PAWN, color)
            enemy_pawns = board.pieces(chess.PAWN, not color)
            files = [sum(chess.square_file(s) == f for s in pawns) for f in range(8)]
            subtotal = 25 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0
            for sq, piece in board.piece_map().items():
                if piece.color != color:
                    continue
                f = chess.square_file(sq)
                r = chess.square_rank(sq) if color else 7 - chess.square_rank(sq)
                center = 7 - (abs(2*f-7) + abs(2*r-7))/2
                value = VALUES[piece.piece_type]
                if piece.piece_type == chess.PAWN:
                    value += r * 7 + center * 3
                    if files[f] > 1:
                        value -= 12
                    if not any(files[g] for g in (f-1, f+1) if 0 <= g < 8):
                        value -= 12
                    if not any(abs(chess.square_file(e)-f) <= 1 and
                               (chess.square_rank(e) > chess.square_rank(sq) if color else
                                chess.square_rank(e) < chess.square_rank(sq)) for e in enemy_pawns):
                        value += r*r * 3
                elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                    value += center * 10 + len(board.attacks(sq)) * 2
                elif piece.piece_type == chess.ROOK:
                    value += 15 if files[f] == 0 else 0
                    value += 20 if r == 6 else 0
                elif piece.piece_type == chess.QUEEN:
                    value += center * 3
                else:
                    if endgame:
                        value += center * 12
                    else:
                        value -= center * 8 + r * 12
                        value += 30 if r == 0 and f in (2, 6) else 0
                        for df in (-1, 0, 1):
                            if 0 <= f+df < 8 and r < 7:
                                shield = chess.square(f+df, r+1 if color else 6-r)
                                if board.piece_at(shield) == chess.Piece(chess.PAWN, color):
                                    value += 12
                subtotal += value
            score += sign * subtotal
        return int(score if board.turn else -score)

    def tick(self):
        self.nodes += 1
        if self.nodes % 64 == 0 and (time.monotonic() >= self.deadline or self.cancel is not None and self.cancel.is_set()):
            raise TimeoutError

    def terminal(self, b, ply):
        if b.is_checkmate():
            return -MATE + ply
        if b.is_stalemate() or b.is_insufficient_material() or b.is_seventyfive_moves() or b.is_repetition(3):
            return 0
        return None

    def order(self, b, moves, preferred=None):
        def priority(m):
            if m == preferred:
                return 1000000
            v = VALUES[b.piece_type_at(m.to_square)] if b.piece_at(m.to_square) else 0
            if b.is_en_passant(m):
                v = 100
            return (10000 + 10*v - VALUES[b.piece_type_at(m.from_square)] if b.is_capture(m) else 0) + (VALUES.get(m.promotion, 0)*10)
        return sorted(moves, key=priority, reverse=True)

    def quiet(self, b, alpha, beta, ply, remaining=8):
        self.tick()
        terminal = self.terminal(b, ply)
        if terminal is not None:
            return terminal
        check = b.is_check()
        if remaining <= 0:
            return self.evaluate(b)
        if not check:
            stand = self.evaluate(b)
            if stand >= beta:
                return stand
            alpha = max(alpha, stand)
        moves = list(b.legal_moves)
        if not check:
            moves = [m for m in moves if b.is_capture(m) or m.promotion]
        for m in self.order(b, moves):
            b.push(m)
            try:
                score = -self.quiet(b, -beta, -alpha, ply+1, remaining-1)
            finally:
                b.pop()
            if score >= beta:
                return score
            alpha = max(alpha, score)
        return alpha

    def search(self, b, depth, alpha, beta, ply):
        self.tick()
        terminal = self.terminal(b, ply)
        if terminal is not None:
            return terminal
        if depth <= 0:
            return self.quiet(b, alpha, beta, ply)
        # Include history: repetition-sensitive scores must not leak across paths.
        key = (b.fen(), tuple(m.uci() for m in b.move_stack))
        entry = self.table.get(key)
        original_alpha = alpha
        preferred = entry[3] if entry else None
        if entry and entry[0] >= depth and abs(entry[1]) < MATE-1000:
            _, score, flag, _ = entry
            if flag == 'exact' or flag == 'lower' and score >= beta or flag == 'upper' and score <= alpha:
                return score
        best, best_move = -MATE*2, None
        for m in self.order(b, list(b.legal_moves), preferred):
            b.push(m)
            try:
                score = -self.search(b, depth-1, -beta, -alpha, ply+1)
            finally:
                b.pop()
            if score > best:
                best, best_move = score, m
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        flag = 'upper' if best <= original_alpha else 'lower' if best >= beta else 'exact'
        self.table[key] = (depth, best, flag, best_move)
        return best

    def choose(self, board, seconds=3.0, max_depth=8, cancel=None):
        self.cancel = cancel
        b = board.copy(stack=True)
        start = time.monotonic()
        self.deadline, self.nodes, self.table = start + seconds, 0, {}
        moves = list(b.legal_moves)
        if not moves or self.terminal(b, 0) is not None:
            return Result(None, self.terminal(b, 0) or 0, 0, 0, 0)
        best = moves[0]
        score, completed = self.evaluate(b), 0
        for depth in range(1, max_depth+1):
            alpha, iteration_move = -MATE*2, best
            try:
                for m in self.order(b, moves, best):
                    if (time.monotonic() >= self.deadline or self.cancel is not None and self.cancel.is_set()):
                        raise TimeoutError
                    b.push(m)
                    try:
                        v = -self.search(b, depth-1, -MATE*2, -alpha, 1)
                    finally:
                        b.pop()
                    if v > alpha:
                        alpha, iteration_move = v, m
            except TimeoutError:
                break
            best, score, completed = iteration_move, alpha, depth
            if abs(score) >= MATE-1000:
                break
        return Result(best, score, completed, self.nodes, time.monotonic()-start)
