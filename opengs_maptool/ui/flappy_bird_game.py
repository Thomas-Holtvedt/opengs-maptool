"""Simple Flappy Bird game implementation using PyQt6."""

import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont


class FlappyBirdGame(QWidget):
    """A simple Flappy Bird game implemented with PyQt6."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flappy Bird")
        self.setGeometry(200, 200, 400, 600)
        self.setStyleSheet("background-color: #87CEEB;")
        
        # Game variables
        self.bird_y = 300
        self.bird_x = 50
        self.bird_size = 20
        self.velocity = 0
        self.gravity = 0.6
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.pipes = []
        self.pipe_gap = 160
        self.pipe_width = 80
        self.pipe_spacing = 250
        self.pipe_speed = 4
        
        # Game timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        self.timer.start(30)  # ~30ms per frame
        
        # Input handling
        self.key_pressed = set()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key.Key_Space:
            if not self.game_over:
                if not self.game_started:
                    self.game_started = True
                self.velocity = -8
        elif event.key() == Qt.Key.Key_R and self.game_over:
            self.reset_game()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse click events."""
        if self.game_over:
            self.reset_game()
    
    def reset_game(self) -> None:
        """Reset the game to initial state."""
        self.bird_y = 300
        self.bird_x = 50
        self.velocity = 0
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.pipes = []
        self.timer.start()
    
    def update_game(self):
        """Update game state."""
        if self.game_over or not self.game_started:
            return
        
        # Apply gravity
        self.velocity += self.gravity
        self.bird_y += self.velocity
        
        # Check boundary collisions
        if self.bird_y <= 0 or self.bird_y >= self.height():
            self.game_over = True
            self.timer.stop()
        
        # Generate pipes
        if len(self.pipes) == 0 or self.pipes[-1]['x'] < self.width() - self.pipe_spacing:
            gap_position = random.randint(80, self.height() - 80 - self.pipe_gap)
            self.pipes.append({
                'x': self.width(),
                'gap_y': gap_position,
                'scored': False
            })
        
        # Update pipes
        for pipe in self.pipes[:]:
            pipe['x'] -= self.pipe_speed
            
            # Check collision
            if (self.bird_x < pipe['x'] + self.pipe_width and
                self.bird_x + self.bird_size > pipe['x']):
                if (self.bird_y < pipe['gap_y'] or
                    self.bird_y + self.bird_size > pipe['gap_y'] + self.pipe_gap):
                    self.game_over = True
                    self.timer.stop()
            
            # Check if bird passed pipe
            if not pipe['scored'] and self.bird_x > pipe['x'] + self.pipe_width:
                self.score += 1
                pipe['scored'] = True
            
            # Remove off-screen pipes
            if pipe['x'] < -self.pipe_width:
                self.pipes.remove(pipe)
        
        self.update()
    
    def paintEvent(self, event):
        """Render the game."""
        painter = QPainter(self)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(135, 206, 235))
        
        # Draw bird
        painter.fillRect(int(self.bird_x), int(self.bird_y), self.bird_size, self.bird_size, QColor(255, 200, 0))
        
        # Draw pipes
        for pipe in self.pipes:
            # Top pipe
            painter.fillRect(int(pipe['x']), 0, self.pipe_width, int(pipe['gap_y']), QColor(34, 139, 34))
            # Bottom pipe
            painter.fillRect(int(pipe['x']), int(pipe['gap_y'] + self.pipe_gap), 
                           self.pipe_width, int(self.height() - pipe['gap_y'] - self.pipe_gap), 
                           QColor(34, 139, 34))
        
        # Draw score
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(10, 30, f"Score: {self.score}")
        
        # Draw game over message
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
            painter.drawText(10, self.height() - 10, "SPACE to flap")
