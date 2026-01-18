"""
Aerial utilities for freestyle bot
Helper functions for aerial navigation and control
"""

import math
from util.vec import Vec3


def aerial_to_target(car_physics, target_location, current_time):
    """
    Calculate controls needed to aerial toward a target
    Returns pitch, yaw, roll values
    """
    car_location = Vec3(car_physics.location)
    car_rotation = car_physics.rotation
    
    # Vector from car to target
    to_target = target_location - car_location
    distance = to_target.length()
    
    if distance == 0:
        return 0, 0, 0
    
    to_target = to_target.normalized()
    
    # Get car's forward vector
    pitch = car_rotation.pitch
    yaw = car_rotation.yaw
    roll = car_rotation.roll
    
    # Calculate forward direction
    forward_x = math.cos(pitch) * math.cos(yaw)
    forward_y = math.cos(pitch) * math.sin(yaw)
    forward_z = math.sin(pitch)
    forward = Vec3(forward_x, forward_y, forward_z)
    
    # Calculate up direction
    up_x = -math.sin(pitch) * math.cos(yaw)
    up_y = -math.sin(pitch) * math.sin(yaw)
    up_z = math.cos(pitch)
    up = Vec3(up_x, up_y, up_z)
    
    # Calculate right direction (cross product of forward and up)
    right = forward.cross(up)
    
    # Calculate the angles needed to point at target
    pitch_control = to_target.dot(up)
    yaw_control = to_target.dot(right)
    roll_control = 0  # Keep level for now
    
    return pitch_control, yaw_control, roll_control


def should_aerial(car, ball_location, ball_velocity, min_height=300, max_distance=2500, min_boost=25):
    """
    Determines if we should attempt an aerial
    """
    car_location = Vec3(car.physics.location)
    distance = car_location.dist(ball_location)
    
    # Check conditions
    if ball_location.z < min_height:
        return False
    if distance > max_distance:
        return False
    if car.boost < min_boost:
        return False
    if car.is_super_sonic:  # Don't aerial if we're supersonic on ground
        return False
        
    return True


def time_to_reach(car_location, target_location, car_velocity):
    """
    Rough estimate of time to reach target
    """
    distance = car_location.dist(target_location)
    speed = car_velocity.length()
    
    if speed < 100:
        speed = 1000  # Assume we'll boost
    
    return distance / speed


def get_car_facing_vector(car_rotation):
    """
    Get the direction the car is facing as a Vec3
    """
    pitch = car_rotation.pitch
    yaw = car_rotation.yaw
    
    x = math.cos(pitch) * math.cos(yaw)
    y = math.cos(pitch) * math.sin(yaw)
    z = math.sin(pitch)
    
    return Vec3(x, y, z)


def angle_between_vectors(v1, v2):
    """
    Calculate angle between two vectors in radians
    """
    dot = v1.dot(v2)
    mag1 = v1.length()
    mag2 = v2.length()
    
    if mag1 == 0 or mag2 == 0:
        return 0
    
    cos_angle = dot / (mag1 * mag2)
    # Clamp to avoid math domain errors
    cos_angle = max(-1, min(1, cos_angle))
    
    return math.acos(cos_angle)


def is_facing_target(car, target_location, max_angle=0.5):
    """
    Check if car is generally facing the target
    max_angle in radians (0.5 ≈ 28 degrees)
    """
    car_location = Vec3(car.physics.location)
    car_facing = get_car_facing_vector(car.physics.rotation)
    
    to_target = (target_location - car_location).normalized()
    
    angle = angle_between_vectors(car_facing, to_target)
    
    return angle < max_angle


def calculate_boost_usage(distance, current_boost):
    """
    Determine if we have enough boost for the aerial
    Returns True if we should use boost
    """
    # Very rough calculation
    # Assume we need about 10 boost per 100 units of distance in air
    estimated_boost_needed = distance / 100 * 10
    
    return current_boost > estimated_boost_needed
