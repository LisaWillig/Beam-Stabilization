import numpy as np
import pyqtgraph as pg
import sys
from PyQt5 import uic
import PyQt5
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from pyqtgraph.Qt import QtGui, QtCore
from matplotlib import cm
from scipy.optimize import curve_fit
from pypylon import genicam
import config
import logging, traceback
from colorama import Style, Fore

# Import own modules
from modules.MirrorCommunication import MirrorCom
from modules.BaslerCommunication import BaslerCam as Basler
from modules.saveGUISettings import GUISettings
from modules.utilities import saveClass, Logging

calcDict = dict()
MirrorStatus = dict()

for i in range(config.CamsToUse):
    calcDict[i] = {}
    MirrorStatus[i] = {}


class MyWindow(PyQt5.QtWidgets.QMainWindow):
    """
    Msin Class handeling presentation and data analysis
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    # ~~~ a) Init ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

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
        self.Save = saveClass(config)
        if self.Save.readLastConfig(calcDict):
            self.config = True

        self.correct = Correction()

        # Initialize GUI plots and images

        self.init_ui()
        self.Setting = GUISettings()
        self.Setting.guirestore(self.ui, QtCore.QSettings(
            './GUI/saved.ini', QtCore.QSettings.IniFormat))

        # Connect Buttons with Function calls
        self.readLastReferencePosition()
        self.btn_Exit.clicked.connect(self.close)
        self.btn_Start.clicked.connect(self.startAligning)
        self.btn_setCenter.clicked.connect(self.newCenter)
        self.btn_showCenter.clicked.connect(self.displayCenterLine)
        self.line_thresholdPercentage.returnPressed.connect(
            self.getThresholdPercentage)
        self.btn_moveMirror.clicked.connect(self.moveSingleMirror)
        self.btn_FitValue.toggled.connect(self.fitCenter)

        # show GUI
        self.show()

        # start Main function
        self.Main()

    def moveSingleMirror(self):
        """
        Move an attached Newport mirror with the values from the Interface
        """

        self.mirrorInit()
        self.mirror.move(int(self.line_mirror.text()),
                         int(self.line_axis.text()),
                         int(self.line_step.text()))

    def displayCenterLine(self):
        """
        Display or remove the center lines of the image,
        so the absolute center of the CCD
        """

        if self.b_centerLine == 0:
            for i in range(config.CamsToUse):
               self.vb[i].removeItem(self.xCenterAbs[i])
               self.vb[i].removeItem(self.yCenterAbs[i])
            self.b_centerLine = 1
        else:
            for i in range(config.CamsToUse):
                self.vb[i].addItem(self.xCenterAbs[i])
                self.vb[i].addItem(self.yCenterAbs[i])
            self.b_centerLine = 0

    def resetStatus(self):
        """
        Check status after an error was detected and removed
        """

        if self.b_align:
            self.status = "Adjust"
        elif self.btn_Logging.isChecked():
            self.status = "Observing"
        else:
            self.status = "StandBy"
        self.checkStatus()

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

        Save = saveClass(config)
        self.config = Save.readLastConfig(calcDict)

    def newCenter(self):
        """
        write current center as reference too file and dictionary
        """

        self.Save = saveClass(config)
        self.Save.writeNewCenter(calcDict)

        for i in range(2):
            self.setCenterValue(i)

    def setCenterValue(self, mir):
        """
        Set the current center of the gaussfit as center for each mirror
        :param mir:
        """

        if self.btn_FitValue.isChecked():
            calcDict[mir]["GoalPixel_X"] = calcDict[mir]["Center_GaussFitX"]
            calcDict[mir]["GoalPixel_Y"] = calcDict[mir]["Center_GaussFitY"]
        else:
            calcDict[mir]["GoalPixel_X"] = calcDict[mir]["CoM_X"]
            calcDict[mir]["GoalPixel_Y"] = calcDict[mir]["CoM_Y"]
        self.correct.setThresholdValues(mir, self.thresholdPercent)

    def init_ui(self):
        """
        Initialize Plots and Images of the UI.
        The Main CCD image displays the current center of
        gaussfit (red) and the threshold values for adjustement of x and y (yellow) for both
        dimensions.
        Two plots at the side of the image display the vertical and horizontal integration
        """

        self.vb = []
        self.Image = []
        self.xCenter = []
        self.yCenter = []
        self.xCenterAbs = []
        self.yCenterAbs = []
        self.xThresLinePlus = []
        self.yThresLinePlus= []
        self.xThresLineMinus = []
        self.yThresLineMinus = []

        # Plots
        self.PlotY = []
        self.PlotX = []

        # Left Image
        leftImage = self.ImageBox.addViewBox(row=0, col=0)
        leftPlotX = self.ImageBox.addPlot(row=1, col=0)
        leftPlotY = self.ImageBox.addPlot(row=0, col=1)

        self.vb.append(leftImage)
        self.PlotX.append(leftPlotX)
        self.PlotY.append(leftPlotY)

        rightImage = self.ImageBox2.addViewBox(row=0, col=0)
        rightPlotX = self.ImageBox2.addPlot(row=1, col=0)
        rightPlotY = self.ImageBox2.addPlot(row=0, col=1)

        self.vb.append(rightImage)
        self.PlotX.append(rightPlotX)
        self.PlotY.append(rightPlotY)

        # create Images and plots
        for i in range(config.CamsToUse):
            self.vb[i].setAspectLocked(True)
            self.Image.append(pg.ImageItem())
            self.xCenter.append(pg.InfiniteLine(pen=(215, 0, 26), angle=90))
            self.yCenter.append(pg.InfiniteLine(pen=(215, 0, 26), angle=0))
            self.xCenterAbs.append(pg.InfiniteLine(pen=(0, 200, 26), angle=90))
            self.yCenterAbs.append(pg.InfiniteLine(pen=(0, 200, 26), angle=0))
            self.xThresLinePlus.append(pg.InfiniteLine())
            self.yThresLinePlus.append(pg.InfiniteLine(angle=0))
            self.xThresLineMinus.append(pg.InfiniteLine())
            self.yThresLineMinus.append(pg.InfiniteLine(angle=0))

        # Add Items to Viewbox
        for i in range(config.CamsToUse):
            self.vb[i].addItem(self.Image[i])
            self.vb[i].addItem(self.xCenter[i])
            self.vb[i].addItem(self.yCenter[i])
            self.vb[i].addItem(self.xThresLinePlus[i])
            self.vb[i].addItem(self.yThresLinePlus[i])
            self.vb[i].addItem(self.xThresLineMinus[i])
            self.vb[i].addItem(self.yThresLineMinus[i])

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
        """ get threshold value from GUI """
        self.thresholdPercent = float(self.ui.line_thresholdPercentage.text())
        for i in range(config.CamsToUse):
            self.correct.setThresholdValues(i, self.thresholdPercent)

    def Main(self):

        self.initCameraCommunication()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def initCameraCommunication(self):
        self.cam = Basler(config.namesCamsToUse)
        self.cam.openCommunications()
        self.cam.setCameraParameters(config.exposureTime)
        self.cam.startAcquisition()

    def update(self):

        if self.btn_Logging.isChecked() and self.blog == 0:
            self.blog = 1
            if self.status == "StandBy" or self.status == "Error":
                self.status = "Observing"
                self.btn_Start.setText("Stop Logging")
            self.log = Logging(config)

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
            self.log.saveValues(calcDict)
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

    def cutToROI(self, mir, image):
        """
        if checkbox is active to cut to ROI: get value and calculate new image
        """

        if mir == 0:
            ROI_percent = float(self.line_ROIPercentage0.text())
        else:
            ROI_percent = float(self.line_ROIPercentage1.text())

        cutImage = self.correct.cutImageToRoi(ROI_percent, image, mir)
        return cutImage

    def updateCamera(self):
        """
        MAIN CAMERA UPDATE
        Retrieve images
        """

        self.getThresholdPercentage()
        for i in range(config.CamsToUse):
            try:
                img, nbCam = self.cam.getImage()
                self.correct.totalImageSum(nbCam[i], img[i])
                if nbCam[i] == 0:
                    img[i] = img[i][::-1, ::-1] # change if camera is turned
                    if self.check_ROICalc0.isChecked():
                        img[i] = self.cutToROI(nbCam[i], img[i])
                elif nbCam[i] == 1:
                    img[i] = img[i][:, ::-1] # change if camera is turned
                    if self.check_ROICalc1.isChecked():
                        img[i] = self.cutToROI(nbCam[i], img[i])
                self.updatePlots(nbCam[i], img[i])
                self.updateCalculations(nbCam[i], img[i])
                if self.status == "Error":
                    print(f'{Fore.YELLOW}Reconnection '
                          f'Established{Style.RESET_ALL}')
                    self.getThresholdPercentage()
                    self.updateThresholds()
                    self.resetStatus()
            except genicam._genicam.LogicalErrorException:
                self.status = "Error"
                QtGui.QApplication.processEvents()
                print(f'{Fore.MAGENTA}Network Error: Camera Image was not '
                      f'transferred correctly. Attempt '
                      f'reconnection.{Style.RESET_ALL}')
                self.cam.close()
                self.initCameraCommunication()

            except genicam._genicam.RuntimeException:
                self.status = "Error"
                QtGui.QApplication.processEvents()
                print(f'{Fore.MAGENTA}Camera Removed Error: Camera cannot be detected anymore. Attempt '
                      f'reconnection.{Style.RESET_ALL}')
                self.initCameraCommunication()
                while len(self.cam.camList) < config.CamsToUse:
                    self.cam.close()
                    self.initCameraCommunication()


    def fitCenter(self):
        """
        Determine the fit center
        """

        if self.btn_FitValue.isChecked():
            return "gauss"
        else:
            return "CoM"

    def updateCalculations(self, mir, image):
        """
        Update the calculations after image was retrieved
        """

        self.correct.calculateCenter(mir, image)
        self.correct.updateMirrorDictionary(mir, image)
        self.correct.getCoM(mir)
        self.correct.getCurrentCenter(mir, self.fitCenter)

        if self.newStart < 2:
            self.setPlotBoundaries()
            self.setGoalCenter(mir)
            self.correct.setThresholdValues(mir, self.thresholdPercent)
        self.newStart = self.newStart+1

    def checkStatus(self):
        """
        Change label and indication rectangle if status was changed
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
        Write the calculated parameters to the labels in the GUI
        Calculate the ratio between x and y (the ellipticity of the beam)
        """

        try:
            ratio1 = calcDict[0]["FWHM_X"] / calcDict[0]["FWHM_Y"]
        except ZeroDivisionError:
            ratio1 = 0
        try:
            ratio2 = calcDict[1]["FWHM_X"] / calcDict[1]["FWHM_Y"]
        except ZeroDivisionError:
            ratio2 = 0

        self.ui.label_0ratio.setText(str(round(ratio1, 2)))
        self.ui.label_0fwhmx.setText(
            str(round((calcDict[0]["FWHM_X"] * config.conversionFactor), 1)) +
            ' mm (' + str(int(calcDict[0]["FWHM_X"])) + ' px)')
        self.ui.label_0fwhmy.setText(
            str(round((calcDict[0]["FWHM_Y"] * config.conversionFactor), 1)) +
            ' mm (' + str(int(calcDict[0]["FWHM_Y"])) + ' px)')

        self.ui.label_1ratio.setText(str(round(ratio2, 2)))
        self.ui.label_1fwhmx.setText(
            str(round((calcDict[1]["FWHM_X"] * config.conversionFactor), 1)) +
            ' mm (' + str(int(calcDict[1]["FWHM_X"])) + ' px)')
        self.ui.label_1fwhmy.setText(
            str(round((calcDict[1]["FWHM_Y"] * config.conversionFactor), 1)) +
            ' mm (' + str(int(calcDict[1]["FWHM_Y"])) + ' px)')

    def closeEvent(self, event):
        """
        Function executed at exiting the application:
            - stop the measurement timer
            - close the logFile if one was produced
            - save the state of the GUI entries
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
        if not self.Save:
            self.Save = saveClass()

        if not self.Save.readLastConfig(calcDict):
            calcDict[mirror]["GoalPixel_X"] = float(calcDict[mirror]["GoalCenter_X"])
            calcDict[mirror]["GoalPixel_Y"] = float(calcDict[mirror]["GoalCenter_Y"])

    def setPlotBoundaries(self):
        """
        Set plotrange equal to the size of the
        """

        for i in range(config.CamsToUse):
            try:
                self.PlotY[i].setYRange(0, len(calcDict[i]["SumY"]))
                self.PlotX[i].setXRange(0, len(calcDict[i]["SumX"]))
            except KeyError:
                pass

    def setupPlots(self):
        """
        Create Plots
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

        for i in range(config.CamsToUse):
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
        # Create from matplotilb colormap
        colormap = cm.get_cmap(config.imgColormap)
        colormap._init()
        # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
        lut = (colormap._lut * 255).view(np.ndarray)
        return lut

    def updatePlots(self, mir, img):
        """
        Update the data for all plots and image
        """

        try:
            self.Image[mir].setImage(img)
            self.integrationX[mir].setData(x=calcDict[mir]["SumY"],
                                           y=np.arange(len(calcDict[mir]["SumY"])))
            self.integrationY[mir].setData(calcDict[mir]["SumX"])
            self.gaussFitY[mir].setData(x=calcDict[mir]["GaussY"],
                                        y=np.arange(len(calcDict[mir]["GaussY"])))
            self.gaussFitX[mir].setData(calcDict[mir]["GaussX"])

            self.plot_XCenter[mir].setValue(calcDict[mir]["CurrentCenter_X"])
            self.plot_YCenter[mir].setValue(calcDict[mir]["CurrentCenter_Y"])

            self.plot_XThresholdPlus[mir].setValue(calcDict[mir]["ThresholdPlus_X"])
            self.plot_XThresholdMinus[mir].setValue(calcDict[mir]["ThresholdMinus_X"])
            self.plot_YThresholdPlus[mir].setValue(calcDict[mir]["ThresholdPlus_Y"])
            self.plot_YThresholdMinus[mir].setValue(calcDict[mir]["ThresholdMinus_Y"])
        except (KeyError, ValueError) as e:
            pass

    def mirrorInit(self):
        """
        Initialize the Mirror Class and set the stepsizes for the individual
        mirrors.
        A stepsize which is too small can lead to the mirror not moving.
        """
        if not self.mirror:
            self.mirror = MirrorCom(config)
            self.mirror.setSettings(1, 30)
            self.mirror.setSettings(2, 50)


    def moveMirrors(self):
        """
        Main Function determining which mirror moves in which direction.
        It consideres the order of the mirrors on the table to ensure
        convergence without moving the laserspots out of the CCD area.
        """

        # initialize mirror if it was not initialized before or disconnected
        self.mirrorInit()

        # calculate the laser parameters for movement
        self.correct.checkBoundaries()
        QtGui.QApplication.processEvents()

        # if the first mirror (from point of view of laser exiting the cavatiy)
        # does not need to be moved, but the second mirror is outside of the
        # threshold: move it until it is inside the center region

        # explanation of the while conditions:
        # while the first laser beam is not on the corners of the image
        # and the second laser beam is not inside the center region
        # and the alignment is requested
        # and a fit can be made (so a laser beam is visible on the image)

        if not MirrorStatus[0]["bMoveX"] and MirrorStatus[1]["bMoveX"]:
            while MirrorStatus[0]["bInsideX"] \
                    and not MirrorStatus[1]["bCenterX"] \
                    and self.status == "Adjust" \
                    and calcDict[1]['bFit']:
                self.updateForMirrorMove()
                if self.correct.goalOffset(1, "CurrentCenter_X", "GoalPixel_X") < 0:
                    self.mirror.move(2, 1, 1)
                else:
                    self.mirror.move(2, 1, -1)

        if not MirrorStatus[0]["bMoveY"] and MirrorStatus[1]["bMoveY"]:
            while MirrorStatus[0]["bInsideY"] \
                and not MirrorStatus[1]["bCenterY"] \
                and self.status == "Adjust" \
                and calcDict[1]['bFit']:
                self.updateForMirrorMove()
                if self.correct.goalOffset(1, "CurrentCenter_Y", "GoalPixel_Y") < 0:
                    self.mirror.move(2, 2, -1)
                else:
                    self.mirror.move(2, 2, 1)

        # move the first mirror as long as it is not in the center region
        # when outside of threshold and as l
        if MirrorStatus[0]["bMoveX"]:
            while not MirrorStatus[0]["bCenterX"] \
                    and self.status == "Adjust" \
                    and calcDict[0]['bFit']:
                self.updateForMirrorMove()
                if self.correct.goalOffset(0, "CurrentCenter_X", "GoalPixel_X") < 0:
                    self.mirror.move(1, 1, -1)
                else:
                    self.mirror.move(1, 1, 1)
        
        if MirrorStatus[0]["bMoveY"]:
            while not MirrorStatus[0]["bCenterY"] \
                    and self.status == "Adjust" \
                    and calcDict[0]['bFit']:
                self.updateForMirrorMove()
                if self.correct.goalOffset(0, "CurrentCenter_Y", "GoalPixel_Y") < 0:
                    self.mirror.move(1, 2, -1)
                else:
                    self.mirror.move(1, 2, 1)

    def updateForMirrorMove(self):
        """
        Update calculations and images after the mirror moved laser beam
        """

        self.correct.checkBoundaries()
        self.updateCamera()
        self.updateThresholds()
        QtGui.QApplication.processEvents()

    def updateThresholds(self):
        """
        Update the lines displaying center and thresholds for each mirror
        """

        for i in range(config.CamsToUse):
            try:
                self.xCenter[i].setPos(calcDict[i]["CurrentCenter_X"])
                self.yCenter[i].setPos(calcDict[i]["CurrentCenter_Y"])

                self.xThresLinePlus[i].setPos(calcDict[i]["ThresholdPlus_X"])
                self.xThresLineMinus[i].setPos(calcDict[i]["ThresholdMinus_X"])
                self.yThresLineMinus[i].setPos(calcDict[i]["ThresholdMinus_Y"])
                self.yThresLinePlus[i].setPos(calcDict[i]["ThresholdPlus_Y"])

            except KeyError:
                pass

    def updateAbsCenter(self):
        """
        Update the absolute center of the used CCD for each mirror
        """

        for i in range(config.CamsToUse):
            try:
                self.xCenterAbs[i].setPos(calcDict[i]["Center_X"])
                self.yCenterAbs[i].setPos(calcDict[i]["Center_Y"])
            except KeyError:
                pass


class Correction:
    """
    Class performing the majority of calculations with the obtained
    """

    def goalOffset(self, i, coordinate, variable):
        """ Calculate the offset from goal"""
        return calcDict[i][coordinate] - calcDict[i][variable]

    def checkBoundaries(self):
        """
        Determine the position of the laser beam in relation to given
        threshold values.
        The dictionary MirrorStatus determines the order of moving the mirrors
        """

        for i in range(config.CamsToUse):
            yOffset = self.goalOffset(i, "CurrentCenter_Y", "GoalPixel_Y")
            xOffset = self.goalOffset(i, "CurrentCenter_X", "GoalPixel_X")

            if calcDict[i]['bFit']:
                # true if center was reached
                if abs(calcDict[i]["CenterThreshold_Y"]) < abs(yOffset):
                    MirrorStatus[i]["bCenterY"] = False
                else:
                    MirrorStatus[i]["bCenterY"] = True

                if abs(calcDict[i]["CenterThreshold_X"]) < abs(xOffset):
                    MirrorStatus[i]["bCenterX"] = False
                else:
                    MirrorStatus[i]["bCenterX"] = True

                # true if inside outer threshold range
                if abs(calcDict[i]["OuterThreshold_Y"]) > abs(yOffset):
                    MirrorStatus[i]["bInsideY"] = True
                else:
                    MirrorStatus[i]["bInsideY"] = False

                if abs(calcDict[i]["OuterThreshold_X"]) > abs(xOffset):
                    MirrorStatus[i]["bInsideX"] = True
                else:
                    MirrorStatus[i]["bInsideX"] = False

                # true if outside normal threshold
                if abs(calcDict[i]["Threshold_Y"]) < abs(yOffset):
                    MirrorStatus[i]["bMoveY"] = True
                else:
                    MirrorStatus[i]["bMoveY"] = False

                if abs(calcDict[i]["Threshold_X"]) < abs(xOffset):
                    MirrorStatus[i]["bMoveX"] = True
                else:
                    MirrorStatus[i]["bMoveX"] = False
            else:
                # if no fit could be made, dont move
                MirrorStatus[i]["bMoveX"] = False
                MirrorStatus[i]["bMoveY"] = False
                break

    def setThresholdValues(self, mir, percent):
        """
        Calculate the position of the thresholds

        Center: 0.005
        Threshold for move: 0.01 * percent written in GUI
        Outer Threshold: 0.25 or 3*original threshold (depends on size of beam)
        """

        try:
            calcDict[mir]["Threshold_X"] = 0.01 * percent * calcDict[mir]["CurrentCenter_X"]
            calcDict[mir]["Threshold_Y"] = 0.01 * percent * calcDict[mir]["CurrentCenter_Y"]

            calcDict[mir]["CenterThreshold_X"] = 0.005 * calcDict[mir]["CurrentCenter_X"]
            calcDict[mir]["CenterThreshold_Y"] = 0.005 * calcDict[mir]["CurrentCenter_Y"]

            if (3 * calcDict[mir]["Threshold_X"]) < (0.25 * calcDict[mir]["CurrentCenter_X"]):
                calcDict[mir]["OuterThreshold_X"] = 3 * calcDict[mir]["Threshold_X"]
            else:
                calcDict[mir]["OuterThreshold_X"] = 0.25 * calcDict[mir]["CurrentCenter_X"]

            if (3 * calcDict[mir]["Threshold_Y"]) < (0.25 * calcDict[mir]["CurrentCenter_Y"]):
                calcDict[mir]["OuterThreshold_Y"] = 3 * calcDict[mir]["Threshold_Y"]
            else:
                calcDict[mir]["OuterThreshold_Y"] = 0.25 * calcDict[mir]["CurrentCenter_Y"]

            calcDict[mir]["ThresholdPlus_Y"] = calcDict[mir]["GoalPixel_Y"] + calcDict[mir]["Threshold_Y"]
            calcDict[mir]["ThresholdMinus_Y"] = calcDict[mir]["GoalPixel_Y"] - calcDict[mir]["Threshold_Y"]
            calcDict[mir]["ThresholdPlus_X"] = calcDict[mir]["GoalPixel_X"] + calcDict[mir]["Threshold_X"]
            calcDict[mir]["ThresholdMinus_X"] = calcDict[mir]["GoalPixel_X"] - calcDict[mir]["Threshold_X"]

            calcDict[mir]["OuterThresholdPlus_Y"] = calcDict[mir]["GoalPixel_Y"] + calcDict[mir]["Threshold_Y"]
            calcDict[mir]["OuterThresholdMinus_Y"] = calcDict[mir]["GoalPixel_Y"] - calcDict[mir]["Threshold_Y"]
            calcDict[mir]["OuterThresholdPlus_X"] = calcDict[mir]["GoalPixel_X"] + calcDict[mir]["Threshold_X"]
            calcDict[mir]["OuterThresholdMinus_X"] = calcDict[mir]["GoalPixel_X"] - calcDict[mir]["Threshold_X"]

            calcDict[mir]["CenterThresholdPlus_Y"] = calcDict[mir]["GoalPixel_Y"] + calcDict[mir]["CenterThreshold_Y"]
            calcDict[mir]["CenterThresholdMinus_Y"] = calcDict[mir]["GoalPixel_Y"] - calcDict[mir]["CenterThreshold_Y"]
            calcDict[mir]["CenterThresholdPlus_X"] = calcDict[mir]["GoalPixel_X"] + calcDict[mir]["CenterThreshold_X"]
            calcDict[mir]["CenterThresholdMinus_X"] = calcDict[mir]["GoalPixel_X"] - calcDict[mir]["CenterThreshold_X"]

        except KeyError:
            pass

    def totalImageSum(self, mir, img):
        """
        Calculate the absolute sum and center of image
        """
        calcDict[mir]["TotalSumY"] = np.sum(img, axis=0)
        calcDict[mir]["TotalSumX"] = np.sum(img, axis=1)
        calcDict[mir]["TotalCenter_X"] = len(calcDict[mir]["TotalSumX"]) / 2
        calcDict[mir]["TotalCenter_Y"] = len(calcDict[mir]["TotalSumY"]) / 2

    def cutImageToRoi(self, ROI_percent, img, mir):
        """
        Substitute all areas outside of ROI region with zeros
        """

        indexX = int(len(calcDict[mir]["TotalSumX"]) * ROI_percent * 0.01)
        indexY = int(len(calcDict[mir]["TotalSumY"]) * ROI_percent * 0.01)

        minX = int(len(calcDict[mir]["TotalSumX"]) / 2 - indexX)
        maxX = int(len(calcDict[mir]["TotalSumX"]) / 2 + indexX)

        minY = int(len(calcDict[mir]["TotalSumY"]) / 2 - indexY)
        maxY = int(len(calcDict[mir]["TotalSumY"]) / 2 + indexY)

        cutImage = np.copy(img)
        cutImage[:, :] = 0
        cutImage[minX:maxX, minY:maxY] = img[minX:maxX, minY:maxY]
        return cutImage

    def updateMirrorDictionary(self, mir, img):
        """
        Update the image in the data Dictionary with the newly aquired image.
        Perform Fitting.
        """

        calcDict[mir]["Image"] = img

        xgauss, ygauss = self.gaussFit(mir)

        if type(xgauss) != int:
            calcDict[mir]["FWHM_X"] = abs(xgauss[2] * 2.354)
            calcDict[mir]["Center_GaussFitX"] = xgauss[1]

        if type(ygauss) != int:
            calcDict[mir]["Center_GaussFitY"] = ygauss[1]
            calcDict[mir]["FWHM_Y"] = abs(ygauss[2] * 2.354)

    def gaussFit(self, mir):
        """
        Fit a gauss function to the integral of the image
        """

        calcDict[mir]['bFit'] = True
        ygauss = self.fitGauss(calcDict[mir]["SumY"], [10000, 0.001, 200])
        xgauss = self.fitGauss(calcDict[mir]["SumX"], [10000, 0.001, 200])

        # set the fitting and therefore the movement to false for all mirrors
        # when one fit does not deliver a result
        if type(ygauss) is int or type(xgauss) is int:
            calcDict[0]['bFit'] = False
            calcDict[1]['bFit'] = False

        if calcDict[mir]['bFit']:
            # create the data of the calculated gauss fit
            calcDict[mir]["GaussX"] = \
                self.gauss(np.linspace(0,
                                       len(calcDict[mir]["SumX"]),
                                       len(calcDict[mir]["SumX"])),
                           xgauss[0],
                           xgauss[1],
                           xgauss[2])

            calcDict[mir]["GaussY"] = \
                self.gauss(np.linspace(0,
                                       len(calcDict[mir]["SumY"]),
                                       len(calcDict[mir]["SumY"])),
                           ygauss[0],
                           ygauss[1],
                           ygauss[2])

        return xgauss, ygauss

    def gauss(self, x, a, x0, sigma):
        """ Used Gauss Function for fit"""
        return a * np.exp(-(x - x0) ** 2 / (2 * sigma ** 2))

    def fitGauss(self, data, init):
        """
        Fit Gauss to integrated image dimensions

        """
        result = False
        i = 0
        while not result and i < 5:
            try:
                i += 1
                popt, pcov = curve_fit(self.gauss,
                                       np.linspace(0, len(data), len(data)),
                                       data,
                                       p0=init)
                result = True
            except:
                pass
        # return the fit values if fit was successful
        # Return 0 if no fit could have been made
        if result:
            return popt
        else:
            return 0

    @staticmethod
    def calculateCenter(mir, img):
        """
        Calculate the center of the image in pixel
        """

        calcDict[mir]["SumY"] = np.sum(img, axis=0)
        calcDict[mir]["SumX"] = np.sum(img, axis=1)
        calcDict[mir]["Center_X"] = len(calcDict[mir]["SumX"]) / 2
        calcDict[mir]["Center_Y"] = len(calcDict[mir]["SumY"]) / 2

    @staticmethod
    def getCoM(mir):
        """
        Get the center of mass of the integrated images
        """
        sum = 0
        for i, val in enumerate(calcDict[mir]["SumX"]):
            sum = sum + val * i
        calcDict[mir]["CoM_X"] = sum / np.sum(calcDict[mir]["SumX"])
        sum = 0
        for i, val in enumerate(calcDict[mir]["SumY"]):
            sum = sum + val * i
        calcDict[mir]["CoM_Y"] = sum / np.sum(calcDict[mir]["SumY"])

    @staticmethod
    def getCurrentCenter(mir, var):
        """
        Get the current center of the fitted object,
        gaussfitcenter or center of mass
        """

        try:
            if var == 'Gauss':
                calcDict[mir]["CurrentCenter_X"] = calcDict[mir]["Center_GaussFitX"]
                calcDict[mir]["CurrentCenter_Y"] = calcDict[mir]["Center_GaussFitY"]
            else:
                calcDict[mir]["CurrentCenter_X"] = calcDict[mir]["CoM_X"]
                calcDict[mir]["CurrentCenter_Y"] = calcDict[mir]["CoM_Y"]
        except KeyError:
            pass


def main():

    app = QApplication(sys.argv)
    window = MyWindow()
    sys.exit(app.exec_())


# catch excpetion, print it and wait for user input
# designed so that the python console does not close immediatly
# when it is run from a shortcut

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error(traceback.format_exc())
        print(e)
        input("Press enter to exit...\n")
        raise
