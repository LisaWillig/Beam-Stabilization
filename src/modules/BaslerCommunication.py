from pypylon import pylon
from pypylon import genicam
import pyqtgraph as pg
import numpy as np

class BaslerCamera:

    def __init__(self):
        tlFactory = pylon.TlFactory.GetInstance()
        self.devices = tlFactory.EnumerateDevices()
        self.camera = pylon.InstantCamera(
            tlFactory.CreateDevice(
            self.devices[2]))

    def openCommunication(self):
        self.camera.Open()
        print(self.camera.DeviceUserID())


    def setCameraParameters(self, exposureTime):
        self.camera.MaxNumBuffer = 2
        try:
            self.camera.Gain = self.camera.Gain.Min
        except genicam.LogicalErrorException:
            self.camera.GainRaw = self.camera.GainRaw.Min
        self.camera.Width = self.camera.Width.Max
        self.camera.Height = self.camera.Height.Max
        self.camera.ExposureTimeRaw = exposureTime
        #self.camera.PixelFormat = "Mono12"

    def getImage(self):
        self.camera.StartGrabbingMax(1)
        return self.camIsGrabbing()

    def camIsGrabbing(self):

        while self.camera.IsGrabbing():

            result = self.camera.RetrieveResult(
                5000,
                pylon.TimeoutHandling_ThrowException)
            if result.GrabSucceeded():
                img = result.Array
                result.Release()

            else:
                print("Error: ", result.GetErrorCode(), result.GetErrorDescription())
        return img


class BaslerMultiple():

    def __init__(self, camsToUse):

        self.tlFactory = pylon.TlFactory.GetInstance()
        self.camNames = camsToUse

        # Get all attached devices and exit application if no device is found.
        self.devices = self.tlFactory.EnumerateDevices()
        if len(self.devices) == 0:
            raise pylon.RUNTIME_EXCEPTION("No camera present.")

        # Create an array of instant cameras for the found devices and avoid
        # exceeding a maximum number of devices.
        self.cameras = pylon.InstantCameraArray(min(len(self.devices), len(self.devices)))

    def openCommunications(self):
        self.camList = []
        camContext = 0

    # Create and attach all Pylon Devices.
        for i, cam in enumerate(self.cameras):
            try:
                cam.Attach(self.tlFactory.CreateDevice(self.devices[i]))
                cam.Open()

                if cam.DeviceUserID() not in self.camNames.values():
                    cam.Close()
                else:
                    camContext = self.setCamContextByKey(cam.DeviceUserID())
                    cam.SetCameraContext(camContext)
                    self.camList.append(i)

            except genicam._genicam.RuntimeException:
                self.cameras.DetachDevice()
                self.cameras.DestroyDevice()

    def setCamContextByKey(self, deviceID):

        for key, value in self.camNames.items():
            if value == deviceID:
                return key

    def setCameraParameters(self, exposureTime):
        for i in self.camList:
            cam=self.cameras[i]
            cam.MaxNumBuffer = 2
            cam.ExposureTimeRaw = exposureTime
            try:
                cam.Gain = cam.Gain.Min
            except genicam.LogicalErrorException:
                cam.GainRaw = cam.GainRaw.Min
            cam.Width = cam.Width.Max
            cam.Height = cam.Height.Max
            cam.ExposureTimeRaw = exposureTime

    def startAquisition(self):
        for i in self.camList:
            cam=self.cameras[i]
            cam.StartGrabbing(1)

    def getImage(self):
        return self.startGrab(1)

    def startGrab(self, countOfImagesToGrab):
        # Starts grabbing for all cameras starting with index 0. The grabbing
        # is started for one camera after the other. That's why the images of all
        # cameras are not taken at the same time.
        # However, a hardware trigger setup can be used to cause all cameras to grab images synchronously.
        # According to their default configuration, the cameras are
        # set up for free-running continuous acquisition.
        imageArray = []
        contextArray = []
        for j in self.camList:
            cam = self.cameras[j]
            # Grab c_countOfImagesToGrab from the cameras.
            for i in range(countOfImagesToGrab):
                if not cam.IsGrabbing():
                    cam.StartGrabbing(1)
                img, cameraContextValue = self.retrieveImage(cam)
                imageArray.append(img)
                contextArray.append(cameraContextValue)
        return imageArray, contextArray

    def grabResultImage(self, cam):
        return cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

    def close(self):
        for i in self.camList:
            cam=self.cameras[i]
            cam.Close()

    def stopAcquisition(self):
        for i in self.camList:
            cam=self.cameras[i]
            cam.StopGrabbing()

    def retrieveImage(self, cam):

        grabResult = self.grabResultImage(cam)

        # When the cameras in the array are created the camera context value
        # is set to the index of the camera in the array.
        # The camera context is a us♠er settable value.
        # This value is attached to each grab result and can be used
        # to determine the camera that produced the grab result.
        cameraContextValue = grabResult.GetCameraContext()

        # Print the index and the model name of the camera.
        # print("Camera ", cameraContextValue, ": ",
        #       cam.GetCameraContext())
        # Now, the image data can be processed.
        #print("GrabSucceeded: ", grabResult.GrabSucceeded())
        retrieve = 0
        while retrieve == 0:
            try:
                img = grabResult.GetArray()
                retrieve = 1
            except TypeError:
                pass

        return img, cameraContextValue

    def getPixelSize(self, camera):

        conversion = np.genfromtxt("camPixelConversion.txt", dtype='str')
        for i, cam in enumerate(self.cameras):
            if cam.DeviceUserID() == camera:
                dev = cam.DeviceModelName()
                for i, entry in enumerate(conversion[:, 0]):
                    if entry == dev:
                        return conversion[i, 1], conversion[i, 2]

        return 0,0




'''
def main():
    cam = BaslerCamera()
    cam.openCommunication()
    cam.setCameraParameters(6000)
    img = cam.getImage()
    print(img)
'''

def main():


    cams = BaslerMultiple(namesCamsToUse)
    cams.openCommunications()
    cams.setCameraParameters(6000)
    h, v = cams.getPixelSize('BS_3')
    print(h, v)
    #cams.startAquisition()
    #for i in range(2):
    #    img, cont = cams.getImage()
    #    print(img)
    """

    single = BaslerCamera()
    single.openCommunication()
    img = single.getImage()
    print(img)
    """
if __name__ == '__main__':
        main()