##### Number of Cams
CamsToUse = 2

# Order of cams and name (UserDeviceId)
namesCamsToUse = {0: 'BS_10', 1: 'BS_11'}

#### Other Variables
exposureTime = {0: 10, 1: 10}
#exposureTime0 = 10000 #muS
#exposureTime1 = 10000 #muS
SavingDestination = "BeamStabilization"
ConfigFileName = "PositionConfigFile.dat"
conversionFactor = 7/200 # (mm/px, calculate real world mm on camera from px)
imgColormap = "inferno"

# Address of Mirror Controller
mirrorAddress = 'ASRLCOM4::INSTR'