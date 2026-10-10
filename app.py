import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import chess
import chess.pgn
from engine import Engine, MATE

GLYPHS = {'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙',
          'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}

class App:
    def __init__(self, root):
        self.root = root
        root.title('Chess Lab • Local Chess AI')
        root.configure(bg='#101b2c')
        root.resizable(True, True)
        root.geometry('980x740')
        root.minsize(650, 560)
        self.board = chess.Board()
        self.selected = self.hint = None
        self.flipped = self.busy = False
        self.version = 0
        self.pending = False
        self.cancel = None
        self.drag_from = self.press_point = self.drag_xy = None
        self.dragging = False
        self.results = queue.Queue()
        self.cell, self.margin = 68, 24
        self.origin_x = self.origin_y = self.margin
        head = tk.Frame(root, bg='#101b2c')
        head.pack(fill='x', padx=24, pady=16)
        tk.Label(head, text='CHESS LAB', fg='#f1f5f9', bg='#101b2c', font=('Arial', 23, 'bold')).pack(anchor='w')
        tk.Label(head, text='Local board • Original engine • Training & analysis', fg='#91a6be', bg='#101b2c').pack(anchor='w')
        body = tk.Frame(root, bg='#101b2c')
        body.pack(padx=12, pady=4, fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        size = self.cell*8 + self.margin*2
        self.canvas = tk.Canvas(body, width=size, height=size, bg='#101b2c', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', self.resize_board)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        side = tk.Frame(body, bg='#101b2c', width=250)
        side.grid(row=0, column=1, sticky='ns', padx=(12,0))
        self.status = tk.StringVar()
        tk.Label(side, textvariable=self.status, fg='white', bg='#101b2c', font=('Arial',14,'bold'), wraplength=240).pack(pady=10)
        for label, callback in [('New game',self.new),('Undo',self.undo),('Flip board',self.flip),('Export PGN',self.export)]:
            ttk.Button(side, text=label, command=callback, width=28).pack(pady=2)
        tk.Label(side, text='Thinking time (seconds)', fg='#91a6be', bg='#101b2c').pack(pady=(12,4))
        self.seconds = tk.StringVar(value='3')
        thinking = ttk.Combobox(side, textvariable=self.seconds, values=['1','3','5','10'], state='readonly', width=25)
        thinking.pack()
        thinking.bind('<<ComboboxSelected>>', lambda event: self.request_analysis())
        self.info = tk.StringVar(value='Bottom side: automatic engine.\nMove the top side yourself.')
        tk.Label(side, textvariable=self.info, fg='#7de3bc', bg='#101b2c', wraplength=235, justify='left').pack(pady=16)
        self.history = tk.Text(side, height=3, width=28, bg='#19283c', fg='white', relief='flat', state='disabled')
        self.history.pack(fill='both', expand=True)
        tk.Label(root, text='Research prototype • Playing strength has not been rated', fg='#91a6be', bg='#101b2c').pack(pady=12)
        self.draw()
        root.after(60, self.poll)
        root.after(100, self.analyze)

    def xy(self, sq):
        f,r = chess.square_file(sq),chess.square_rank(sq)
        col,row = (7-f,r) if self.flipped else (f,7-r)
        return self.origin_x+(col+.5)*self.cell,self.origin_y+(row+.5)*self.cell

    @property
    def bottom_color(self):
        return chess.BLACK if self.flipped else chess.WHITE

    def resize_board(self, event):
        self.cell = max(1, (min(event.width, event.height)-2*self.margin)/8)
        self.origin_x = (event.width-8*self.cell)/2
        self.origin_y = (event.height-8*self.cell)/2
        self.reset_drag()
        self.draw()

    def draw_piece(self, x, y, piece):
        # Filled glyphs with a contrasting outline stay legible on every square.
        glyph = GLYPHS[piece.symbol().lower()]
        font = ('DejaVu Sans', max(8, int(self.cell*.63)))
        outline = '#172438' if piece.color else '#eaf2ff'
        fill = '#ffffff' if piece.color else '#152238'
        offset = max(1, self.cell/40)
        for dx, dy in [(-offset,0),(offset,0),(0,-offset),(0,offset)]:
            self.canvas.create_text(x+dx,y+dy,text=glyph,font=font,fill=outline)
        self.canvas.create_text(x,y,text=glyph,font=font,fill=fill)

    def draw(self):
        c=self.canvas
        c.delete('all')
        targets = {m.to_square for m in self.board.legal_moves if m.from_square == self.selected}
        last = self.board.peek() if self.board.move_stack else None
        for sq in chess.SQUARES:
            x,y=self.xy(sq)
            color = '#adbed0' if (chess.square_file(sq)+chess.square_rank(sq))%2 else '#4f6b8c'
            if last and sq in (last.from_square,last.to_square): color='#7196a6'
            if sq==self.selected: color='#91bce4'
            half=self.cell/2
            c.create_rectangle(x-half,y-half,x+half,y+half,fill=color,outline='')
            p=self.board.piece_at(sq)
            if p and not (self.dragging and sq == self.drag_from):
                self.draw_piece(x,y,p)
            if sq in targets:
                if p: c.create_oval(x-self.cell*.43,y-self.cell*.43,x+self.cell*.43,y+self.cell*.43,outline='#245787',width=4)
                else: c.create_oval(x-self.cell*.1,y-self.cell*.1,x+self.cell*.1,y+self.cell*.1,fill='#245787',outline='')
        for i in range(8):
            f=7-i if self.flipped else i
            r=i if self.flipped else 7-i
            c.create_text(self.origin_x+(i+.5)*self.cell,self.origin_y+8*self.cell+12,text=chess.FILE_NAMES[f],fill='#91a6be')
            c.create_text(self.origin_x-12,self.origin_y+(i+.5)*self.cell,text=str(r+1),fill='#91a6be')
        if self.hint:
            x,y=self.xy(self.hint.from_square); xx,yy=self.xy(self.hint.to_square)
            c.create_line(x,y,xx,yy,fill='#ed793d',width=max(2,self.cell*.12),arrow=tk.LAST,arrowshape=(self.cell*.32,self.cell*.38,self.cell*.16))
        if self.dragging and self.drag_xy is not None:
            piece = self.board.piece_at(self.drag_from)
            if piece:
                self.draw_piece(*self.drag_xy, piece)
        outcome=self.board.outcome()
        self.status.set('Game over: '+outcome.result() if outcome else ('White to move' if self.board.turn else 'Black to move')+(' • Check' if self.board.is_check() else '')+'\n'+('Engine (bottom)' if self.board.turn == self.bottom_color else 'Your turn (top)'))
        replay=self.board.root(); lines=[]
        for m in self.board.move_stack:
            san=replay.san(m)
            if replay.turn: lines.append(f'{replay.fullmove_number}. {san}')
            elif lines: lines[-1]+='   '+san
            else: lines.append(f'{replay.fullmove_number}... {san}')
            replay.push(m)
        self.history.configure(state='normal'); self.history.delete('1.0','end')
        self.history.insert('end','\n'.join(lines)); self.history.see('end'); self.history.configure(state='disabled')

    def request_analysis(self):
        self.version += 1
        self.hint = None
        self.pending = True
        if self.cancel is not None:
            self.cancel.set()
        self.info.set('Thinking… Suggestions update automatically.')
        self.draw()
        self.analyze()

    def changed(self):
        self.selected = None
        self.reset_drag()
        self.request_analysis()

    def square_at(self, x, y):
        col = int((x-self.origin_x)//self.cell)
        row = int((y-self.origin_y)//self.cell)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        return chess.square(7-col if self.flipped else col,
                            row if self.flipped else 7-row)

    def reset_drag(self):
        self.drag_from = self.press_point = self.drag_xy = None
        self.dragging = False

    def try_move(self, source, target):
        if source is None or target is None or self.board.turn == self.bottom_color:
            return False
        candidates = [m for m in self.board.legal_moves
                      if m.from_square == source and m.to_square == target]
        if not candidates:
            return False
        move = candidates[0]
        if move.promotion:
            choice = simpledialog.askstring('Promotion', 'Choose Q, R, B, or N:',
                                            initialvalue='Q', parent=self.root)
            if choice is None:
                return False
            kind = {'q':chess.QUEEN, 'r':chess.ROOK, 'b':chess.BISHOP,
                    'n':chess.KNIGHT}.get(choice.lower().strip())
            if kind is None:
                return False
            move = next(m for m in candidates if m.promotion == kind)
        self.board.push(move)
        self.changed()
        return True

    def press(self, event):
        self.reset_drag()
        if self.board.is_game_over() or self.board.turn == self.bottom_color:
            return
        sq = self.square_at(event.x, event.y)
        if sq is None:
            return
        if self.selected is not None and self.selected != sq:
            if self.try_move(self.selected, sq):
                return
        piece = self.board.piece_at(sq)
        self.selected = sq if piece and piece.color == self.board.turn else None
        if self.selected is not None:
            self.drag_from = sq
            self.press_point = (event.x, event.y)
        self.draw()

    def drag(self, event):
        if self.drag_from is None:
            return
        x, y = self.press_point
        if self.dragging or (event.x-x)**2 + (event.y-y)**2 >= 36:
            self.dragging = True
            self.drag_xy = (event.x, event.y)
            self.draw()

    def release(self, event):
        source, dragging = self.drag_from, self.dragging
        target = self.square_at(event.x, event.y)
        self.reset_drag()
        if dragging:
            self.selected = None
            if self.try_move(source, target):
                return
        self.draw()

    def new(self):
        self.board=chess.Board(); self.changed()
    def undo(self):
        if self.board.move_stack:
            self.board.pop()
            if self.board.move_stack and self.board.turn == self.bottom_color:
                self.board.pop()
            self.changed()
    def flip(self):
        self.flipped=not self.flipped; self.changed()
    def play_hint(self):
        if self.board.turn == self.bottom_color and self.hint and self.hint in self.board.legal_moves:
            self.board.push(self.hint); self.changed()
    def analyze(self):
        if self.board.is_game_over():
            self.pending = False
            self.info.set('Game over. No suggestion available.')
            return
        if self.busy:
            self.pending = True
            return
        self.pending = False
        self.busy=True; self.info.set('Thinking… Suggestions update automatically.')
        cancel = self.cancel = threading.Event()
        position=self.board.copy(stack=True); version=self.version; seconds=float(self.seconds.get())
        def worker():
            try: self.results.put((version,Engine().choose(position,seconds,cancel=cancel),None))
            except Exception as e: self.results.put((version,None,str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            version,result,error=self.results.get_nowait(); self.busy=False
            if version==self.version:
                if error: self.info.set('Analysis failed: '+error)
                elif result.move:
                    self.hint=result.move
                    score=('Mate found' if abs(result.score)>MATE-1000 else f'{result.score/100:+.2f} pawns (side to move)')
                    self.info.set(f'Suggestion: {self.board.san(result.move)}\n{score}\nDepth {result.depth} • {result.nodes:,} nodes\n{result.seconds:.2f} seconds')
                    if self.board.turn == self.bottom_color:
                        self.play_hint()
                    else:
                        self.draw()
                else: self.info.set('No move available.')
        except queue.Empty: pass
        if not self.busy and self.pending:
            self.analyze()
        self.root.after(60,self.poll)
    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.pgn',filetypes=[('Chess PGN','*.pgn')])
        if path:
            game=chess.pgn.Game.from_board(self.board)
            game.headers['Event']='Chess Lab local experiment'
            try:
                with open(path,'w',encoding='utf-8') as f: f.write(str(game)+'\n')
            except OSError as e: messagebox.showerror('Export failed',str(e))

if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()
