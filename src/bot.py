from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.messages.flat.QuickChatSelection import QuickChatSelection
from rlbot.utils.structures.game_data_struct import GameTickPacket

from util.ball_prediction_analysis import find_slice_at_time
from util.boost_pad_tracker import BoostPadTracker
from util.drive import steer_toward_target
from util.sequence import Sequence, ControlStep
from util.vec import Vec3
import math
import random


class AdvancedFreestyleBot(BaseAgent):
    """
    Advanced Rocket League freestyle bot with multiple aerial tricks
    Features:
    - Multiple freestyle aerial variations
    - Smart aerial decision making
    - Boost management
    - Ground dribbling attempts
    - Recovery mechanics
    """

    def __init__(self, name, team, index):
        super().__init__(name, team, index)
        self.active_sequence: Sequence = None
        self.boost_pad_tracker = BoostPadTracker()
        
        # Freestyle state tracking
        self.last_aerial_time = 0
        self.aerial_cooldown = 3.0  # Seconds between aerials
        self.tricks_performed = 0
        
        # Trick variation counter
        self.last_trick_type = None

    def initialize_agent(self):
        self.boost_pad_tracker.initialize_boosts(self.get_field_info())

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:
        """Main bot logic with freestyle decision making"""
        
        # Update boost pads
        self.boost_pad_tracker.update_boost_status(packet)

        # Continue active sequences
        if self.active_sequence is not None and not self.active_sequence.done:
            controls = self.active_sequence.tick(packet)
            if controls is not None:
                return controls

        # Gather game state
        my_car = packet.game_cars[self.index]
        car_location = Vec3(my_car.physics.location)
        car_velocity = Vec3(my_car.physics.velocity)
        ball_location = Vec3(packet.game_ball.physics.location)
        ball_velocity = Vec3(packet.game_ball.physics.velocity)
        
        current_time = packet.game_info.seconds_elapsed
        time_since_aerial = current_time - self.last_aerial_time

        # Calculate useful values
        car_to_ball = ball_location - car_location
        distance_to_ball = car_to_ball.length()
        ball_height = ball_location.z
        car_speed = car_velocity.length()

        # Visualization
        self.draw_debug_info(my_car, ball_location, car_speed, distance_to_ball)

        # === AERIAL DECISION LOGIC ===
        aerial_conditions = self.check_aerial_conditions(
            my_car, ball_location, ball_height, distance_to_ball, time_since_aerial
        )

        if aerial_conditions:
            # Predict ball trajectory
            ball_prediction = self.get_ball_prediction_struct()
            target = self.find_aerial_target(
                ball_prediction, packet.game_info.seconds_elapsed, distance_to_ball
            )
            
            if target is not None:
                self.last_aerial_time = current_time
                return self.choose_freestyle_aerial(packet, target, my_car.boost)

        # === GROUND GAME ===
        return self.ground_game_logic(
            packet, my_car, car_location, ball_location, 
            distance_to_ball, car_speed
        )

    def check_aerial_conditions(self, my_car, ball_location, ball_height, 
                                distance_to_ball, time_since_aerial):
        """Check if we should attempt an aerial"""
        return (
            ball_height > 350 and  # Ball is high enough
            400 < distance_to_ball < 2200 and  # We're in range
            my_car.boost > 35 and  # We have boost
            time_since_aerial > self.aerial_cooldown and  # Not spamming aerials
            not my_car.is_super_sonic and  # Not already supersonic
            my_car.has_wheel_contact  # On the ground (ready to jump)
        )

    def find_aerial_target(self, ball_prediction, current_time, distance):
        """Find where to intercept the ball in the air"""
        # Predict further ahead based on distance
        lookahead = 0.5 + (distance / 1500.0)
        lookahead = min(lookahead, 2.5)  # Cap at 2.5 seconds
        
        target_slice = find_slice_at_time(ball_prediction, current_time + lookahead)
        
        if target_slice is not None:
            target_location = Vec3(target_slice.physics.location)
            # Only go for it if it's actually aerial-worthy
            if target_location.z > 400:
                return target_location
        
        return None

    def choose_freestyle_aerial(self, packet, target_location, boost_amount):
        """Choose which freestyle aerial to perform"""
        
        my_car = packet.game_cars[self.index]
        car_location = Vec3(my_car.physics.location)
        ball_location = Vec3(packet.game_ball.physics.location)
        
        # Different tricks based on boost available and randomness
        tricks = []
        
        # High boost tricks (60+)
        if boost_amount > 60:
            tricks.extend(['tornado', 'ceiling_shuffle', 'kuxir_twist', 'flip_reset', 'psycho'])
        
        # Medium boost tricks (40+)
        if boost_amount > 40:
            tricks.extend(['air_roll_shot', 'musty_flick', 'flip_reset'])
        
        # Low boost tricks
        tricks.extend(['basic_aerial', 'spinning_aerial'])
        
        # Don't repeat the same trick twice in a row
        if self.last_trick_type in tricks:
            tricks.remove(self.last_trick_type)
        
        chosen_trick = random.choice(tricks)
        self.last_trick_type = chosen_trick
        self.tricks_performed += 1

        # Execute the chosen trick
        if chosen_trick == 'tornado':
            return self.tornado_aerial(packet, target_location)
        elif chosen_trick == 'kuxir_twist':
            return self.kuxir_twist(packet, target_location)
        elif chosen_trick == 'air_roll_shot':
            return self.air_roll_shot(packet, target_location)
        elif chosen_trick == 'ceiling_shuffle':
            return self.ceiling_shuffle(packet, target_location)
        elif chosen_trick == 'spinning_aerial':
            return self.spinning_aerial(packet, target_location)
        elif chosen_trick == 'psycho':
            return self.psycho(packet, target_location)
        elif chosen_trick == 'musty_flick':
            return self.musty_flick(packet, target_location)
        elif chosen_trick == 'flip_reset':
            return self.flip_reset(packet, target_location)
        else:
            return self.basic_freestyle_aerial(packet, target_location)

    def tornado_aerial(self, packet, target):
        """Tornado spin - continuous rotation while aerial"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Calculated)
        
        self.active_sequence = Sequence([
            # Jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Double jump with initial tilt
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.4)),
            # Tornado spin sequence
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.3, roll=1.0, yaw=1.0)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.2, roll=1.0, yaw=-1.0)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.3, roll=1.0, yaw=1.0)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.2, roll=1.0, yaw=-1.0)),
            # Hit the ball
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.9, roll=0.5)),
            # Recovery
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0, roll=0)),
        ])
        
        return self.active_sequence.tick(packet)

    def kuxir_twist(self, packet, target):
        """Kuxir twist - backward aerial with twist"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Siiiick)
        
        self.active_sequence = Sequence([
            # Jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Flip backward and twist
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=1.0)),
            # Spinning while upside down
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.5, roll=-1.0, yaw=0.8)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.3, roll=-1.0, yaw=-0.8)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.5, roll=-1.0, yaw=0.8)),
            # Adjust for hit
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.5, roll=0.5)),
            # Recovery
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0, roll=0)),
        ])
        
        return self.active_sequence.tick(packet)

    def air_roll_shot(self, packet, target):
        """Air roll shot - spinning while approaching ball"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Wow)
        
        self.active_sequence = Sequence([
            # Jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Double jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.5)),
            # Air roll sequence
            ControlStep(duration=0.25, controls=SimpleControllerState(boost=True, pitch=-0.4, roll=1.0)),
            ControlStep(duration=0.25, controls=SimpleControllerState(boost=True, pitch=-0.4, roll=1.0)),
            ControlStep(duration=0.25, controls=SimpleControllerState(boost=True, pitch=-0.5, roll=1.0)),
            # Final adjustment
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-1.0, roll=0)),
            # Recovery
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0)),
        ])
        
        return self.active_sequence.tick(packet)

    def ceiling_shuffle(self, packet, target):
        """Ceiling shuffle style aerial"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_NoProblem)
        
        self.active_sequence = Sequence([
            # Jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Lean back and roll
            ControlStep(duration=0.15, controls=SimpleControllerState(jump=True, boost=True, pitch=0.5, roll=-1.0)),
            # Shuffle sequence - alternating rolls
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.2, roll=1.0, yaw=0.5)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.2, roll=-1.0, yaw=-0.5)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.3, roll=1.0, yaw=0.5)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.3, roll=-1.0, yaw=-0.5)),
            # Hit
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.8)),
            # Recovery
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0)),
        ])
        
        return self.active_sequence.tick(packet)

    def spinning_aerial(self, packet, target):
        """Basic spinning aerial"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_OMG)
        
        self.active_sequence = Sequence([
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.4)),
            # Continuous spin
            ControlStep(duration=0.3, controls=SimpleControllerState(boost=True, pitch=-0.3, roll=-1.0)),
            ControlStep(duration=0.3, controls=SimpleControllerState(boost=True, pitch=-0.4, roll=-1.0)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.8)),
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0)),
        ])
        
        return self.active_sequence.tick(packet)

    def basic_freestyle_aerial(self, packet, target):
        """Standard freestyle aerial"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Information_IGotIt)
        
        self.active_sequence = Sequence([
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.5)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.4, roll=-1.0, yaw=0.3)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.5, roll=1.0, yaw=-0.3)),
            ControlStep(duration=0.25, controls=SimpleControllerState(boost=True, pitch=-0.7)),
            ControlStep(duration=0.4, controls=SimpleControllerState(pitch=1.0)),
        ])
        
        return self.active_sequence.tick(packet)

    def psycho(self, packet, target):
        """Psycho - Backwards aerial with continuous air roll"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Siiiick)
        
        self.active_sequence = Sequence([
            # Jump backwards
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=0.3)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Second jump while tilting back
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=0.8)),
            # Psycho sequence - backwards with air roll
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.6, roll=1.0, yaw=0.5)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.4, roll=1.0, yaw=-0.5)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.5, roll=1.0, yaw=0.5)),
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=0.3, roll=1.0, yaw=-0.5)),
            # Adjust to hit ball while still spinning
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.5, roll=1.0)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=-0.8, roll=0.5)),
            # Recovery
            ControlStep(duration=0.5, controls=SimpleControllerState(pitch=1.0, roll=0)),
        ])
        
        return self.active_sequence.tick(packet)

    def musty_flick(self, packet, target):
        """Musty Flick - Backflip while under the ball for powerful shot"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Wow)
        
        self.active_sequence = Sequence([
            # Jump up to ball
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Second jump with slight forward tilt
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.3)),
            # Get under the ball - tilt back
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=0.6)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=0.8)),
            # Position perfectly under ball
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=1.0)),
            # THE MUSTY - backflip while ball is on top of car
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, pitch=1.0, boost=False)),
            ControlStep(duration=0.2, controls=SimpleControllerState(pitch=1.0, boost=False)),
            # Recovery
            ControlStep(duration=0.5, controls=SimpleControllerState(pitch=-1.0, roll=0)),
            ControlStep(duration=0.3, controls=SimpleControllerState(pitch=1.0, roll=0)),
        ])
        
        return self.active_sequence.tick(packet)

    def flip_reset(self, packet, target):
        """Flip Reset - Get all 4 wheels on ball to reset flip"""
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Calculated)
        
        self.active_sequence = Sequence([
            # Jump toward ball
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Second jump
            ControlStep(duration=0.1, controls=SimpleControllerState(jump=True, boost=True, pitch=-0.4)),
            # Aerial toward ball
            ControlStep(duration=0.2, controls=SimpleControllerState(boost=True, pitch=-0.3)),
            # Adjust angle to get underside of car on ball
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=0.6, roll=0.3)),
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=0.8, roll=-0.3)),
            # Try to get all 4 wheels touching ball (this resets our flip)
            ControlStep(duration=0.15, controls=SimpleControllerState(boost=True, pitch=0.9, roll=0)),
            # FLIP RESET ACHIEVED - now we can flip again!
            # Small adjustment
            ControlStep(duration=0.1, controls=SimpleControllerState(boost=True, pitch=-0.3)),
            # USE THE RESET FLIP - diagonal flip into ball
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=True, boost=True)),
            ControlStep(duration=0.2, controls=SimpleControllerState(jump=True, pitch=-1.0, yaw=0.4, boost=True)),
            # Recovery
            ControlStep(duration=0.5, controls=SimpleControllerState(pitch=1.0)),
        ])
        
        return self.active_sequence.tick(packet)

    def ground_game_logic(self, packet, my_car, car_location, ball_location, distance, speed):
        """Ground game when not going for aerials"""
        
        # Predict ball movement
        target_location = ball_location
        
        if distance > 1200:
            ball_prediction = self.get_ball_prediction_struct()
            ball_in_future = find_slice_at_time(
                ball_prediction, 
                packet.game_info.seconds_elapsed + min(distance / 1000.0, 2.0)
            )
            if ball_in_future is not None:
                target_location = Vec3(ball_in_future.physics.location)

        # Do speed flips at optimal speeds for kickoff or rushing
        if 0 < speed < 200 and my_car.has_wheel_contact and distance > 1500:
            # Speed flip from standstill (great for kickoffs)
            return self.speed_flip(packet)
        
        # Do stylish diagonal flips at medium speeds
        if 900 < speed < 1100 and my_car.has_wheel_contact and distance > 800:
            return self.diagonal_flip(packet)
        
        # Speed flip at higher speeds for extra boost
        if 1200 < speed < 1400 and my_car.has_wheel_contact and distance > 1000:
            return self.speed_flip(packet)

        # Basic driving
        controls = SimpleControllerState()
        controls.steer = steer_toward_target(my_car, target_location)
        controls.throttle = 1.0
        
        # Smart boost usage
        if distance > 1500 and my_car.boost > 20 and speed < 2200:
            controls.boost = True
        
        return controls

    def diagonal_flip(self, packet):
        """Diagonal flip for style and speed"""
        self.active_sequence = Sequence([
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=True)),
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False)),
            ControlStep(duration=0.2, controls=SimpleControllerState(jump=True, pitch=-1, yaw=0.4)),
            ControlStep(duration=0.8, controls=SimpleControllerState()),
        ])
        return self.active_sequence.tick(packet)

    def speed_flip(self, packet):
        """
        Speed Flip - The fastest way to move in Rocket League
        Diagonal flip with cancel for maximum speed
        """
        self.send_quick_chat(team_only=False, quick_chat=QuickChatSelection.Reactions_Siiiick)
        
        self.active_sequence = Sequence([
            # Initial jump with boost
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=True, boost=True, pitch=0.2)),
            # Release jump briefly
            ControlStep(duration=0.05, controls=SimpleControllerState(jump=False, boost=True)),
            # Diagonal flip (forward-left)
            ControlStep(duration=0.12, controls=SimpleControllerState(
                jump=True, 
                pitch=-1.0,  # Forward
                yaw=-0.25,   # Slight left angle
                boost=True
            )),
            # FLIP CANCEL - pull back stick to stop rotation and maintain speed
            ControlStep(duration=0.18, controls=SimpleControllerState(
                pitch=1.0,   # Pull back to cancel flip
                yaw=-0.15,
                roll=-0.4,   # Air roll to land on wheels
                boost=True
            )),
            # Adjust landing
            ControlStep(duration=0.15, controls=SimpleControllerState(
                pitch=0.3,
                roll=-0.5,
                boost=True
            )),
            # Continue boosting after landing
            ControlStep(duration=0.3, controls=SimpleControllerState(
                boost=True,
                throttle=1.0
            )),
        ])
        
        return self.active_sequence.tick(packet)

    def draw_debug_info(self, my_car, ball_location, speed, distance):
        """Draw debug visualization"""
        car_location = Vec3(my_car.physics.location)
        
        # Draw line to ball
        self.renderer.draw_line_3d(car_location, ball_location, self.renderer.white())
        
        # Draw car info
        info_text = f'Speed: {speed:.0f} | Boost: {my_car.boost} | Tricks: {self.tricks_performed}'
        self.renderer.draw_string_3d(car_location, 1, 1, info_text, self.renderer.white())
        
        # Draw ball target
        self.renderer.draw_rect_3d(ball_location, 12, 12, True, self.renderer.cyan(), centered=True)
        
        # Draw distance indicator
        mid_point = car_location + (ball_location - car_location) * 0.5
        self.renderer.draw_string_3d(mid_point, 1, 1, f'{distance:.0f}u', self.renderer.yellow())
