#!/usr/bin/env python3

import numpy as np
import rospy
from sensor_msgs.msg import Joy
from std_srvs.srv import SetBool, SetBoolRequest
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32MultiArray, Float32MultiArray, Bool
from geometry_msgs.msg import PoseArray
from time import sleep


class TeleopNode:
    def __init__(self):
        # Load all params from the parameter server
        self.load_params()

        # Initialize variables for storing positions and states
        self.armposition_1 = np.array([0, 200, 300])
        self.armposition_2 = np.array([0, 200, 300])
        self.end_effector1_angles = np.array([90, 90])
        self.end_effector2_angles = np.array([90, 90])

        # Initialize variables for storing states
        self.T_buttons_initiated_ = False
        self.arm1_initiated = False
        self.arm2_initiated = False
        self.endeffector1_initiated = False
        self.endeffector2_initiated = False
        self.global_frame_point = True
        self.L3_R3_button_prev_state = False
        self.mirror_movement = False
        self.safety_stop_ = False
        self.arm_straight_line = False
        self.arm_free = True
        self.active_cosinusodal = False
        self.active_end_effector_move = False

        self.sinus_forward = True
        self.cosinus_forward = True
        self.cosinus_upward = True
        self.sinus_x_number = 0
        self.cosinus_x_number = 200
        self.cosinus_z_number = 200
        self.function_state = 0

        self.previous_button_pressed = [0] * len(self.button_mapping)
        self.arm_speed_control = 2
        self.joy_data = None
        self.real_armposition_1 = None
        self.real_armposition_1 = None

        # Initialize ROS node with 60 Hz
        self.rate = rospy.Rate(60)

        # Initialize ROS publishers
        self.arm1_position_pub = rospy.Publisher('arm1position', JointState, queue_size=10)
        self.arm2_position_pub = rospy.Publisher('arm2position', JointState, queue_size=10)
        self.arm1_away_position = rospy.Publisher('arm1_calib_stretched_cmd', Bool, queue_size=10)
        self.arm2_away_position = rospy.Publisher('arm2_calib_stretched_cmd', Bool, queue_size=10)
        self.arm1_calib = rospy.Publisher('arm1_calib_cmd', Bool, queue_size=10)
        self.arm2_calib = rospy.Publisher('arm2_calib_cmd', Bool, queue_size=10)
        self.end_effector1_pub = rospy.Publisher('endeffector1', Int32MultiArray, queue_size=10)
        self.end_effector2_pub = rospy.Publisher('endeffector2', Int32MultiArray, queue_size=10)

        # Initialize ROS services
        self.safety_stop_service1 = rospy.ServiceProxy('safety_stop_arm1', SetBool)
        self.safety_stop_service2 = rospy.ServiceProxy('safety_stop_arm2', SetBool)

        # Initialize ROS subscribers
        rospy.Subscriber('arm1_cur_pos', PoseArray, self.arm1_pos_callback)
        rospy.Subscriber('arm2_cur_pos', PoseArray, self.arm2_pos_callback)
        rospy.Subscriber('arm1_angle', Float32MultiArray, self.endeff1_pos_callback)
        rospy.Subscriber('arm2_angle', Float32MultiArray, self.endeff2_pos_callback)
        rospy.Subscriber('joy_arms', Joy, self.joy_callback)

        # Initialize ROS node
        rospy.loginfo('Teleop_node started')
        rospy.loginfo('Press LB and RB to enable the arms')
        rospy.loginfo('Press X and Y to enable the end effectors')
        rospy.loginfo('Press L3 and R3 to enable safety stop')

    def load_params(self):
        try:
            # Get the button and axes mapping from the parameter server
            self.button_mapping = rospy.get_param('button_map')
            self.axes_mapping = rospy.get_param('axes_map')

            # Get button action and corresponding button from parameter server
            self.activate_arm1_button = rospy.get_param('activate_arm1_button')
            self.activate_arm2_button = rospy.get_param('activate_arm2_button')
            self.activate_endef1_button = rospy.get_param('activate_endef1_button')
            self.activate_endef2_button = rospy.get_param('activate_endef2_button')
            self.increase_arm_speed = rospy.get_param('increase_arm_speed')
            self.decrease_arm_speed = rospy.get_param('decrease_arm_speed')
            self.arm_up = rospy.get_param('arm_up')
            self.arm_down = rospy.get_param('arm_down')
            self.arm_x = rospy.get_param('arm_x')
            self.arm_y = rospy.get_param('arm_y')
            self.endef_up = rospy.get_param('endef_up')
            self.endef_side = rospy.get_param('endef_side')
            self.frame_change = rospy.get_param('frame_change')
            self.home_button = rospy.get_param('home_button')
            self.end_button = rospy.get_param('end_button')
            self.mirror_button = rospy.get_param('mirror_button')
            self.function_button = rospy.get_param('away_button')
            self.safety_stop_button = rospy.get_param('safety_stop_button')

            # Get the restrictions from the parameter server
            self.min_x_arm = rospy.get_param('min_x_arm')
            self.max_x_arm = rospy.get_param('max_x_arm')
            self.min_y_arm = rospy.get_param('min_y_arm')
            self.max_y_arm = rospy.get_param('max_y_arm')
            self.min_z_arm = rospy.get_param('min_z_arm')
            self.max_z_arm = rospy.get_param('max_z_arm')

            self.arm_max_speed = rospy.get_param('arm_max_speed')
            self.arm_min_speed = rospy.get_param('arm_min_speed')

            # Variables for boundaries for the end effector
            self.min_x_end_effector = rospy.get_param('min_x_end_effector')
            self.max_x_end_effector = rospy.get_param('max_x_end_effector')

            # Variables for home position for the arms 
            self.home_position_x = rospy.get_param('home_position_x')
            self.home_position_y = rospy.get_param('home_position_y')
            self.home_position_z = rospy.get_param('home_position_z')

            # Variables for end position for the arms
            self.end_position_x = rospy.get_param('end_position_x')
            self.end_position_y = rospy.get_param('end_position_y')
            self.end_position_z = rospy.get_param('end_position_z')

            # List of positions to move
            self.arm_movement = rospy.get_param('arm_movement')
            self.endeff_movement = rospy.get_param('endeff_movement')

            # Variables for sinusoidal movement
            self.sinus_x_start_end = rospy.get_param('sinus_x_start_end')
            self.sinus_speed_x = rospy.get_param('sinus_speed_x')
            self.sinus_y = rospy.get_param('sinus_y')

            # Variables for cosinusoidal movement
            self.cosinus_x_start_end = rospy.get_param('cosinus_x_start_end')
            self.cosinus_z_start_end = rospy.get_param('cosinus_z_start_end')
            self.cosinus_speed_x = rospy.get_param('cosinus_speed_x')
            self.cosinus_speed_z = rospy.get_param('cosinus_speed_z')
            self.cosinus_y = rospy.get_param('cosinus_y')
            rospy.loginfo('Params loaded')

        except:
            rospy.logerr('Failed to load params')

    # Makes position follow the real values when controller is not in use
    def arm1_pos_callback(self, data):
        self.real_armposition_1 = data.poses[0].position
        if not self.arm1_initiated:
            self.armposition_1 = np.array([self.real_armposition_1.x, self.real_armposition_1.y, self.real_armposition_1.z])

    def arm2_pos_callback(self, data):
        self.real_armposition_1 = data.poses[0].position
        if not self.arm2_initiated:
            self.armposition_2 = np.array([self.real_armposition_1.x, self.real_armposition_1.y, self.real_armposition_1.z])

    def endeff1_pos_callback(self, data):
        if not self.endeffector1_initiated:
            angles = np.degrees(data.data)
            self.end_effector1_angles[1] = 180 - np.clip(angles[0], self.min_x_end_effector,
                                                         self.max_x_end_effector)

    def endeff2_pos_callback(self, data):
        if not self.endeffector2_initiated:
            angles = np.degrees(data.data)
            self.end_effector2_angles[1] = 180 - np.clip(angles[0], self.min_x_end_effector,
                                                         self.max_x_end_effector)

    # Calls safety stop service to stop arms
    def safety_stop(self):
        request = SetBoolRequest()
        request.data = self.safety_stop_
        # Arm 1
        try:
            response = self.safety_stop_service1(request)
            if response.success:
                rospy.loginfo('Safety stop arm1 successfully!')
            else:
                rospy.logwarn('Failed to safety stop arm1.')
        except rospy.ServiceException as e:
            rospy.logerr('Service call failed: ' + str(e))

        # Arm 2
        try:
            response = self.safety_stop_service2(request)
            if response.success:
                rospy.loginfo('Safety stop arm2 successfully!')
            else:
                rospy.logwarn('Failed to safety stop arm2.')
        except rospy.ServiceException as e:
            rospy.logerr('Service call failed: ' + str(e))


    # Used for checking if the arm has reached the desired position
    def lists_close(self, list1, list2, tolerance=10):
        if abs(list1.x - list2[0]) > tolerance:
            return True
        if abs(list1.y - list2[1]) > tolerance:
            return True
        if abs(list1.z - list2[2]) > tolerance:
            return True
        else:
            return False
        
    # Function for controlling the arms
    def controll_arm(self, pos, mirror=False, left=False):
        # pos[0] # x
        # pos[1] # y
        # pos[2] # z
        if self.move_arm_from_list:
            if self.arm_right_move_index == len(self.arm_movement):
                self.self.arm_right_move_index == 0
                self.move_arm_from_list == False
                rospy.loginfo("Done moving")
                return pos
            
            i = self.arm_movement[self.arm_right_move_index]
            if not self.lists_close(self.real_armposition_1, i):
                self.arm_right_move_index += 1
                pos[0] = i[0]
                pos[1] = i[1]
                pos[2] = i[2]

            return pos


        if self.arm_straight_line:
            # Checks if the arm should move forward or backward
            if self.sinus_forward:
                self.sinus_x_number += self.sinus_speed_x
            if not self.sinus_forward:
                self.sinus_x_number -= self.sinus_speed_x

            # Checks if the arm should have reached the end of the movement, if so change direction
            if self.sinus_x_number > self.sinus_x_start_end[1]:
                self.sinus_forward = False

            if self.sinus_x_number < self.sinus_x_start_end[0]:
                self.sinus_forward = True

            pos[0] = self.sinus_x_number
            pos[1] = self.sinus_y
            return pos


            # Reset the arm to home position
        if self.arm_free:
            if self.evaluate_button(self.home_button):
                pos[0] = self.home_position_x
                pos[1] = self.home_position_y
                pos[2] = self.home_position_z
                rospy.loginfo('Arm reset ' + ('2' if left else '1'))
                return pos

            # Controls for right arm
            if not left:
                # Check if the global frame is enabled
                if self.global_frame_point:
                    x_nav = self.joy_data.axes[self.axes_mapping[self.arm_x]]
                    y_nav = self.joy_data.axes[self.axes_mapping[self.arm_y]]
                else:
                    x_nav = -self.joy_data.axes[self.axes_mapping[self.arm_y]]
                    y_nav = self.joy_data.axes[self.axes_mapping[self.arm_x]]

            # Controls for left arm
            if left:
                if self.global_frame_point:
                    x_nav = -self.joy_data.axes[self.axes_mapping[self.arm_x]]
                    y_nav = -self.joy_data.axes[self.axes_mapping[self.arm_y]]
                    # Check if mirror is enabled
                    if mirror:
                        x_nav = self.joy_data.axes[self.axes_mapping[self.arm_x]]
                        y_nav = self.joy_data.axes[self.axes_mapping[self.arm_y]]
                else:
                    x_nav = -self.joy_data.axes[self.axes_mapping[self.arm_y]]
                    y_nav = self.joy_data.axes[self.axes_mapping[self.arm_x]]
                    if mirror:
                        x_nav = self.joy_data.axes[self.axes_mapping[self.arm_x]]
                        y_nav = self.joy_data.axes[self.axes_mapping[self.arm_y]]

            # Increases the arm movement with the speed and within the boundaries
            pos[0] += x_nav * self.arm_speed_control
            pos[0] = np.clip(pos[0], self.min_x_arm, self.max_x_arm)

            pos[1] += y_nav * self.arm_speed_control
            pos[1] = np.clip(pos[1], self.min_y_arm, self.max_y_arm)

            # Check if the LT, RT buttons are initiated
            if self.T_buttons_initiated_:
                # Uses the LT and RT buttons to control the z-axis linearly
                pos[2] += (1 - self.joy_data.axes[self.axes_mapping[self.arm_up]]
                        ) / 2 * self.arm_speed_control
                pos[2] -= (1 - self.joy_data.axes[self.axes_mapping[self.arm_down]]
                        ) / 2 * self.arm_speed_control
                pos[2] = np.clip(pos[2], self.min_z_arm, self.max_z_arm)

            return pos


    # Function for moving the arm cosinusodial
    def move_arm_cosinusodial(self, pos):

        x_p = 100
        y_p = 200
        r = 100
        
        # Checks if the arm should have reached the end of the movement, if so change direction
        if self.cosinus_x_number > self.cosinus_x_start_end[1]:
            self.cosinus_forward = False

        if self.cosinus_x_number < self.cosinus_x_start_end[0]:
            self.cosinus_forward = True

        # Checks if the arm should move forward or backward
        if self.cosinus_forward:
            self.cosinus_x_number += self.cosinus_speed_x
        """
        if self.cosinus_x_number >= x_p:
                self.cosinus_x_number += 0.2 + (1 - (self.cosinus_x_number - self.cosinus_x_start_end[1]))/self.cosinus_x_start_end[1]
        if self.cosinus_x_number < x_p:
        self.cosinus_x_number += 0.2 + (1 - (self.cosinus_x_start_end[0] - self.cosinus_x_number))/self.cosinus_x_start_end[1]
        """

        if not self.cosinus_forward:
            self.cosinus_x_number -= self.cosinus_speed_x
        """
        if self.cosinus_x_number >= x_p:
                self.cosinus_x_number -= 0.2 + (1 - (self.cosinus_x_number - self.cosinus_x_start_end[1]))/self.cosinus_x_start_end[1]
        if self.cosinus_x_number < x_p:
        self.cosinus_x_number -= 0.2 + (1 - (self.cosinus_x_start_end[0] - self.cosinus_x_number))/self.cosinus_x_start_end[1]
        """
        x_norm = float(self.cosinus_x_number)/float(self.cosinus_x_start_end[1])*np.pi*2

        # Checks if the arm should move upward or downward
        if self.cosinus_forward:
            self.cosinus_z_number = 200 + 80 * np.sin(x_norm)
        if not self.cosinus_forward:
            self.cosinus_z_number = 200 - 80 * np.sin(x_norm)
	

        pos[0] = self.cosinus_x_number
        pos[1] = self.cosinus_y
        pos[2] = self.cosinus_z_number
        return pos

    # Function for controlling the end effector
    def controll_endeff(self, angle, mirror=False, left=False):

        # Puts the end effector to home position
        if self.evaluate_button(self.home_button):
            angle[0] = 90
            angle[1] = 90
            rospy.loginfo('End effector reset')
            return angle

        # Puts the end effector to away position
        if self.evaluate_button(self.end_button):
            angle[0] = 0
            angle[1] = 0
            rospy.loginfo('End effector away')
            return angle

            # Controls for right end effector
        if not left:
            if self.global_frame_point:
                m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                m2_nav = self.joy_data.axes[self.axes_mapping[self.endef_side]]
            else:
                m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                m2_nav = self.joy_data.axes[self.axes_mapping[self.endef_side]]

        # Controls for left end effector
        if left:
            if self.global_frame_point:
                m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                m2_nav = -self.joy_data.axes[self.axes_mapping[self.endef_side]]
                if mirror:
                    m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                    m2_nav = self.joy_data.axes[self.axes_mapping[self.endef_side]]
            else:
                m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                m2_nav = -self.joy_data.axes[self.axes_mapping[self.endef_side]]
                if mirror:
                    m1_nav = self.joy_data.axes[self.axes_mapping[self.endef_up]]
                    m2_nav = self.joy_data.axes[self.axes_mapping[self.endef_side]]

        # Increasing the values within the limits
        angle[0] += m1_nav * self.arm_speed_control
        angle[0] = np.clip(angle[0], self.min_x_end_effector, self.max_x_end_effector)

        angle[1] += m2_nav * self.arm_speed_control
        angle[1] = np.clip(angle[1], self.min_x_end_effector, self.max_x_end_effector)

        # Returns the updated variables so it can be stored
        return angle
    
    def move_endeff_from_list(self, left=0):
        for i in self.endeff_movement:
            # Arm 1
            if left == 0:
                # Publishes the position to the arm
                self.end_effector1_angles[0] = i[0]
                self.end_effector1_angles[1] = i[1]

            # Arm 2
            if left == 1:
                # Publishes the position to the arm
                self.end_effector2_angles[0] = i[0]
                self.end_effector2_angles[1] = i[1]

            # Both arms
            if left == 2:
                # Publishes the position to the arms
                self.end_effector1_angles[0] = i[0]
                self.end_effector1_angles[1] = i[1]

                self.end_effector2_angles[0] = i[0]
                self.end_effector2_angles[1] = i[1]

            array1 = Int32MultiArray()
            array1.data = self.end_effector1_angles
            self.end_effector1_pub.publish(array1)

            array2 = Int32MultiArray()
            array2.data = self.end_effector2_angles
            self.end_effector2_pub.publish(array2)

            sleep(3)

        # Prints when the arm has reached the desired position
        rospy.loginfo('Done moving')
        self.active_end_effector_move = False

    # Callback function for the "joy" topic to control hz
    def joy_callback(self, data):
        self.joy_data = data

    # Function for evaluating if a button is pressed or held down
    def evaluate_button(self, button):
        return self.joy_data.buttons[self.button_mapping[button]] == 1 and \
            self.previous_button_pressed[self.button_mapping[button]] != 1

    # Loop that keeps the ros node running
    def run(self):
        # Checks if the joy_data has been received
        while not rospy.is_shutdown() and self.joy_data is not None:
            # Bypass that RT and LT starts with 0 as default value and default value changes to
            # 1 when pressed.
            # Check if the RT and LT buttons have been pressed, first then are they in use
            if not self.T_buttons_initiated_ and self.joy_data.axes[2] == 1 and \
                    self.joy_data.axes[5] == 1:
                self.T_buttons_initiated_ = True
                rospy.loginfo("LT and RT are ready to be used")

            if self.evaluate_button(self.activate_arm1_button):
                self.arm1_initiated = not self.arm1_initiated
                rospy.loginfo('Arm 1 ' + ('enabled' if self.arm1_initiated else 'disabled'))

            if self.evaluate_button(self.activate_arm2_button):
                self.arm2_initiated = not self.arm2_initiated
                rospy.loginfo('Arm 2 ' + ('enabled' if self.arm2_initiated else 'disabled'))

            if self.evaluate_button(self.activate_endef1_button):
                self.endeffector1_initiated = not self.endeffector1_initiated
                rospy.loginfo('End effector 1 ' + (
                    'enabled' if self.endeffector1_initiated else 'disabled'))

            if self.evaluate_button(self.activate_endef2_button):
                self.endeffector2_initiated = not self.endeffector2_initiated
                rospy.loginfo('End effector 2 ' + (
                    'enabled' if self.endeffector2_initiated else 'disabled'))

            if self.evaluate_button(self.frame_change):
                self.global_frame_point = not self.global_frame_point
                rospy.loginfo(
                    'Global frame ' + ('enabled' if self.global_frame_point else 'disabled'))

            if self.evaluate_button(self.mirror_button):
                self.mirror_movement = not self.mirror_movement
                rospy.loginfo('Mirror ' + ('enabled' if self.mirror_movement else 'disabled'))

            if self.evaluate_button(self.function_button):
                self.function_state = (self.function_state + 1) % 7
                if self.function_state == 0:
                    rospy.loginfo("Status: Free")
                elif self.function_state == 1:
                    rospy.loginfo("Status: Calibration")
                elif self.function_state == 2:
                    rospy.loginfo("Status: Arms away")
                elif self.function_state == 3:
                    self.arm_movement = rospy.get_param('/arm_movement')
                    rospy.loginfo("Status: Move to points")
                elif self.function_state == 4:
                    rospy.loginfo("Status: Move sinusodial")
                elif self.function_state == 5:
                    rospy.loginfo("Status: Move cosinusodial")
                elif self.function_state == 6:
                    self.endeff_movement = rospy.get_param('/endeff_movement')
                    rospy.loginfo("Status: Move end_effectors to points")
                else:
                    rospy.logwarn("Unknown status value: {}".format(self.function_state))

            if self.evaluate_button(self.end_button):
                if self.function_state == 0:
                    self.arm_free = not self.arm_free
                    rospy.loginfo(
                        'Arm controller move ' + ('enabled' if self.arm_straight_line else 'disabled'))

                if self.function_state == 1:
                    if self.arm1_initiated and self.arm2_initiated:
                        rospy.logwarn("Calibrate one arm at a time")
                    elif self.arm1_initiated:
                        self.arm1_calib.publish(True)
                        rospy.loginfo('Arm 1 calibrating')
                    elif self.arm2_initiated:
                        self.arm2_calib.publish(True)
                        rospy.loginfo('Arm 2 calibrating')

                elif self.function_state == 2:
                    if self.arm1_initiated and self.arm2_initiated:
                        rospy.logwarn("Put one arm away at a time")
                    elif self.arm1_initiated:
                        self.arm1_away_position.publish(True)
                        rospy.loginfo('Arm 1 away position')
                    elif self.arm2_initiated:
                        self.arm2_away_position.publish(True)
                        rospy.loginfo('Arm 2 away position')

                elif self.function_state == 3:
                    if self.arm1_initiated and self.arm2_initiated:
                        rospy.loginfo('Arm 1 and 2 prevmove')
                        self.move_arm_from_list(left=2)
                    elif self.arm1_initiated:
                        rospy.loginfo('Arm 1 prevmove')
                        self.move_arm_from_list()
                    elif self.arm2_initiated:
                        rospy.loginfo('Arm 2 prevmove')
                        self.move_arm_from_list(left=1)


                elif self.function_state == 4:
                    self.arm_straight_line = not self.arm_straight_line
                    rospy.loginfo(
                        'Sinusoidal ' + ('enabled' if self.arm_straight_line else 'disabled'))

                elif self.function_state == 5:
                    self.active_cosinusodal = not self.active_cosinusodal
                    rospy.loginfo('Co-sinusoidal ' + (
                        'enabled' if self.active_cosinusodal else 'disabled'))
                    
                elif self.function_state == 6:
                    self.active_end_effector_move = not self.active_end_effector_move
                    rospy.loginfo('Endeffector_pre_move ' + (
                        'enabled' if self.active_end_effector_move else 'disabled'))

            # Adjust the speed of the arms and end effectors
            if self.evaluate_button(self.increase_arm_speed):
                self.arm_speed_control += 0.1
                self.arm_speed_control = np.clip(self.arm_speed_control, self.arm_min_speed,
                                                    self.arm_max_speed)
                rospy.loginfo("Arm speed: %s", self.arm_speed_control)

            if self.evaluate_button(self.decrease_arm_speed):
                self.arm_speed_control -= 0.1
                self.arm_speed_control = np.clip(self.arm_speed_control, self.arm_min_speed,
                                                    self.arm_max_speed)
                rospy.loginfo("Arm speed: %s", self.arm_speed_control)

            # Activates the emergency stop 
            if self.joy_data.buttons[self.button_mapping[self.safety_stop_button[0]]] == 1 and \
                    self.joy_data.buttons[self.button_mapping[
                        self.safety_stop_button[1]]] == 1 and not self.L3_R3_button_prev_state:
                self.safety_stop_ = not self.safety_stop_
                self.safety_stop()
                rospy.loginfo('Safety ' + ('enabled' if self.safety_stop_ else 'disabled'))

            # Pushes safety stop only once, when hold down
            if self.joy_data.buttons[self.button_mapping[self.safety_stop_button[0]]] == 1 and \
                    self.joy_data.buttons[self.button_mapping[self.safety_stop_button[1]]] == 1:
                self.L3_R3_button_prev_state = True
            else:
                self.L3_R3_button_prev_state = False

            if not self.safety_stop_:
                # Will not publish data when safety stop is enabled
                # Controls only the arms that are activated
                if self.arm1_initiated and self.function_state == 0:
                    self.armposition_1 = self.controll_arm(self.armposition_1)

                if self.arm2_initiated and self.function_state == 0:
                    self.armposition_2 = self.controll_arm(self.armposition_2, self.mirror_movement,
                                                            left=True)

                if self.endeffector1_initiated and not self.active_end_effector_move:
                    self.end_effector1_angles = self.controll_endeff(self.end_effector1_angles)

                if self.endeffector2_initiated and not self.active_end_effector_move:
                    self.end_effector2_angles = self.controll_endeff(self.end_effector2_angles,
                                                                    self.mirror_movement, left=True)
                """
                if self.endeffector1_initiated and self.endeffector2_initiated and self.active_end_effector_move:
                    self.move_endeff_from_list(left=2)

                elif self.endeffector1_initiated and self.active_end_effector_move:
                    self.move_endeff_from_list()

                elif self.endeffector2_initiated and self.active_end_effector_move:
                    self.move_endeff_from_list(left=1)

                if self.arm1_initiated and self.active_sinusodal and not self.active_cosinusodal:
                    self.armposition_1 = self.move_arm_sinusodial(self.armposition_1)

                if self.arm2_initiated and self.active_sinusodal and not self.active_cosinusodal:
                    self.armposition_2 = self.move_arm_sinusodial(self.armposition_2)

                if self.arm1_initiated and self.active_cosinusodal and not self.active_sinusodal:
                    self.armposition_1 = self.move_arm_cosinusodial(self.armposition_1)

                if self.arm2_initiated and self.active_cosinusodal and not self.active_sinusodal:
                    self.armposition_2 = self.move_arm_cosinusodial(self.armposition_2)
                """

                # Publish only position when controller is used
                if self.arm1_initiated:
                    joint_state = JointState()
                    joint_state.position = self.armposition_1
                    joint_state.velocity = [0.0]
                    joint_state.effort = [0]
                    self.arm1_position_pub.publish(joint_state)

                if self.arm2_initiated:
                    joint_state = JointState()
                    joint_state.position = self.armposition_2
                    joint_state.velocity = [0.0]
                    joint_state.effort = [0]
                    self.arm2_position_pub.publish(joint_state)

                # Publish only angles to end effector
                array1 = Int32MultiArray()
                array1.data = self.end_effector1_angles
                self.end_effector1_pub.publish(array1)

                array2 = Int32MultiArray()
                array2.data = self.end_effector2_angles
                self.end_effector2_pub.publish(array2)

            # Stores which button is being held down
            self.previous_button_pressed = self.joy_data.buttons
            self.rate.sleep()


if __name__ == '__main__':
    # Initialize the ROS node
    rospy.init_node('teleop_node_arms')
    Teleop_Node = TeleopNode()
    Teleop_Node.run()

"""
Nytt oppsett:
En funskjon har hvor den er og incrementer dit den skal.
En annen funsksjon sier hvor den skal til. Har kan alle andre funskjoner brukes.

End effector error if moved to fast

Safety NEED to work ALL time
"""
