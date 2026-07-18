"""
Animal-Aware Collision Prevention System - Interactive Pygame Simulation
Demonstrates real-time detection and prevention of animal-vehicle collisions
with dynamic animal movement and audio feedback
"""

import pygame
import sys
import math
import numpy as np

# ==================== CONFIGURATION CONSTANTS ====================
# Window settings
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 600
FPS = 60

# Distance thresholds (in simulation units - representing cm)
THRESHOLD_NORMAL = 50      # > 50 cm: Normal operation
THRESHOLD_WARNING = 30     # 30-50 cm: Horn warning
THRESHOLD_CAUTION = 20     # 20-30 cm: Speed reduction
THRESHOLD_EMERGENCY = 20   # <= 20 cm: Emergency stop

# Vehicle speeds (pixels per frame) - REDUCED FOR BETTER OBSERVATION
SPEED_NORMAL = 0.8         # Reduced from 3.0
SPEED_CAUTION = 0.3        # Reduced from 1.0
SPEED_STOP = 0.0

# Animal movement speed (pixels per frame)
ANIMAL_SPEED = 0.4         # Animal moves towards car

# Colors
COLOR_BACKGROUND = (34, 139, 34)      # Forest green
COLOR_ROAD = (50, 50, 50)             # Dark gray
COLOR_ROAD_LINE = (255, 255, 255)     # White
COLOR_CAR = (0, 100, 200)             # Blue
COLOR_ANIMAL = (139, 69, 19)          # Brown
COLOR_TEXT = (255, 255, 255)          # White
COLOR_ZONE_NORMAL = (0, 255, 0)       # Green
COLOR_ZONE_WARNING = (255, 255, 0)    # Yellow
COLOR_ZONE_CAUTION = (255, 165, 0)    # Orange
COLOR_ZONE_EMERGENCY = (255, 0, 0)    # Red
COLOR_HORN_ALERT = (255, 255, 100)    # Light yellow
COLOR_EMERGENCY_FLASH = (255, 0, 0)   # Red

# Animation settings
RESET_DELAY = 180  # Increased frames to wait before reset
EMERGENCY_BLINK_RATE = 15  # Frames per blink cycle


# ==================== SOUND GENERATOR ====================

class SoundGenerator:
    """Generates beep sounds programmatically without external files"""
    
    def __init__(self):
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.sample_rate = 22050
        
    def generate_beep(self, frequency, duration, volume=0.3):
        """Generate a beep sound wave"""
        num_samples = int(self.sample_rate * duration)
        
        # Generate sine wave
        wave = np.sin(2.0 * np.pi * frequency * np.linspace(0, duration, num_samples))
        
        # Apply envelope to avoid clicks (fade in/out)
        envelope = np.ones(num_samples)
        fade_samples = int(0.01 * self.sample_rate)  # 10ms fade
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        
        wave = wave * envelope * volume
        
        # Convert to 16-bit integers
        wave = np.array(wave * 32767, dtype=np.int16)
        
        # Create stereo by duplicating to 2 channels
        stereo_wave = np.column_stack((wave, wave))
        
        return pygame.sndarray.make_sound(stereo_wave)
    
    def generate_continuous_beep(self, frequency, duration, volume=0.4):
        """Generate a continuous urgent beep"""
        return self.generate_beep(frequency, duration, volume)
    
    def generate_pulsed_beep(self, frequency, duration, pulses=3, volume=0.3):
        """Generate a pulsed beep pattern"""
        num_samples = int(self.sample_rate * duration)
        pulse_length = num_samples // pulses
        
        wave = np.zeros(num_samples)
        
        for i in range(pulses):
            start = i * pulse_length
            end = start + pulse_length // 2  # 50% duty cycle
            
            pulse_samples = end - start
            pulse_wave = np.sin(2.0 * np.pi * frequency * 
                               np.linspace(0, pulse_samples / self.sample_rate, pulse_samples))
            wave[start:end] = pulse_wave
        
        wave = wave * volume
        wave = np.array(wave * 32767, dtype=np.int16)
        stereo_wave = np.column_stack((wave, wave))
        
        return pygame.sndarray.make_sound(stereo_wave)


# ==================== CLASS DEFINITIONS ====================

