"""Simple Flappy Bird game implementation using PyQt6."""

import multiprocessing as mp
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont
import random
import sys


class Player:
    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size
        self.velocity = 0
        self.acceleration = 0
        self.color = QColor(255, 200, 0)

    def flap(self, strength):
        self.velocity = strength
        self.acceleration = 0

    def glide(self, strength):
        self.velocity = strength
        self.acceleration = 0

    def apply_gravity(self, gravity, terminal_velocity):
        self.acceleration += gravity
        self.velocity += self.acceleration
        if self.velocity > terminal_velocity:
            self.velocity = terminal_velocity

    def update_position(self):
        self.y += self.velocity

    def draw(self, painter):
        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(self.x), int(self.y), self.size, self.size)


class FlappyBirdGame(QWidget):
    """A simple Flappy Bird game implemented with PyQt6."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flappy Bird")
        self.setGeometry(200, 200, 400, 600)
        self.setStyleSheet("background-color: #87CEEB;")
        self.player = Player(x=50, y=300, size=24)
        self.gravity = 0.35
        self.jump_strength = -10
        self.glide_strength = -3
        self.terminal_velocity = 6
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.pipes = []
        self.pipe_gap = 160
        self.pipe_width = 80
        self.pipe_spacing = 250
        self.pipe_speed = 4
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        self.timer.start(30)  # ~30ms per frame
        self.key_pressed = set()
        self.best_score = 0
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key.Key_Space:
            if not self.game_over:
                if not self.game_started:
                    self.game_started = True
                self.player.flap(self.jump_strength)
        elif event.key() == Qt.Key.Key_R and self.game_over:
            self.reset_game()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Down:
            self.player.glide(self.glide_strength)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse click events."""
        if self.game_over:
            self.reset_game()
        elif not self.game_started:
            self.game_started = True
            self.player.flap(self.jump_strength)
    
    def reset_game(self) -> None:
        """Reset the game to initial state."""
        self.best_score = max(self.best_score, self.score)
        self.player = Player(x=50, y=300, size=24)
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.pipes = []
        self.timer.start()
    
    def update_game(self):
        """Update game state."""
        if self.game_over or not self.game_started:
            return
        self.player.apply_gravity(self.gravity, self.terminal_velocity)
        self.player.update_position()
        if self.player.y <= 0 or self.player.y + self.player.size >= self.height():
            self.game_over = True
            self.best_score = max(self.best_score, self.score)
            self.timer.stop()
        if len(self.pipes) == 0 or self.pipes[-1]['x'] < self.width() - self.pipe_spacing:
            gap_position = random.randint(80, self.height() - 80 - self.pipe_gap)
            self.pipes.append({
                'x': self.width(),
                'gap_y': gap_position,
                'scored': False
            })
        for pipe in self.pipes[:]:
            pipe['x'] -= self.pipe_speed
            if (self.player.x < pipe['x'] + self.pipe_width and
                self.player.x + self.player.size > pipe['x']):
                if (self.player.y < pipe['gap_y'] or
                    self.player.y + self.player.size > pipe['gap_y'] + self.pipe_gap):
                    self.game_over = True
                    self.best_score = max(self.best_score, self.score)
                    self.timer.stop()
            if not pipe['scored'] and self.player.x > pipe['x'] + self.pipe_width:
                self.score += 1
                pipe['scored'] = True
            if pipe['x'] < -self.pipe_width:
                self.pipes.remove(pipe)
        self.update()
    
    def paintEvent(self, event):
        """Render the game."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(135, 206, 235))
        self.player.draw(painter)
        for pipe in self.pipes:
            painter.fillRect(int(pipe['x']), 0, self.pipe_width, int(pipe['gap_y']), QColor(34, 139, 34))
            painter.fillRect(int(pipe['x']), int(pipe['gap_y'] + self.pipe_gap),
                            self.pipe_width, int(self.height() - pipe['gap_y'] - self.pipe_gap),
                            QColor(34, 139, 34))
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(10, 30, f"Score: {self.score}")
        painter.drawText(10, 55, f"Best: {self.best_score}")
        if self.game_over:
            font.setPointSize(30)
            painter.setFont(font)
            painter.setPen(QColor(255, 0, 0))
            text = f"Game Over! Score: {self.score}"
            text_width = painter.fontMetrics().horizontalAdvance(text)
            painter.drawText((self.width() - text_width) // 2, self.height() // 2, text)
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 0))
            hint = "Click or press R to restart | ESC to close"
            hint_width = painter.fontMetrics().horizontalAdvance(hint)
            painter.drawText((self.width() - hint_width) // 2, self.height() // 2 + 50, hint)
        elif not self.game_started:
            font.setPointSize(24)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            text = "Press SPACE to start"
            text_width = painter.fontMetrics().horizontalAdvance(text)
            painter.drawText((self.width() - text_width) // 2, self.height() // 2, text)
        else:
            font.setPointSize(12)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(10, self.height() - 10, "SPACE to flap | DOWN to glide")


def run_flappy_bird_game() -> None:
    """Run Flappy Bird in a dedicated Qt application process."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = FlappyBirdGame()
    window.show()
    app.exec()


def start_flappy_bird_process() -> mp.Process:
    """Start Flappy Bird in a separate process and return the process handle."""
    ctx = mp.get_context("spawn")
    process = ctx.Process(target=run_flappy_bird_game, daemon=True)
    process.start()
    return process
