import numpy as np
import pyqtgraph as pg
import pyqtgraph.ptime as ptime
import sys
import os
from datetime import datetime
from PyQt5 import QtGui, uic
import PyQt5
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from pyqtgraph.Qt import QtGui, QtCore
import time as t
from matplotlib import cm
from scipy.optimize import curve_fit
from pypylon import genicam
import pypylon
from config import *

from modules.MirrorCommunication import MirrorCom
from modules.BaslerCommunication import BaslerMultiple as Basler
from modules.saveSettings import GUISettings

Mirror_Calculations = dict()
MirrorStatus = dict()

for i in range(CamsToUse):
    Mirror_Calculations[i] = {}
    MirrorStatus[i] = {}

class MyWindow(PyQt5.QtWidgets.QMainWindow):
    """
    Msin Class handeling GUI inputs, main  and data analysis
    """

    def __init__(self, parent=None):

        super(MyWindow, self).__init__(parent)

        # load GUI from .ui file (created in QtDesigner)
        self.ui = uic.loadUi('GUI\\Beamstabilization_V2.ui', self)

        # Variables used for Tracking Initialization Status and GUI Choices
        self.status = "StandBy"
        self.ui.setWindowTitle("Beamstabilization")
        self.log = None
        self.config = False
        self.mirror = None
        self.b_align = False
        self.newStart = 0
        self.blog = 0
        self.b_centerLine = 1

        # read last reference position
        self.Save = saveClass()
        if self.Save.readLastConfig():
            self.config = True

        self.correct = Correction()

        # Initialize GUI plots and images
        self.init_ui()

        self.Setting = GUISettings()
        self.Setting.guirestore(self.ui, QtCore.QSettings('./GUI/saved.ini', QtCore.QSettings.IniFormat))

        # Connect Buttons with Function calls
        self.readLastReferencePosition()
        self.btn_Exit.clicked.connect(self.close)
        self.btn_Start.clicked.connect(self.startAligning)
        self.btn_setCenter.clicked.connect(self.newCenter)
        self.btn_showCenter.clicked.connect(self.displayCenterLine)
        self.line_thresholdPercentage.returnPressed.connect(self.getThresholdPercentage)
        self.btn_moveMirror.clicked.connect(self.moveSingleMirror)
        #self.btn_FitValue.toggled.connect(self.fitCenter)

        # show GUI
        self.show()
        self.Main()

    def moveSingleMirror(self):
        """
        Move an attached Newport mirror with the values from the Interface
        """

        self.mirrorInit()
        self.mirror.move(int(self.line_mirror.text()), int(self.line_axis.text()), int(self.line_step.text()))

    def displayCenterLine(self):
        """
        Display or remove the center lines of the image,
        so the absolute center of the CCD
        """

        if self.b_centerLine == 0:
            for i in range(CamsToUse):
               self.vb[i].removeItem(self.xCenterAbs[i])
               self.vb[i].removeItem(self.yCenterAbs[i])
            self.b_centerLine = 1
        else:
            for i in range(CamsToUse):
                self.vb[i].addItem(self.xCenterAbs[i])
                self.vb[i].addItem(self.yCenterAbs[i])
            self.b_centerLine = 0

    def displayThresholdlines(self, i):
        if Mirror_Calculations[i]["Fit"] == True and self.b_showlines[i] == False:
            self.vb[i].addItem(self.xThresholdLinePlus[i])
            self.vb[i].addItem(self.yThresholdLinePlus[i])
            self.vb[i].addItem(self.xThresholdLineMinus[i])
            self.vb[i].addItem(self.yThresholdLineMinus[i])
            self.vb[i].addItem(self.xCenter[i])
            self.vb[i].addItem(self.yCenter[i])
            self.b_showlines[i] = True
        elif self.b_showlines[i] == True:
            self.vb[i].removeItem(self.xThresholdLinePlus[i])
            self.vb[i].removeItem(self.yThresholdLinePlus[i])
            self.vb[i].removeItem(self.xThresholdLineMinus[i])
            self.vb[i].removeItem(self.yThresholdLineMinus[i])
            self.vb[i].removeItem(self.xCenter[i])
            self.vb[i].removeItem(self.yCenter[i])
            self.b_showlines[i] = False

    def startAligning(self):
        """
        Start alignment,
        set Status to "Adjust",
        change text of button
        """

        if not self.b_align:
            self.b_align = True
            self.status = "Adjust"
            self.btn_Start.setText("Stop Adjustement")
        else:
            self.b_align = False
            if self.btn_Logging.isChecked():
                self.status = "Observing"
            else:
                self.status = "StandBy"
            self.btn_Start.setText("Start Adjustement")

    def readLastReferencePosition(self):
        """
        get last reference position
        """

        Save = saveClass()
        self.config = Save.readLastConfig()

    def newCenter(self):
        """
        write current center as reference too file and dictionary
        """

        self.Save = saveClass()
        self.Save.writeNewCenter()

        for i in range(2):
            self.setCenterValue(i)

    def setCenterValue(self, mirror):
        """
        Set the current center of the gaussfit as center for each mirror
        :param mirror:
        """

        if self.btn_FitValue.isChecked():
            Mirror_Calculations[mirror]["GoalPixel_X"] = Mirror_Calculations[mirror]["Center_GaussFitX"]
            Mirror_Calculations[mirror]["GoalPixel_Y"] = Mirror_Calculations[mirror]["Center_GaussFitY"]
        else:
            Mirror_Calculations[mirror]["GoalPixel_X"] = Mirror_Calculations[mirror]["CoM_X"]
            Mirror_Calculations[mirror]["GoalPixel_Y"] = Mirror_Calculations[mirror]["CoM_Y"]
        self.correct.setThresholdValues(mirror, self.thresholdPercentage)

    def init_ui(self):
        """
        Initialize Plots and Images of the UI.
        The Main CCD image displays the current center of
        gaussfit (red) and the threshold values for adjustement of x and y (yellow) for both
        dimensions.
        Two plots at the side of the image display the vertical and horizontal integration of 
        the image
        """

        self.vb =[]
        self.Image = []
        self.xCenter = []
        self.yCenter = []
        self.xCenterAbs = []
        self.yCenterAbs = []
        self.xThresholdLinePlus = []
        self.yThresholdLinePlus= []
        self.xThresholdLineMinus = []
        self.yThresholdLineMinus = []
        # Plots
        self.PlotY = []
        self.PlotX = []
        self.b_showlines = []

        # Left Image
        leftImage = self.ImageBox.addViewBox(row=0, col=0)
        leftPlotX = self.ImageBox.addPlot(row=1, col=0)
        leftPlotY = self.ImageBox.addPlot(row=0, col=1)

        self.vb.append(leftImage)
        self.PlotX.append(leftPlotX)
        self.PlotY.append(leftPlotY)

        # Right Image
        rightImage = self.ImageBox2.addViewBox(row=0, col=0)
        rightPlotX = self.ImageBox2.addPlot(row=1, col=0)
        rightPlotY = self.ImageBox2.addPlot(row=0, col=1)

        self.vb.append(rightImage)
        self.PlotX.append(rightPlotX)
        self.PlotY.append(rightPlotY)

        for i in range(CamsToUse):
            self.vb[i].setAspectLocked(True)
            self.Image.append(pg.ImageItem())
            self.xCenter.append(pg.InfiniteLine(pen=(215, 0, 26), angle=90))
            self.yCenter.append(pg.InfiniteLine(pen=(215, 0, 26), angle=0))
            self.xCenterAbs.append(pg.InfiniteLine(pen=(0, 200, 26), angle=90))
            self.yCenterAbs.append(pg.InfiniteLine(pen=(0, 200, 26), angle=0))
            self.xThresholdLinePlus.append(pg.InfiniteLine())
            self.yThresholdLinePlus.append(pg.InfiniteLine(angle=0))
            self.xThresholdLineMinus.append(pg.InfiniteLine())
            self.yThresholdLineMinus.append(pg.InfiniteLine(angle=0))
            self.b_showlines.append(False)


        # Add Items to Viewbox
        for i in range(CamsToUse):
            self.vb[i].addItem(self.Image[i])
            self.PlotX[i].setXLink(self.Image[i].getViewBox())
            self.PlotY[i].setYLink(self.Image[i].getViewBox())

        # Set Layout
        self.ImageBox.ci.layout.setColumnMaximumWidth(1, 100)
        self.ImageBox.ci.layout.setRowMaximumHeight(1, 100)
        self.ImageBox2.ci.layout.setColumnMaximumWidth(1, 100)
        self.ImageBox2.ci.layout.setRowMaximumHeight(1, 100)

        self.getThresholdPercentage()
        self.setupPlots()

    def getThresholdPercentage(self):
        """
        Set the threshold by getting value from GUI
        """

        self.thresholdPercentage = float(self.ui.line_thresholdPercentage.text())
        for i in range(CamsToUse):
            self.correct.setThresholdValues(i, self.thresholdPercentage)

    def Main(self):
        """
        Initialize Cameras and start QTimer
        """

        self.initializeCams()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def initializeCams(self):
        """
        Start communication with cameras, 
        here models from Basler are used
        """
        self.cam = Basler(namesCamsToUse)
        self.cam.openCommunications()
        self.cam.setCameraParameters(exposureTime)
        self.cam.startAquisition()

    def update(self):
        """
        update determining the status of program (idle, logging, adjusting),
        retrieving camera images
        calculate parameters
        """

        if self.btn_Logging.isChecked() and self.blog == 0:
            self.blog = 1
            if self.status == "StandBy" or self.status == "Error":
                self.status = "Observing"
                self.btn_Start.setText("Stop Logging")
            self.log = Logging()

        if not self.btn_Logging.isChecked() and self.blog ==1:
            self.blog = 0
            self.log.closeFile()
            if self.status == "Observing":
                self.status = "StandBy"
                self.btn_Start.setText("Start Logging")
            self.log = None

        self.updateCamera()
        self.updateAbsCenter()
        if self.log:
            self.log.saveValues()
        QtGui.QApplication.processEvents()
        try:
            self.calculateBeamProportion()
            self.checkStatus()
            self.updateThresholds()
        except KeyError:
            pass

        if self.b_align:
            self.correct.checkBoundaries()
            self.moveMirrors()

    def cutToROI(self, mirror, image):
        """
        if image has too much background light distracting from the main 
        beam, this can be cut away. ROI is defined as region around center 
        """

        if mirror == 0:
            ROI_percent = float(self.line_ROIPercentage0.text())
        else:
            ROI_percent = float(self.line_ROIPercentage1.text())

        cutImage = self.correct.cutImageToRoi(ROI_percent, image, mirror)
        return cutImage

    def updateCamera(self):
        """
        retrieve image for each camera, calculate parameters,
        if error occurs (an image was not send or grabbed correctly via 
        network): restart camera communication
        Order of cameras is defined by order in config file
        line : img[i] = img[i][::-1, ::-1] turns image, this is necessary depending 
        on how the camera is mounted
        """

        for i in range(CamsToUse):
            try:
                img, nbCam = self.cam.getImage()
                self.correct.totalImageSum(nbCam[i], img[i])
                if nbCam[i] == 0:
                    img[i] = img[i][::-1, ::-1]
                    if self.check_ROICalc0.isChecked():
                        img[i] = self.cutToROI(nbCam[i], img[i])
                elif nbCam[i] == 1:
                    img[i] = img[i][:, ::-1]
                    if self.check_ROICalc1.isChecked():
                        img[i] = self.cutToROI(nbCam[i], img[i])
                self.updatePlots(nbCam[i], img[i])
                self.updateCalculations(nbCam[i], img[i])
                self.displayThresholdlines(nbCam[i])
            except genicam._genicam.LogicalErrorException:
                QtGui.QApplication.processEvents()
                self.status = "Error"
                self.cam.close()
                self.initializeCams()
                pass

    def fitCenter(self):
        """
        define if the Centre of Mass (CoM) or centre of gaussfit is used 
        as centre reference for adjustment
        """

        if self.btn_FitValue.isChecked():
            return "gauss"
        else:
            return "CoM"


    def updateCalculations(self, mirror, image):
        """
        Calculate Parameters for adjustment
        """

        self.correct.calculateCenter(mirror, image)
        self.correct.updateMirrorDictionary(mirror, image)
        self.correct.getCoM(mirror)
        self.correct.getCurrentCenter(mirror, self.fitCenter)

        if self.newStart < 2:
            self.setPlotBoundaries()
            self.setGoalCenter(mirror)
            self.correct.setThresholdValues(mirror, self.thresholdPercentage)
        self.newStart = self.newStart+1

    def checkStatus(self):
        """
        Status Rectangle displaying the current state of the program:
            Adjusting: stabilization is active and deviations are corrected
            Observing: no corrections are made but the beam position is logged
            StandBy: Idle state
            Error: Camera image not grabbed correctly
        """

        if self.status == "Adjust":
            self.label.setStyleSheet('background: green; color: black')
            self.label.setText("Adjusting")
        elif self.status == "Observing":
            self.label.setStyleSheet('background: yellow; color: black')
            self.label.setText("Observing")
        elif self.status == "Error":
            self.label.setStyleSheet('background: red; color: black')
            self.label.setText("Error")
        elif self.status == "StandBy":
            self.label.setStyleSheet('background: none; color: white')
            self.label.setText("StandBy")

    def calculateBeamProportion(self):
        """
        Calculate the beam parameters shown on the GUI
            FWHMs: corrected to represent the real world dimensions
            Ratio: between x and y dimensions, describing the roundness of the beam profile
        """

        try:
            ratio1 = Mirror_Calculations[0]["FWHM_X"]/Mirror_Calculations[0]["FWHM_Y"]
        except ZeroDivisionError:
            ratio1 = 0
        try:
            ratio2 = Mirror_Calculations[1]["FWHM_X"] / Mirror_Calculations[1]["FWHM_Y"]
        except ZeroDivisionError:
            ratio2 = 0

        self.ui.label_0ratio.setText(str(round(ratio1, 2)))
        self.ui.label_0fwhmx.setText(str(round((Mirror_Calculations[0]["FWHM_X"]*conversionFactor), 1))+' mm (' + str(int(Mirror_Calculations[0]["FWHM_X"]))+' px)')
        self.ui.label_0fwhmy.setText(str(round((Mirror_Calculations[0]["FWHM_Y"]*conversionFactor), 1))+' mm (' + str(int(Mirror_Calculations[0]["FWHM_Y"]))+' px)')

        self.ui.label_1ratio.setText(str(round(ratio2, 2)))
        self.ui.label_1fwhmx.setText(str(round((Mirror_Calculations[1]["FWHM_X"]*conversionFactor), 1))+' mm (' + str(int(Mirror_Calculations[1]["FWHM_X"]))+' px)')
        self.ui.label_1fwhmy.setText(str(round((Mirror_Calculations[1]["FWHM_Y"]*conversionFactor), 1))+' mm (' + str(int(Mirror_Calculations[1]["FWHM_Y"]))+' px)')

    def closeEvent(self, event):
        """ 
        Function for exiting the application
        - GUI settings are stored
        - open files are closed
        """

        reply = QMessageBox.question(self, 'Message',
                                     "Are you sure to quit?", QMessageBox.Yes,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.timer.stop()
            if self.log:
                self.log.closeFile()
            self.Setting.guisave(self.ui, QtCore.QSettings('./GUI/saved.ini', QtCore.QSettings.IniFormat))
            sys.exit()
            event.accept()
        else:
            event.ignore()

    def setGoalCenter(self, mirror):
        """
        Set a reference center value
        """

        if not self.Save:
            self.Save = saveClass()

        if not self.Save.readLastConfig():
            Mirror_Calculations[mirror]["GoalPixel_X"] = float(Mirror_Calculations[mirror]["GoalCenter_X"])
            Mirror_Calculations[mirror]["GoalPixel_Y"] = float(Mirror_Calculations[mirror]["GoalCenter_Y"])

    def setPlotBoundaries(self):
        """
        Set the plot boundaries to the total range of the image
        """

        for i in range(CamsToUse):
            try:
                self.PlotY[i].setYRange(0, len(Mirror_Calculations[i]["SumY"]))
                self.PlotX[i].setXRange(0, len(Mirror_Calculations[i]["SumX"]))
            except KeyError:
                pass

    def setupPlots(self):
        """
        Setup plots with the lines displaying center and thresholds for each camera
        """

        lut = self.createColormap()

        self.integrationY = []
        self.integrationX = []
        self.gaussFitX = []
        self.gaussFitY = []
        self.plot_XCenter =[]
        self.plot_YCenter = []
        self.plot_XThresholdPlus = []
        self.plot_XThresholdMinus = []
        self.plot_YThresholdPlus = []
        self.plot_YThresholdMinus = []

        for i in range(CamsToUse):
            self.integrationX.append(self.PlotY[i].plot(pen=(215, 128, 26)))
            self.integrationY.append(self.PlotX[i].plot(pen=(215, 128, 26)))
            self.gaussFitX.append(self.PlotX[i].plot(pen=(255, 0, 0)))
            self.gaussFitY.append(self.PlotY[i].plot(pen=(255, 0, 0)))
            self.plot_XCenter.append(self.PlotX[i].addLine(x=0, movable=True, pen=(215, 0, 26)))
            self.plot_YCenter.append(self.PlotY[i].addLine(y=0, movable=True, pen=(215, 0, 26)))
            self.plot_XThresholdPlus.append(self.PlotX[i].addLine(x=0, movable=True))
            self.plot_XThresholdMinus.append(self.PlotX[i].addLine(x=0, movable=True))
            self.plot_YThresholdPlus.append(self.PlotY[i].addLine(y=0, movable=True))
            self.plot_YThresholdMinus.append(self.PlotY[i].addLine(y=0, movable=True))

            self.Image[i].setLookupTable(lut)


    def createColormap(self):
        """
        Generate a pyqtgraph colormap from a matplotlib name
        """

        colormap = cm.get_cmap(imgColormap)  # cm.get_cmap("CMRmap")
        colormap._init()
        lut = (colormap._lut * 255).view(np.ndarray)  # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
        return lut

    def updatePlots(self, mirror, img):
        """
        Set data for each plot
        """

        try:
            self.Image[mirror].setImage(img)
            self.integrationX[mirror].setData(x=Mirror_Calculations[mirror]["SumY"],
                                y=np.arange(len(Mirror_Calculations[mirror]["SumY"])))
            self.integrationY[mirror].setData(Mirror_Calculations[mirror]["SumX"])
            self.gaussFitY[mirror].setData(x=Mirror_Calculations[mirror]["GaussY"],
                                y=np.arange(len(Mirror_Calculations[mirror]["GaussY"])))
            self.gaussFitX[mirror].setData(Mirror_Calculations[mirror]["GaussX"])

            self.plot_XCenter[mirror].setValue(Mirror_Calculations[mirror]["CurrentCenter_X"])
            self.plot_YCenter[mirror].setValue(Mirror_Calculations[mirror]["CurrentCenter_Y"])

            self.plot_XThresholdPlus[mirror].setValue(Mirror_Calculations[mirror]["ThresholdPlus_X"])
            self.plot_XThresholdMinus[mirror].setValue(Mirror_Calculations[mirror]["ThresholdMinus_X"])
            self.plot_YThresholdPlus[mirror].setValue(Mirror_Calculations[mirror]["ThresholdPlus_Y"])
            self.plot_YThresholdMinus[mirror].setValue(Mirror_Calculations[mirror]["ThresholdMinus_Y"])
        except (KeyError, ValueError) as e:
            print('error: ',e)

    def mirrorInit(self):
        """
        Initialize Mirror Motors. The setpwidth (second parameter) has to be tested in order to see, 
        if the amplitude is large enough for the weigth of the mirror to acutally move
        """

        if self.mirror == None:
            self.mirror = MirrorCom(1)
            self.mirror.setSettings(1, 30)
            self.mirror.setSettings(2, 50)

    def moveMirrors(self):
        """
        Move mirrors depending on the calculation results.
        Algorithm of correction:
            - first miirror/cam: closer to laser source
            - if a calculated center moves outside of the defined threshold: start correcting 
            - first mirror is moved independently from second
            - if the second mirror is moved, but the first one moves outside of a defined outside threshold,
              move it back first (otherwise it could result in the laser not hitting CCD anymore) 
            - when a correction was triggered: the reference point is the goal (not only inside threshold)
        """

        self.mirrorInit()
        self.correct.checkBoundaries()
        QtGui.QApplication.processEvents()

        if not MirrorStatus[0]["bMoveX"] and MirrorStatus[1]["bMoveX"]:
            while MirrorStatus[0]["bInsideX"] and not MirrorStatus[1]["bCenterX"]:
                self.correct.checkBoundaries()
                self.updateCamera()
                self.updateThresholds()
                QtGui.QApplication.processEvents()
                if self.correct.goalOffset(1, "CurrentCenter_X", "GoalPixel_X") < 0:
                    self.mirror.move(2, 1, 1)
                else:
                    self.mirror.move(2, 1, -1)

        if not MirrorStatus[0]["bMoveY"] and MirrorStatus[1]["bMoveY"]:
            while MirrorStatus[0]["bInsideY"] and not MirrorStatus[1]["bCenterY"]:
                self.correct.checkBoundaries()
                self.updateCamera()
                self.updateThresholds()
                QtGui.QApplication.processEvents()
                if self.correct.goalOffset(1, "CurrentCenter_Y", "GoalPixel_Y") < 0:
                    self.mirror.move(2, 2, 2)
                else:
                    self.mirror.move(2, 2, -2)

        if MirrorStatus[0]["bMoveX"]:
            while not MirrorStatus[0]["bCenterX"]:
                self.correct.checkBoundaries()
                self.updateCamera()
                self.updateThresholds()
                QtGui.QApplication.processEvents()
                if self.correct.goalOffset(0, "CurrentCenter_X", "GoalPixel_X") < 0:
                    self.mirror.move(1, 1, -1)
                else:
                    self.mirror.move(1, 1, 1)
        
        if MirrorStatus[0]["bMoveY"]:
            while not MirrorStatus[0]["bCenterY"]:
                self.correct.checkBoundaries()
                self.updateCamera()
                self.updateThresholds()
                QtGui.QApplication.processEvents()
                if self.correct.goalOffset(0, "CurrentCenter_Y", "GoalPixel_Y") < 0:
                    self.mirror.move(1, 2, -1)
                else:
                    self.mirror.move(1, 2, 1)

    def updateThresholds(self):
        """
        Update the position of the threshold lines
        """

        for i in range(CamsToUse):
            try:
                self.xCenter[i].setPos(Mirror_Calculations[i]["CurrentCenter_X"])
                self.yCenter[i].setPos(Mirror_Calculations[i]["CurrentCenter_Y"])

                self.xThresholdLinePlus[i].setPos(Mirror_Calculations[i]["ThresholdPlus_X"])
                self.xThresholdLineMinus[i].setPos(Mirror_Calculations[i]["ThresholdMinus_X"])
                self.yThresholdLineMinus[i].setPos(Mirror_Calculations[i]["ThresholdMinus_Y"])
                self.yThresholdLinePlus[i].setPos(Mirror_Calculations[i]["ThresholdPlus_Y"])

            except KeyError:
                pass

    def updateAbsCenter(self):
        """
        Update Position of center line
        """

        for i in range(CamsToUse):
            try:
                self.xCenterAbs[i].setPos(Mirror_Calculations[i]["Center_X"])
                self.yCenterAbs[i].setPos(Mirror_Calculations[i]["Center_Y"])
            except KeyError:
                pass


class Correction:
    """
    Class handeling the caluclations for the mirror and laser parameters
    """

    def goalOffset(self, i, coordinate, variable):
        """
        Determination of the offset from center
        """
        return Mirror_Calculations[i][coordinate]-Mirror_Calculations[i][variable]

    def checkBoundaries(self):
        """
        Sets boolean Dictionary values determining if mirror has to be moved or not
        """

        for i in range(CamsToUse):
            yOffset = self.goalOffset(i, "CurrentCenter_Y", "GoalPixel_Y")
            xOffset = self.goalOffset(i, "CurrentCenter_X", "GoalPixel_X")

            # true if center was reached
            if abs(Mirror_Calculations[i]["CenterThreshold_Y"]) < abs(yOffset):
                MirrorStatus[i]["bCenterY"] = False
            else:
                MirrorStatus[i]["bCenterY"] = True

            if abs(Mirror_Calculations[i]["CenterThreshold_X"]) < abs(xOffset):
                MirrorStatus[i]["bCenterX"] = False
            else:
                MirrorStatus[i]["bCenterX"] = True

            # true if inside outer threshold range
            if abs(Mirror_Calculations[i]["OuterThreshold_Y"]) > abs(yOffset):
                MirrorStatus[i]["bInsideY"] = True
            else:
                MirrorStatus[i]["bInsideY"] = False

            if abs(Mirror_Calculations[i]["OuterThreshold_X"]) > abs(xOffset):
                MirrorStatus[i]["bInsideX"] = True
            else:
                MirrorStatus[i]["bInsideX"] = False

            # true if outside normal threshold
            if abs(Mirror_Calculations[i]["Threshold_Y"]) < abs(yOffset):
                MirrorStatus[i]["bMoveY"] = True
            else:
                MirrorStatus[i]["bMoveY"] = False

            if abs(Mirror_Calculations[i]["Threshold_X"]) < abs(xOffset):
                MirrorStatus[i]["bMoveX"] = True
            else:
                MirrorStatus[i]["bMoveX"] = False

    def setThresholdValues(self, mirror, percent):
        """
        Calculates the threshold values:
            - CenterThreshold: if correction takes place, this is the value the center has to reach to be succesfull corrected
            - OuterThreshold: the first mirror should not move the laser beam off the CCD camera during adjustment
            - Threshold: if this is crossed by the beam center, a correction is necessary
        """

        try:
            Mirror_Calculations[mirror]["Threshold_X"] = 0.01 * percent * Mirror_Calculations[mirror]["CurrentCenter_X"]
            Mirror_Calculations[mirror]["Threshold_Y"] = 0.01 * percent * Mirror_Calculations[mirror]["CurrentCenter_Y"]

            Mirror_Calculations[mirror]["CenterThreshold_X"] = 0.005 * Mirror_Calculations[mirror]["CurrentCenter_X"]
            Mirror_Calculations[mirror]["CenterThreshold_Y"] = 0.005 * Mirror_Calculations[mirror]["CurrentCenter_Y"]

            if (3 * Mirror_Calculations[mirror]["Threshold_X"]) < (0.25 * Mirror_Calculations[mirror]["CurrentCenter_X"]):
                Mirror_Calculations[mirror]["OuterThreshold_X"] = 3 * Mirror_Calculations[mirror]["Threshold_X"]
            else:
                Mirror_Calculations[mirror]["OuterThreshold_X"] = 0.25 * Mirror_Calculations[mirror]["CurrentCenter_X"]

            if (3 * Mirror_Calculations[mirror]["Threshold_Y"]) < (0.25 * Mirror_Calculations[mirror]["CurrentCenter_Y"]):
                Mirror_Calculations[mirror]["OuterThreshold_Y"] = 3 * Mirror_Calculations[mirror]["Threshold_Y"]
            else:
                Mirror_Calculations[mirror]["OuterThreshold_Y"] = 0.25 * Mirror_Calculations[mirror]["CurrentCenter_Y"]

            Mirror_Calculations[mirror]["ThresholdPlus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] + Mirror_Calculations[mirror]["Threshold_Y"]
            Mirror_Calculations[mirror]["ThresholdMinus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] - Mirror_Calculations[mirror]["Threshold_Y"]
            Mirror_Calculations[mirror]["ThresholdPlus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] + Mirror_Calculations[mirror]["Threshold_X"]
            Mirror_Calculations[mirror]["ThresholdMinus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] - Mirror_Calculations[mirror]["Threshold_X"]

            Mirror_Calculations[mirror]["OuterThresholdPlus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] + Mirror_Calculations[mirror]["Threshold_Y"]
            Mirror_Calculations[mirror]["OuterThresholdMinus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] - Mirror_Calculations[mirror]["Threshold_Y"]
            Mirror_Calculations[mirror]["OuterThresholdPlus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] + Mirror_Calculations[mirror]["Threshold_X"]
            Mirror_Calculations[mirror]["OuterThresholdMinus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] - Mirror_Calculations[mirror]["Threshold_X"]

            Mirror_Calculations[mirror]["CenterThresholdPlus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] + Mirror_Calculations[mirror]["CenterThreshold_Y"]
            Mirror_Calculations[mirror]["CenterThresholdMinus_Y"] = Mirror_Calculations[mirror]["GoalPixel_Y"] - Mirror_Calculations[mirror]["CenterThreshold_Y"]
            Mirror_Calculations[mirror]["CenterThresholdPlus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] + Mirror_Calculations[mirror]["CenterThreshold_X"]
            Mirror_Calculations[mirror]["CenterThresholdMinus_X"] = Mirror_Calculations[mirror]["GoalPixel_X"] - Mirror_Calculations[mirror]["CenterThreshold_X"]

        except KeyError:
            pass

    def totalImageSum(self, mirror, img):
        """
        Total center and integration of the image. Independent of ROI calculations
        """

        Mirror_Calculations[mirror]["TotalSumY"] = np.sum(img, axis=0)
        Mirror_Calculations[mirror]["TotalSumX"] = np.sum(img, axis=1)
        Mirror_Calculations[mirror]["TotalCenter_X"] = len(Mirror_Calculations[mirror]["TotalSumX"]) / 2
        Mirror_Calculations[mirror]["TotalCenter_Y"] = len(Mirror_Calculations[mirror]["TotalSumY"]) / 2

    def cutImageToRoi(self, ROI_percent, image, mirror):
        """
        ROI cutting of the image. A new array is created and the values outside of the defined ROI are set too zero
        """

        indexX = int(len(Mirror_Calculations[mirror]["TotalSumX"]) * ROI_percent * 0.01)
        indexY = int(len(Mirror_Calculations[mirror]["TotalSumY"]) * ROI_percent * 0.01)

        minX = int(len(Mirror_Calculations[mirror]["TotalSumX"]) / 2 - indexX)
        maxX = int(len(Mirror_Calculations[mirror]["TotalSumX"]) / 2 + indexX)

        minY = int(len(Mirror_Calculations[mirror]["TotalSumY"]) / 2 - indexY)
        maxY = int(len(Mirror_Calculations[mirror]["TotalSumY"]) / 2 + indexY)

        cutImage = np.copy(image)
        cutImage[:, :] = 0
        cutImage[minX:maxX, minY:maxY] = image[minX:maxX, minY:maxY]
        return cutImage

    def updateMirrorDictionary(self, mirror, img):
        """
        MAIN Image calculations.
        """

        Mirror_Calculations[mirror]["Image"] = img

        xgauss, ygauss = self.gaussFit(mirror)

        # int will be returned if fit is not successful
        if type(xgauss) != int:
            Mirror_Calculations[mirror]["FWHM_X"] = abs(xgauss[2] * 2.354)
            Mirror_Calculations[mirror]["Center_GaussFitX"] = xgauss[1]

        if type(ygauss) != int:
            Mirror_Calculations[mirror]["Center_GaussFitY"] = ygauss[1]
            Mirror_Calculations[mirror]["FWHM_Y"] = abs(ygauss[2] * 2.354)

    def gaussFit(self, mirror):
        """
        Give integrated image data to Gauss Fit function.
        """

        ygauss = self.fitGauss(Mirror_Calculations[mirror]["SumY"], [10000, 0.001, 200])
        xgauss = self.fitGauss(Mirror_Calculations[mirror]["SumX"], [10000, 0.001, 200])

        if not type(ygauss) is int or type(xgauss) is int:
            Mirror_Calculations[mirror]["GaussX"] = self.gauss(np.linspace(0,
                                                                          len(Mirror_Calculations[mirror]["SumX"]),
                                                                          len(Mirror_Calculations[mirror]["SumX"])),
                                                              xgauss[0], xgauss[1], xgauss[2])
            Mirror_Calculations[mirror]["GaussY"] = self.gauss(np.linspace(0,
                                                                          len(Mirror_Calculations[mirror]["SumY"]),
                                                                          len(Mirror_Calculations[mirror]["SumY"])),
                                                              ygauss[0], ygauss[1], ygauss[2])
            Mirror_Calculations[mirror]['Fit'] = True
        else:
            Mirror_Calculations[mirror]['Fit'] = False
        return xgauss, ygauss

    def gauss(self, x, a, x0, sigma):
        """
        FitFunction
        #TODO: implement offset fit
        """
        return a * np.exp(-(x - x0) ** 2 / (2 * sigma ** 2))

    def fitGauss(self, data, init):
        """
        Gauss Fitting, 0 is returned if fit is not successfull
        """

        result = False
        i = 0
        while result == False and i < 5:
            try:
                i = i + 1
                popt, pcov = curve_fit(self.gauss, np.linspace(0, len(data),
                                                              len(data)), data, p0=init)
                result = True
            except:
                TypeError
        if result == True:
            return popt
        else:
            return 0

    def calculateCenter(self, mirror, img):
        """
        Calculate Center of Image data
        """

        Mirror_Calculations[mirror]["SumY"] = np.sum(img, axis=0)
        Mirror_Calculations[mirror]["SumX"] = np.sum(img, axis=1)
        Mirror_Calculations[mirror]["Center_X"] = len(Mirror_Calculations[mirror]["SumX"]) / 2
        Mirror_Calculations[mirror]["Center_Y"] = len(Mirror_Calculations[mirror]["SumY"]) / 2

    def getCoM(self, mirror):
        """
        Calculate the Center of mass
        """

        sum = 0
        for i, val in enumerate(Mirror_Calculations[mirror]["SumX"]):
            sum = sum + val * i
        Mirror_Calculations[mirror]["CoM_X"] = sum / np.sum(Mirror_Calculations[mirror]["SumX"])
        sum = 0
        for i, val in enumerate(Mirror_Calculations[mirror]["SumY"]):
            sum = sum + val * i
        Mirror_Calculations[mirror]["CoM_Y"] = sum / np.sum(Mirror_Calculations[mirror]["SumY"])

    def getCurrentCenter(self, mirror, variable):
        """
        change center based on the chosen variable
        """

        try:
            if variable == 'Gauss':
                Mirror_Calculations[mirror]["CurrentCenter_X"] = Mirror_Calculations[
                    mirror]["Center_GaussFitX"]
                Mirror_Calculations[mirror]["CurrentCenter_Y"] = Mirror_Calculations[
                    mirror]["Center_GaussFitY"]
            else:
                Mirror_Calculations[mirror]["CurrentCenter_X"] = Mirror_Calculations[
                    mirror]["CoM_X"]
                Mirror_Calculations[mirror]["CurrentCenter_Y"] = Mirror_Calculations[
                    mirror]["CoM_Y"]
        except KeyError:
            pass

class saveClass():
    """
    Class for writing and reading the reference values from the position logging file
    (ConfigFileName)

    Methods:
        createOrOpenConfigFile
        readLastConfig
        writeNewCenter
    """

    fn = "BeamStabilization\\"+str(ConfigFileName)

    def createOrOpenConfigFile(self):
        """
        Get the file object with previous reference positions.
        Create it, if it does not exist (size == 0), write header in new file
        :return: file object
        """

        header = False
        file = open(self.fn, 'a+')
        if os.stat(self.fn).st_size == 0:
            header = True
        if header:
            file.write('#Cam0 X\t Cam0 Y\t Cam1 X\t Cam1 Y\n')
        return file

    def readLastConfig(self, line=-1):
        """
        Open the file object and read the last entry (default) or the specified line
        :param line: reference position
        :return: bool, if it was succesfull
        """

        open(self.fn, 'a+')
        if os.stat(self.fn).st_size != 0:
            try:
                with open(self.fn, 'r') as file:
                    lines = file.read().splitlines()
                    last_line = lines[line]
                Mirror_Calculations[0]["GoalPixel_X"] = float(last_line.split('\t')[0])
                Mirror_Calculations[0]["GoalPixel_Y"] = float(last_line.split('\t')[1])
                Mirror_Calculations[1]["GoalPixel_X"] = float(last_line.split('\t')[2])
                Mirror_Calculations[1]["GoalPixel_Y"] = float(last_line.split('\t')[3])
                return True
            except FileNotFoundError:
                return False

    def writeNewCenter(self):
        """
        write the new reference position to the position reference file.
        """

        file = self.createOrOpenConfigFile()
        file.write(str(Mirror_Calculations[0]["Center_GaussFitX"])+'\t')
        file.write(str(Mirror_Calculations[0]["Center_GaussFitY"])+'\t')
        file.write(str(Mirror_Calculations[1]["Center_GaussFitX"])+'\t')
        file.write(str(Mirror_Calculations[1]["Center_GaussFitY"])+'\t')
        file.write('\n')
        file.close()


class Logging:
    """
    Class handeling the continuous logging of the beam position

    Methods:
        init
        createFolderAndFile
        saveValues
        closeFile
    """

    def __init__(self):
        self.createFolderAndFile()

    def createFolderAndFile(self):
        """
        Get the file object with previous reference positions.
        Create it, if it does not exist (size == 0), write header in new file
        :return: file object
        """

        if not os.path.exists(SavingDestination+"\\Logging"):
            os.makedirs(SavingDestination+"\\Logging")
        os.chdir(SavingDestination+"\\Logging")
        self.timeStamp = str(datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.file = open(str(self.timeStamp), 'a+')

        self.file.write('# timeStamp\t FWHMX1\t FWHMY1\t FWHMX2\t '
                        'FWHMY2\t CoM_X1\t CoM_X2\t '
                        'CoM_Y1\tCoM_Y2\tGausscenterX1\t '
                        'GausscenterX2\t '
                   'GausscenterY1\t GausscenterY2\n')

    def saveValues(self):
        """
        write line to logging file from the global dictionaries for both cameras:
            time
            FWHM_X, FWHM_Y
            CoM_X, CoM_Y
            Center_GaussFitX, Center_GaussFitY
        """
        self.file.write(str(datetime.now().strftime("%Y%m%d_%H%M%S")) + '\t')

        self.file.write(str(Mirror_Calculations[0]["FWHM_X"])+'\t')
        self.file.write(str(Mirror_Calculations[0]["FWHM_Y"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["FWHM_X"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["FWHM_Y"]) + '\t')

        self.file.write(str(Mirror_Calculations[0]["CoM_X"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["CoM_X"]) + '\t')
        self.file.write(str(Mirror_Calculations[0]["CoM_Y"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["CoM_Y"]) + '\t')

        self.file.write(str(Mirror_Calculations[0]["Center_GaussFitX"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["Center_GaussFitX"]) + '\t')
        self.file.write(str(Mirror_Calculations[0]["Center_GaussFitY"]) + '\t')
        self.file.write(str(Mirror_Calculations[1]["Center_GaussFitY"]) + '\n')

    def closeFile(self):
        """
        close file object at the end of logging
        """

        self.file.close()


def main():

    app = QApplication(sys.argv)
    MyWindow()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
