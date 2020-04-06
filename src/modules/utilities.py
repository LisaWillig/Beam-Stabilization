import os
from datetime import datetime

class saveClass:
    """
    Class for writing and reading the reference values from the position logging file
    (ConfigFileName)

    Methods:
        createOrOpenConfigFile
        readLastConfig
        writeNewCenter
    """

    def __init__(self, config):
        self.fn = "BeamStabilization\\"+str(config.ConfigFileName)

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

    def readLastConfig(self, dataDict, line=-1):
        """
        Open the file object and read the last entry (default) or the specified line
        :param line: reference position
        :return: bool, if it was succesfull
        """

        #open(self.fn, 'a+')
        try:
            if os.stat(self.fn).st_size != 0:
                with open(self.fn, 'r') as file:
                    lines = file.read().splitlines()
                    last_line = lines[line]
                dataDict[0]["GoalPixel_X"] = float(last_line.split('\t')[0])
                dataDict[0]["GoalPixel_Y"] = float(last_line.split('\t')[1])
                dataDict[1]["GoalPixel_X"] = float(last_line.split('\t')[2])
                dataDict[1]["GoalPixel_Y"] = float(last_line.split('\t')[3])
                return True
        except FileNotFoundError:
            return False

    def writeNewCenter(self, dataDict):
        """
        write the new reference position to the position reference file.
        """

        file = self.createOrOpenConfigFile()
        file.write(str(dataDict[0]["Center_GaussFitX"])+'\t')
        file.write(str(dataDict[0]["Center_GaussFitY"])+'\t')
        file.write(str(dataDict[1]["Center_GaussFitX"])+'\t')
        file.write(str(dataDict[1]["Center_GaussFitY"])+'\t')
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

    def __init__(self, config):
        self.SavingDestination = config.SavingDestination
        self.createFolderAndFile()

    def createFolderAndFile(self):
        """
        Get the file object with previous reference positions.
        Create it, if it does not exist (size == 0), write header in new file
        :return: file object
        """

        if not os.path.exists(self.SavingDestination+"\\Logging"):
            os.makedirs(self.SavingDestination+"\\Logging")
        os.chdir(self.SavingDestination+"\\Logging")
        self.timeStamp = str(datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.file = open(str(self.timeStamp), 'a+')

        self.file.write('# timeStamp\t FWHMX1\t FWHMY1\t FWHMX2\t '
                        'FWHMY2\t CoM_X1\t CoM_X2\t '
                        'CoM_Y1\tCoM_Y2\tGausscenterX1\t '
                        'GausscenterX2\t '
                   'GausscenterY1\t GausscenterY2\n')

    def saveValues(self, dataDict):
        """
        write line to logging file from the global dictionaries for both cameras:
            time
            FWHM_X, FWHM_Y
            CoM_X, CoM_Y
            Center_GaussFitX, Center_GaussFitY
        """
        self.file.write(str(datetime.now().strftime("%Y%m%d_%H%M%S")) + '\t')

        self.file.write(str(dataDict[0]["FWHM_X"])+'\t')
        self.file.write(str(dataDict[0]["FWHM_Y"]) + '\t')
        self.file.write(str(dataDict[1]["FWHM_X"]) + '\t')
        self.file.write(str(dataDict[1]["FWHM_Y"]) + '\t')

        self.file.write(str(dataDict[0]["CoM_X"]) + '\t')
        self.file.write(str(dataDict[1]["CoM_X"]) + '\t')
        self.file.write(str(dataDict[0]["CoM_Y"]) + '\t')
        self.file.write(str(dataDict[1]["CoM_Y"]) + '\t')

        self.file.write(str(dataDict[0]["Center_GaussFitX"]) + '\t')
        self.file.write(str(dataDict[1]["Center_GaussFitX"]) + '\t')
        self.file.write(str(dataDict[0]["Center_GaussFitY"]) + '\t')
        self.file.write(str(dataDict[1]["Center_GaussFitY"]) + '\n')

    def closeFile(self):
        """
        close file object at the end of logging
        """

        self.file.close()