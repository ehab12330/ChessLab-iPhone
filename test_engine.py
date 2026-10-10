import unittest
import chess
from engine import Engine, MATE

class EngineTests(unittest.TestCase):
    def test_legal_and_no_mutation(self):
        b=chess.Board(); b.push_san('e4'); original=b.fen(); history=list(b.move_stack)
        r=Engine().choose(b,0.2)
        self.assertIn(r.move,b.legal_moves)
        self.assertEqual(b.fen(),original); self.assertEqual(b.move_stack,history)
    def test_mate_in_one(self):
        b=chess.Board('7k/5Q2/6K1/8/8/8/8/8 w - - 0 1')
        r=Engine().choose(b,1)
        b.push(r.move); self.assertTrue(b.is_checkmate())
        self.assertGreater(r.score,MATE-100)
    def test_terminal(self):
        b=chess.Board('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1')
        self.assertIsNone(Engine().choose(b,0.1).move)
    def test_special_moves(self):
        for fen,uci in [('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1'),
                        ('7k/8/8/3pP3/8/8/8/7K w - d6 0 1','e5d6'),
                        ('7k/P7/8/8/8/8/8/7K w - - 0 1','a7a8n')]:
            b=chess.Board(fen); m=chess.Move.from_uci(uci)
            self.assertIn(m,b.legal_moves)
            original=b.fen(); b.push(m); b.pop(); self.assertEqual(b.fen(),original)
    def test_timeout_preserves_position(self):
        b=chess.Board(); original=b.fen()
        self.assertIn(Engine().choose(b,0).move,b.legal_moves)
        self.assertEqual(b.fen(),original)

if __name__=='__main__': unittest.main()