class Car:
    """Represents the vehicle with collision prevention capabilities"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 80
        self.height = 40
        self.speed = SPEED_NORMAL
        self.target_speed = SPEED_NORMAL
        self.mode = "Normal"
        
    def update(self):
        """Update car position with smooth speed transitions"""
        # Smooth acceleration/deceleration - slower transitions for better visibility
        if self.speed < self.target_speed:
            self.speed = min(self.speed + 0.02, self.target_speed)
        elif self.speed > self.target_speed:
            self.speed = max(self.speed - 0.03, self.target_speed)
        
        self.x += self.speed
    
    def draw(self, screen):
        """Draw the car on screen"""
        # Car body
        pygame.draw.rect(screen, COLOR_CAR, 
                        (self.x, self.y, self.width, self.height))
        # Car windows
        pygame.draw.rect(screen, (150, 200, 255), 
                        (self.x + 10, self.y + 5, 25, 15))
        pygame.draw.rect(screen, (150, 200, 255), 
                        (self.x + 45, self.y + 5, 25, 15))
        # Car wheels
        pygame.draw.circle(screen, (30, 30, 30), 
                          (int(self.x + 15), int(self.y + self.height)), 8)
        pygame.draw.circle(screen, (30, 30, 30), 
                          (int(self.x + self.width - 15), int(self.y + self.height)), 8)
    
    def get_front_x(self):
        """Get x-coordinate of car's front"""
        return self.x + self.width
    
    def reset(self):
        """Reset car to starting position"""
        self.x = 50
        self.speed = SPEED_NORMAL
        self.target_speed = SPEED_NORMAL
        self.mode = "Normal"


class Animal:
    """Represents the animal obstacle on the road - now moves towards car"""
    
    def __init__(self, x, y):
        self.initial_x = x
        self.x = x
        self.y = y
        self.width = 50
        self.height = 50
        self.bob_offset = 0  # For subtle animation
        self.bob_direction = 1
        self.speed = ANIMAL_SPEED  # Animal moves towards car
        self.moving = True
        
    def update(self, should_move=True):
        """Update animal position - moves towards car (left)"""
        # Add slight bobbing animation
        self.bob_offset += 0.3 * self.bob_direction
        if abs(self.bob_offset) > 3:
            self.bob_direction *= -1
        
        # Move towards car (leftward) if allowed
        if should_move and self.moving:
            self.x -= self.speed
    
    def stop(self):
        """Stop animal movement"""
        self.moving = False
    
    def draw(self, screen):
        """Draw the animal (simplified deer/cattle)"""
        y_pos = self.y + self.bob_offset
        
        # Body
        pygame.draw.ellipse(screen, COLOR_ANIMAL,
                           (self.x, y_pos, self.width, self.height - 10))
        # Head
        pygame.draw.circle(screen, COLOR_ANIMAL,
                          (int(self.x + self.width - 10), int(y_pos + 10)), 15)
        # Legs
        leg_positions = [
            (self.x + 10, y_pos + self.height - 10),
            (self.x + 20, y_pos + self.height - 10),
            (self.x + 30, y_pos + self.height - 10),
            (self.x + 40, y_pos + self.height - 10)
        ]
        for leg_x, leg_y in leg_positions:
            pygame.draw.line(screen, COLOR_ANIMAL,
                           (leg_x, leg_y), (leg_x, leg_y + 20), 4)
        
        # Add movement direction indicator
        if self.moving:
            # Draw arrow showing movement
            arrow_x = self.x - 20
            arrow_y = y_pos + self.height // 2
            pygame.draw.polygon(screen, (200, 100, 100), [
                (arrow_x, arrow_y),
                (arrow_x + 15, arrow_y - 8),
                (arrow_x + 15, arrow_y + 8)
            ])
    
    def get_position(self):
        """Get animal's x-coordinate"""
        return self.x
    
    def reset(self):
        """Reset animal to starting position"""
        self.x = self.initial_x
        self.moving = True


class Sensor:
    """Distance sensor that measures and reports car-to-animal distance"""
    
    def __init__(self):
        self.distance = 0
        self.mode = "Normal"
        self.previous_mode = "Normal"
        
    def measure_distance(self, car, animal):
        """Calculate distance between car front and animal"""
        car_front = car.get_front_x()
        animal_pos = animal.get_position()
        self.distance = animal_pos - car_front
        return self.distance
    
    def determine_mode(self, distance):
        """Determine operating mode based on distance thresholds"""
        self.previous_mode = self.mode
        
        if distance > THRESHOLD_NORMAL:
            self.mode = "Normal"
        elif distance > THRESHOLD_WARNING:
            self.mode = "Warning"
        elif distance > THRESHOLD_CAUTION:
            self.mode = "Caution"
        else:
            self.mode = "Emergency"
        return self.mode
    
    def mode_changed(self):
        """Check if mode has changed since last update"""
        return self.mode != self.previous_mode


