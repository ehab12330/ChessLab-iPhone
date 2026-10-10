"""Headless tests of real mouse handlers and asynchronous analysis."""
import queue
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import chess
from app import App
from engine import Result

class InterfaceTests(unittest.TestCase):
    def app(self):
        a=App.__new__(App)
        a.root=Mock(); a.board=chess.Board()
        a.selected=a.hint=None; a.flipped=True; a.busy=False; a.version=0
        a.pending=False; a.cancel=None; a.results=queue.Queue()
        a.cell=68; a.margin=24; a.origin_x=a.origin_y=24; a.info=Mock(); a.seconds=Mock()
        a.seconds.get.return_value='0.05'; a.draw=Mock(); a.reset_drag()
        return a
    def event(self,a,sq):
        x,y=a.xy(chess.parse_square(sq)); return SimpleNamespace(x=x,y=y)
    def test_drag_and_flipped_drag(self):
        for flipped in [False,True]:
            a=self.app(); a.flipped=flipped; a.analyze=Mock()
            source,target=('e2','e4') if flipped else ('e7','e5')
            if not flipped: a.board.push_san('e4')
            a.press(self.event(a,source)); a.drag(self.event(a,target)); a.release(self.event(a,target))
            self.assertEqual(a.board.peek().uci(),source+target)
            a.analyze.assert_called_once(); self.assertTrue(a.pending)
    def test_illegal_or_outside_drop(self):
        for destination in ['e5',None]:
            a=self.app()
            e=self.event(a,destination) if destination else SimpleNamespace(x=0,y=0)
            a.press(self.event(a,'e2')); a.drag(e); a.release(e)
            self.assertEqual(a.board.fen(),chess.STARTING_FEN)
            self.assertFalse(a.dragging)
    def test_click_still_works(self):
        a=self.app(); a.analyze=Mock()
        a.press(self.event(a,'g1')); a.release(self.event(a,'g1'))
        a.press(self.event(a,'f3')); a.release(self.event(a,'f3'))
        self.assertEqual(a.board.peek().uci(),'g1f3')
    def test_undo_and_new_auto_analyze(self):
        a=self.app(); a.analyze=Mock(); a.board.push_san('e4')
        a.undo(); a.new()
        self.assertEqual(a.analyze.call_count,2)
        self.assertIsNone(a.hint)
    def test_stale_analysis_is_replaced(self):
        a=self.app(); a.busy=True; a.cancel=threading.Event()
        a.hint=chess.Move.from_uci('e2e4'); a.board.push_san('d4'); a.changed()
        self.assertTrue(a.cancel.is_set()); self.assertIsNone(a.hint)
        a.results.put((0,Result(chess.Move.from_uci('e2e4'),0,1,1,0),None))
        a.analyze=Mock(); a.poll()
        self.assertIsNone(a.hint); a.analyze.assert_called_once()
    def test_real_worker_returns_auto_arrow(self):
        a=self.app(); a.analyze()
        limit=time.monotonic()+3
        while a.results.empty() and time.monotonic()<limit:
            time.sleep(0.01)
        self.assertFalse(a.results.empty())
        a.poll()
        self.assertIn(a.hint,a.board.legal_moves)
    def test_promotion_drag(self):
        a=self.app(); a.analyze=Mock()
        a.board=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        with patch('app.simpledialog.askstring',return_value='N'):
            a.press(self.event(a,'a7')); a.drag(self.event(a,'a8')); a.release(self.event(a,'a8'))
        self.assertEqual(a.board.piece_at(chess.A8).piece_type,chess.KNIGHT)

    def test_engine_only_moves_bottom_side(self):
        for flipped in [False,True]:
            a=self.app(); a.flipped=flipped
            if flipped: a.board.push_san('e4')
            before=len(a.board.move_stack); move=next(iter(a.board.legal_moves))
            a.results.put((0,Result(move,0,1,1,0),None))
            a.analyze=Mock(side_effect=lambda: setattr(a,'pending',False))
            a.poll()
            self.assertEqual(len(a.board.move_stack),before+1)
            self.assertNotEqual(a.board.turn,a.bottom_color)
            a.analyze.assert_called_once()
    def test_bottom_cannot_be_dragged(self):
        a=self.app(); a.flipped=False
        a.press(self.event(a,'e2')); a.drag(self.event(a,'e4')); a.release(self.event(a,'e4'))
        self.assertEqual(a.board.fen(),chess.STARTING_FEN)
    def test_flip_restarts_analysis(self):
        a=self.app(); a.analyze=Mock(); a.flip()
        self.assertFalse(a.flipped); self.assertEqual(a.bottom_color,chess.WHITE)
        a.analyze.assert_called_once()
    def test_resize_coordinate_mapping(self):
        a=self.app()
        for width,height in [(400,500),(900,650),(250,300)]:
            a.resize_board(SimpleNamespace(width=width,height=height))
            for flipped in [False,True]:
                a.flipped=flipped
                for sq in chess.SQUARES:
                    self.assertEqual(a.square_at(*a.xy(sq)),sq)
            self.assertIsNone(a.square_at(0,0))
    def test_undo_does_not_repeat_auto_reply(self):
        a=self.app(); a.flipped=False; a.analyze=Mock()
        for san in ['e4','e5','Nf3']: a.board.push_san(san)
        a.undo()
        self.assertEqual(len(a.board.move_stack),1)
        self.assertNotEqual(a.board.turn,a.bottom_color)

if __name__=='__main__': unittest.main()
