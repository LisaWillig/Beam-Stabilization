# -*- coding: utf-8 -*-
"""

Send Commands to Newport UC8 Motor Controller
Created on Sept 2018
@author: Jan, Lisa (some code von Vincent Paeder, github vpaeder)

LIST OF COMMANDS:
MR — Set to remote mode
PR — Relative move
RS — Reset controller
SU — Set step amplitude (or get step amplitude setting)

LIST OF NOT INCLUDED COMMANDS:
DL — Set step delay or get step delay setting
JA — Start jog motion or get jog mode
ML — Set to local mode (mak eno sense for UC8)
SU — (Set step amplitude or) get step amplitude setting
TE — Get error of previous command
TP — Tell number of steps
VE — Get controller firmware version

LIST OF NOT INCLUDED COMMANDS FOR POSITIONERS WITH END SWITCH:
MA — Measure current position
MV — Move to limit
PA — Absolute move
PH —Tell limit status
"""
import time as t
import pyvisa as visa


class AGUC8():
    """
    Device driver for Newport Agilis AG-UC motion controller
    """

    def __init__(self, config):
        self.timeout = 1.0
        self.instr = None
        self.channel = None
        print(config.mirrorAddress)
        self.address = str(config.mirrorAddress)

    def initialize(self):
        # create device handle
        rm = visa.ResourceManager()
        print(rm.list_resources())
        self.instr = rm.open_resource(self.address)
        self.instr.baud_rate = 921600
        self.instr.data_bits = 8
        self.instr.stop_bits = visa.constants.StopBits.one
        self.instr.timeout = 2000
        self.instr.parity = visa.constants.Parity.none
        self.instr.term_chars = "\r\n"
        self.instr.write("MR")
        #self.setChannel(1)

    def write(self, axis, cmd):
        cmdstr = str(axis) + cmd
        self.instr.write(cmdstr)

    def stopConnection(self):

        self.instr.close()

    def read(self, axis, cmd):
        cmdstr = str(axis) + cmd
        result = ""
        while result == "":
            result = self.instr.ask(cmdstr)
        return result[3:]

    def resetController(self):
        """
        RS: Resets the controller. All temporary settings are reset to default
        and the controller is in local mode.
        """
        print("reinitialize..")
        self.instr.write("RS")
        t.sleep(10)
        self.initialize()

    def setChannel(self, channel):
        """
        CC: This command is specific to AG-UC8. The piezo actuators are selected
        by pairs which are grouped in four channels. This command changes the
        selected channel by an integer from 1 to 4.

        Description: The QRESET command resets a power supply quench condition
        and returns the supply to STANDBY
        """
        if self.channel != channel:
            print("Changing channel from "+str(self.channel) + " to " + str(
                channel))
            self.channel = channel
            cmdstr = "CC"+str(channel)
            self.instr.write(cmdstr)

    def relativeMove(self, channel, axis, steps):
        """
        PR: Starts a relative move of steps with step amplitude defined by the
        SU command
        """
        self.setChannel(channel)
        print("move" + str(steps))
        self.write(axis, "PR" + str(steps))

    def stopMotion(self, channel, axis):
        """
        ST:Stops the motion on the defined axis. Sets the state to ready.
        """
        self.setChannel(channel)
        #print("stop motion of axis " + str(axis)+ " from channel "+str(channel))
        self.write("ST")

    def setStepAmplitude(self, channel, axis, ampl):
        """
        SU: Sets the step amplitude (step size) in positive or negative
        direction. If the parameter is positive, it will set the step amplitude
        in the forward direction. If the parameter is negative, it will set the
        step amplitude in the backward direction.
        The step amplitude is a relative measure. The step amplitude corresponds
        to the amplitude of the electrical signal sent to the Agilis motor.
        There is no linear correlation between the step amplitude and the
        effective motion size. In particular, too low a setting for the step
        amplitude may result in no output motion. Also, the same step amplitude
        setting for forward and backward  direction may result in different size
        motion steps. Also, the motion step size corresponding to a step
        amplitude setting may vary by position, load, and
        throughout the life time of the product. The step amplitude setting is
        not
        stored after power down. The default value after power-up is 16.
        This step size is used with the commands PR, JA1, JA4, MV1, and MV4, but
        not
        with JA2, JA3, MV2, and MV3. JA2, JA3, MV2, MV3 use the maximum step
        amplitude,
        equivalent to xxSU50 setting.
        """
        self.setChannel(channel)
        #print("set step amplitude to " + str(ampl))
        self.write(axis, "SU" + str(ampl))

    def getStepAmplitude(self, channel, axis):

        self.setChannel(channel)
        answer = self.read(axis, "SU+?")
        print("step amplitude + is " + str(answer))
        answer = self.read(axis, "SU-?")
        print("step amplitude - is " + str(answer))

    def getPosition(self, channel, axis):

        self.setChannel(channel)
        answer = self.read(axis, "TP")
        print("Position " + str(axis) +" "+ str(answer))

    def getAxisStatus(self, channel, axis):
        """
        TS: Returns the status of the axis:
        0 - ready
        1 - stepping
        2 - jogging
        3 - moving to limit
        """
        self.setChannel(channel)
        status = self.read(axis, "TS")
        status = int(status[:-2])
        return status

    def setZeroPosition(self, channel, axis):
        """
        ZP: Resets the step counter to zero. See TP command for further details.
        """
        self.setChannel(channel)
        print("set to zero")
        self.write(axis, "ZP")


def main():
    mirror = AGUC8()
    mirror.initialize()
    #mirror.setZeroPosition(2,1)
    #mirror.setZeroPosition(2,2)
    #mirror.relativeMove(2, 1, +10)
    #mirror.relativeMove(2, 1, -10)
    #t.sleep(0.5)
    #mirror.resetController()
    mirror.relativeMove(1, 1, +10)
    mirror.relativeMove(1   , 1, -10)
    mirror.getPosition(2,1)
    mirror.getPosition(2,2)

    mirror.stopConnection()


if __name__ == '__main__':
        main()
