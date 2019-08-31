from modules.NewportMirrorMounts.Newport_UC8 import AGUC8 as Mirror

class MirrorCom:

    def __init__(self, chan):
        self.mir = Mirror()
        self.mir.initialize(chan)

    def move(self, channel, axis, step):
        self.mir.relativeMove(channel, axis, step)
        if self.mir.getAxisStatus(channel, axis) == 0:
            return 0

    def resetMirror(self):
        self.mir.resetController()

    def setSettings(self, mirror, amplitude):
        for i in range(2):
            self.mir.setStepAmplitude(mirror, i+1, amplitude)