class CollisionPreventionSystem:
    """Main system that integrates all components"""
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Animal Collision Prevention System")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 28)
        
        # Initialize sound generator
        self.sound_gen = SoundGenerator()
        self.warning_sound = self.sound_gen.generate_beep(800, 0.15, 0.25)  # Soft beep
        self.caution_sound = self.sound_gen.generate_pulsed_beep(1000, 0.3, 2, 0.3)  # Medium beeps
        self.emergency_sound = self.sound_gen.generate_continuous_beep(1200, 0.5, 0.35)  # Continuous urgent beep
        
        # Initialize components
        self.car = Car(50, WINDOW_HEIGHT // 2 - 20)
        self.animal = Animal(WINDOW_WIDTH - 250, WINDOW_HEIGHT // 2 - 25)
        self.sensor = Sensor()
        
        # State variables
        self.running = True
        self.emergency_stop_timer = 0
        self.blink_counter = 0
        self.show_horn_alert = False
        self.sound_played_for_mode = None  # Track which mode's sound was played
        
    def handle_events(self):
        """Process user input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset_simulation()
    
    def play_mode_sound(self, mode):
        """Play appropriate sound for the current mode (once per mode entry)"""
        # Only play if we've entered a new mode
        if self.sound_played_for_mode != mode:
            if mode == "Warning":
                self.warning_sound.play()
                self.sound_played_for_mode = "Warning"
            elif mode == "Caution":
                self.caution_sound.play()
                self.sound_played_for_mode = "Caution"
            elif mode == "Emergency":
                self.emergency_sound.play()
                self.sound_played_for_mode = "Emergency"
            elif mode == "Normal":
                self.sound_played_for_mode = "Normal"
    
    def update_system(self):
        """Update system state based on distance measurements"""
        # Measure distance
        distance = self.sensor.measure_distance(self.car, self.animal)
        mode = self.sensor.determine_mode(distance)
        self.car.mode = mode
        
        # Play sound when mode changes
        self.play_mode_sound(mode)
        
        # Control car and animal based on mode
        if mode == "Normal":
            self.car.target_speed = SPEED_NORMAL
            self.show_horn_alert = False
            
        elif mode == "Warning":
            self.car.target_speed = SPEED_NORMAL
            self.show_horn_alert = True  # Horn activated
            
        elif mode == "Caution":
            self.car.target_speed = SPEED_CAUTION
            self.show_horn_alert = True
            
        elif mode == "Emergency":
            self.car.target_speed = SPEED_STOP
            self.show_horn_alert = True
            self.animal.stop()  # Animal stops moving in emergency
            
            # Start emergency stop timer
            if self.car.speed <= 0.1:
                self.emergency_stop_timer += 1
        
        # Reset after emergency stop delay
        if self.emergency_stop_timer > RESET_DELAY:
            self.reset_simulation()
        
        # Update components
        should_update = self.emergency_stop_timer == 0
        if should_update:
            self.car.update()
        
        # Animal continues moving unless in emergency stop
        self.animal.update(should_move=should_update)
        self.blink_counter += 1
    
    def draw_road(self):
        """Draw the road with lane markings"""
        road_y = WINDOW_HEIGHT // 2 - 60
        road_height = 160
        
        # Road surface
        pygame.draw.rect(self.screen, COLOR_ROAD,
                        (0, road_y, WINDOW_WIDTH, road_height))
        
        # Center line dashes
        dash_width = 40
        dash_gap = 30
        for x in range(0, WINDOW_WIDTH, dash_width + dash_gap):
            pygame.draw.rect(self.screen, COLOR_ROAD_LINE,
                           (x, WINDOW_HEIGHT // 2 - 2, dash_width, 4))
        
        # Road edges
        pygame.draw.line(self.screen, COLOR_ROAD_LINE,
                        (0, road_y), (WINDOW_WIDTH, road_y), 3)
        pygame.draw.line(self.screen, COLOR_ROAD_LINE,
                        (0, road_y + road_height), (WINDOW_WIDTH, road_y + road_height), 3)
    
    def draw_distance_zones(self):
        """Draw colored zones representing distance thresholds"""
        animal_x = self.animal.get_position()
        zone_height = 30
        zone_y = WINDOW_HEIGHT - 150
        
        # Calculate zone positions (from animal backward)
        # Emergency zone (0-20 cm)
        emergency_width = THRESHOLD_EMERGENCY * 2
        pygame.draw.rect(self.screen, COLOR_ZONE_EMERGENCY,
                        (animal_x - emergency_width, zone_y, emergency_width, zone_height))
        
        # Caution zone (20-30 cm)
        caution_width = (THRESHOLD_WARNING - THRESHOLD_CAUTION) * 2
        pygame.draw.rect(self.screen, COLOR_ZONE_CAUTION,
                        (animal_x - emergency_width - caution_width, zone_y, 
                         caution_width, zone_height))
        
        # Warning zone (30-50 cm)
        warning_width = (THRESHOLD_NORMAL - THRESHOLD_WARNING) * 2
        pygame.draw.rect(self.screen, COLOR_ZONE_WARNING,
                        (animal_x - emergency_width - caution_width - warning_width, zone_y,
                         warning_width, zone_height))
        
        # Normal zone (>50 cm)
        normal_start = animal_x - emergency_width - caution_width - warning_width
        if normal_start > 0:
            pygame.draw.rect(self.screen, COLOR_ZONE_NORMAL,
                            (0, zone_y, normal_start, zone_height))
        
        # Zone labels
        label_y = zone_y + 35
        self.draw_text("Normal >50cm", 100, label_y, self.font_small, COLOR_ZONE_NORMAL)
        self.draw_text("Warning 30-50cm", 300, label_y, self.font_small, COLOR_ZONE_WARNING)
        self.draw_text("Caution 20-30cm", 550, label_y, self.font_small, COLOR_ZONE_CAUTION)
        self.draw_text("Emergency ≤20cm", 800, label_y, self.font_small, COLOR_ZONE_EMERGENCY)
    
    def draw_distance_indicator(self):
        """Draw a line showing current distance with measurement"""
        car_front = self.car.get_front_x()
        animal_pos = self.animal.get_position()
        y_line = WINDOW_HEIGHT // 2 - 80
        
        # Distance line with color based on mode
        line_colors = {
            "Normal": COLOR_ZONE_NORMAL,
            "Warning": COLOR_ZONE_WARNING,
            "Caution": COLOR_ZONE_CAUTION,
            "Emergency": COLOR_ZONE_EMERGENCY
        }
        line_color = line_colors.get(self.car.mode, (255, 255, 255))
        
        pygame.draw.line(self.screen, line_color,
                        (car_front, y_line), (animal_pos, y_line), 3)
        
        # Endpoint markers
        pygame.draw.circle(self.screen, line_color,
                          (int(car_front), y_line), 6)
        pygame.draw.circle(self.screen, line_color,
                          (int(animal_pos), y_line), 6)
        
        # Distance text
        mid_x = (car_front + animal_pos) / 2
        distance_text = f"{self.sensor.distance:.1f} cm"
        self.draw_text(distance_text, mid_x, y_line - 25, 
                      self.font_medium, line_color)
    
    def draw_status_panel(self):
        """Draw system status information panel"""
        panel_x = 20
        panel_y = 20
        line_height = 40
        
        # Mode indicator with color coding
        mode_colors = {
            "Normal": COLOR_ZONE_NORMAL,
            "Warning": COLOR_ZONE_WARNING,
            "Caution": COLOR_ZONE_CAUTION,
            "Emergency": COLOR_ZONE_EMERGENCY
        }
        mode_color = mode_colors.get(self.car.mode, COLOR_TEXT)
        
        self.draw_text(f"MODE: {self.car.mode}", panel_x, panel_y, 
                      self.font_large, mode_color)
        
        # Speed indicator
        speed_kmh = self.car.speed * 30  # Adjusted conversion for display
        self.draw_text(f"Speed: {speed_kmh:.1f} km/h", panel_x, panel_y + line_height,
                      self.font_medium, COLOR_TEXT)
        
        # Distance
        self.draw_text(f"Distance: {self.sensor.distance:.1f} cm", 
                      panel_x, panel_y + line_height * 2,
                      self.font_medium, COLOR_TEXT)
        
        # System actions
        actions = []
        if self.show_horn_alert:
            actions.append("🔊 HORN ACTIVE")
        if self.car.mode == "Caution":
            actions.append("⚠️ REDUCING SPEED")
        if self.car.mode == "Emergency":
            actions.append("🚨 EMERGENCY BRAKING")
        if self.animal.moving:
            actions.append("🦌 Animal Approaching")
        
        for i, action in enumerate(actions):
            self.draw_text(action, panel_x, panel_y + line_height * (3 + i),
                          self.font_small, COLOR_HORN_ALERT)
    
    def draw_emergency_effects(self):
        """Draw emergency visual effects (blinking hazard lights)"""
        if self.car.mode == "Emergency" and self.car.speed <= 0.1:
            # Blinking effect
            if (self.blink_counter // EMERGENCY_BLINK_RATE) % 2 == 0:
                # Draw flashing border
                pygame.draw.rect(self.screen, COLOR_EMERGENCY_FLASH,
                               (0, 0, WINDOW_WIDTH, WINDOW_HEIGHT), 10)
                
                # Emergency text
                emergency_text = "🚨 EMERGENCY STOP 🚨"
                text_surface = self.font_large.render(emergency_text, True, 
                                                      COLOR_EMERGENCY_FLASH)
                text_rect = text_surface.get_rect(center=(WINDOW_WIDTH // 2, 100))
                
                # Text background
                padding = 20
                bg_rect = text_rect.inflate(padding * 2, padding)
                pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(self.screen, COLOR_EMERGENCY_FLASH, bg_rect, 3)
                
                self.screen.blit(text_surface, text_rect)
    
    def draw_text(self, text, x, y, font, color):
        """Helper function to draw text"""
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(topleft=(x, y))
        self.screen.blit(text_surface, text_rect)
    
    def draw_instructions(self):
        """Draw usage instructions"""
        instructions = "Press R to Reset | ESC to Exit | Watch: Animal approaches dynamically"
        self.draw_text(instructions, WINDOW_WIDTH - 700, WINDOW_HEIGHT - 30,
                      self.font_small, (200, 200, 200))
    
    def reset_simulation(self):
        """Reset the simulation to initial state"""
        self.car.reset()
        self.animal.reset()
        self.emergency_stop_timer = 0
        self.blink_counter = 0
        self.show_horn_alert = False
        self.sound_played_for_mode = None
        pygame.mixer.stop()  # Stop all sounds
    
    def render(self):
        """Render all visual elements"""
        # Background
        self.screen.fill(COLOR_BACKGROUND)
        
        # Draw components in layers
        self.draw_road()
        self.draw_distance_zones()
        self.car.draw(self.screen)
        self.animal.draw(self.screen)
        self.draw_distance_indicator()
        self.draw_status_panel()
        self.draw_emergency_effects()
        self.draw_instructions()
        
        pygame.display.flip()
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            self.update_system()
            self.render()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()


# ==================== MAIN ENTRY POINT ====================

if __name__ == "__main__":
    print("=" * 70)
    print("Animal-Aware Collision Prevention System Simulation")
    print("Enhanced Version with Dynamic Animal Movement & Audio Feedback")
    print("=" * 70)
    print("\nThis simulation demonstrates the working principle of")
    print("an automated animal collision prevention system.")
    print("\nSystem Stages:")
    print("  • Normal (>50cm): Full speed operation")
    print("  • Warning (30-50cm): Horn alert activated (soft beep)")
    print("  • Caution (20-30cm): Speed reduction (medium beeps)")
    print("  • Emergency (≤20cm): Complete stop (continuous urgent beep)")
    print("\nNew Features:")
    print("  ✓ Slower vehicle speed for better zone observation")
    print("  ✓ Animal moves dynamically towards the vehicle")
    print("  ✓ Audio feedback for each safety stage")
    print("  ✓ Smooth transitions between all modes")
    print("\nControls:")
    print("  • R: Reset simulation")
    print("  • ESC: Exit")
    print("=" * 70)
    print("\nStarting simulation...\n")
    
    # Create and run the simulation
    system = CollisionPreventionSystem()
    system.run()