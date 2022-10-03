import os
import vtk, qt, ctk, slicer
import logging
from SegmentEditorEffects import *
import numpy as np
import math
import vtkSegmentationCorePython

class SegmentEditorEffect(AbstractScriptedSegmentEditorEffect):
  """This effect uses shrinkwrap, raycasting, remesh, and solidifying algorithms to filter the surface from the input segmentation"""

  def __init__(self, scriptedEffect):
    scriptedEffect.name = 'Wrap Solidify'
    scriptedEffect.perSegment = True # this effect operates on all segments at once (not on a single selected segment)
    AbstractScriptedSegmentEditorEffect.__init__(self, scriptedEffect)

    self.logic = WrapSolidifyLogic()
    self.logic.logCallback = self.addLog

  def clone(self):
    # It should not be necessary to modify this method
    import qSlicerSegmentationsEditorEffectsPythonQt as effects
    clonedEffect = effects.qSlicerSegmentEditorScriptedEffect(None)
    clonedEffect.setPythonSource(__file__.replace('\\','/'))
    return clonedEffect

  def icon(self):
    # It should not be necessary to modify this method
    iconPath = os.path.join(os.path.dirname(__file__), 'SegmentEditorEffect.png')
    if os.path.exists(iconPath):
      return qt.QIcon(iconPath)
    return qt.QIcon()

  def helpText(self):
    return """<html>Create a solid segment from the outer surface or an internal surface of a segment. It is using a combination of shrinkwrapping, projection and solidification algorithms.<br>
    For further information, license, disclaimers and possible research partnerships visit <a href="https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify">this</a> github repository.
    </html>"""

  def activate(self):
    pass

  def deactivate(self):
    self.cleanup()
  
  def cleanup(self):
    pass

  def setupOptionsFrame(self):

    # Load widget from .ui file. This .ui file can be edited using Qt Designer
    # (Edit / Application Settings / Developer / Qt Designer -> launch).
    uiWidget = slicer.util.loadUI(os.path.join(os.path.dirname(__file__), "SegmentEditorEffect.ui"))
    self.scriptedEffect.addOptionsWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Order of buttons in the buttongroup must be the same order as the corresponding
    # options in ARG_OPTIONS[].

    self.ui.regionGroup = qt.QButtonGroup()
    self.ui.regionGroup.addButton(self.ui.regionOuterSurfaceRadioButton)
    self.ui.regionGroup.addButton(self.ui.regionLargestCavityRadioButton)
    self.ui.regionGroup.addButton(self.ui.regionSegmentRadioButton)

    self.ui.shellOffsetDirectionGroup = qt.QButtonGroup()
    self.ui.shellOffsetDirectionGroup.addButton(self.ui.shellOffsetInsideRadioButton)
    self.ui.shellOffsetDirectionGroup.addButton(self.ui.shellOffsetOutsideRadioButton)

    self.ui.outputTypeGroup = qt.QButtonGroup()
    self.ui.outputTypeGroup.addButton(self.ui.outputSegmentRadioButton)
    self.ui.outputTypeGroup.addButton(self.ui.outputNewSegmentRadioButton)
    self.ui.outputTypeGroup.addButton(self.ui.outputModelRadioButton)

    # Widget to arguments mapping
    self.valueEditWidgets = {
      ARG_REGION: self.ui.regionGroup,
      ARG_REGION_SEGMENT_ID: self.ui.regionSegmentSelector,
      ARG_CARVE_HOLES_IN_OUTER_SURFACE: self.ui.carveHolesInOuterSurfaceCheckBox,
      ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER: self.ui.carveHolesInOuterSurfaceDiameterSlider,
      ARG_SPLIT_CAVITIES: self.ui.splitCavitiesCheckBox,
      ARG_SPLIT_CAVITIES_DIAMETER: self.ui.splitCavitiesDiameterSlider,
      ARG_CREATE_SHELL: self.ui.createShellCheckBox,
      ARG_SHELL_THICKNESS: self.ui.shellThicknessSlider,
      ARG_SHELL_OFFSET_DIRECTION: self.ui.shellOffsetDirectionGroup,
      ARG_SHELL_PRESERVE_CRACKS: self.ui.shellPreserveCracksCheckBox,
      ARG_OUTPUT_TYPE: self.ui.outputTypeGroup,
      ARG_OUTPUT_MODEL_NODE: self.ui.outputModelNodeSelector,
      ARG_SMOOTHING_FACTOR: self.ui.smoothingFactorSlider,
      ARG_REMESH_OVERSAMPLING: self.ui.remeshOversamplingSlider,
      ARG_SHRINKWRAP_ITERATIONS: self.ui.iterationsSlider,
      ARG_SAVE_INTERMEDIATE_RESULTS: self.ui.saveIntermediateResultsCheckBox
    }

    # Add connections

    for argName, widget in self.valueEditWidgets.items():
      widgetClassName = widget.metaObject().getClassName()
      if widgetClassName=="qMRMLSliderWidget" or widgetClassName=="ctkSliderWidget":
        widget.connect("valueChanged(double)", self.updateMRMLFromGUI)
      elif widgetClassName=="QCheckBox":
        widget.connect("stateChanged(int)", self.updateMRMLFromGUI)
      elif widgetClassName=="qMRMLNodeComboBox":
        widget.connect("currentNodeChanged(vtkMRMLNode*)", self.updateMRMLFromGUI)
      elif widgetClassName=="QButtonGroup":
        widget.connect("buttonClicked(int)", self.updateMRMLFromGUI)
      elif widgetClassName=="qMRMLSegmentSelectorWidget":
        widget.connect("currentSegmentChanged(QString)", self.updateMRMLFromGUI)
      else:
        raise Exception("Unexpected widget class: {0}".format(widgetClassName))

    self.ui.applyButton.connect('clicked()', self.onApply)

  def createCursor(self, widget):
    return slicer.util.mainWindow().cursor

  def layoutChanged(self):
    pass

  def processInteractionEvents(self, callerInteractor, eventId, viewWidget):
    return False # For the sake of example

  def processViewNodeEvents(self, callerViewNode, eventId, viewWidget):
    pass # For the sake of example

  def setMRMLDefaults(self):
    for (argName, defaultValue) in ARG_DEFAULTS.items():
      self.scriptedEffect.setParameterDefault(argName, defaultValue)

  def updateGUIFromMRML(self):
    parameterNode = self.scriptedEffect.parameterSetNode()
    if not parameterNode:
      return

    # Update values in widgets
    for argName, widget in self.valueEditWidgets.items():
      widgetClassName = widget.metaObject().getClassName()
      oldBlockSignalsState = widget.blockSignals(True)
      if widgetClassName=="qMRMLSliderWidget" or widgetClassName=="ctkSliderWidget":
        widget.value = self.scriptedEffect.doubleParameter(argName)
      elif widgetClassName=="QCheckBox":
        widget.setChecked(self.scriptedEffect.parameter(argName)=='True')
      elif widgetClassName=="qMRMLNodeComboBox":
        widget.setCurrentNodeID(parameterNode.GetNodeReferenceID(argName))
      elif widgetClassName=="QButtonGroup":
        try:
          optionIndex = ARG_OPTIONS[argName].index(self.scriptedEffect.parameter(argName))
        except ValueError:
          optionIndex = 0
        widget.button(-2-optionIndex).setChecked(True)
      elif widgetClassName=="qMRMLSegmentSelectorWidget":
        segmentationNode = parameterNode.GetSegmentationNode()
        segmentId = self.scriptedEffect.parameter(argName)
        if widget.currentNode() != segmentationNode:
          widget.setCurrentNode(segmentationNode)
        widget.setCurrentSegmentID(segmentId)
      else:
        raise Exception("Unexpected widget class: {0}".format(widgetClassName))
      widget.blockSignals(oldBlockSignalsState)

    # Enable/disable dependent widgets
    carveHolesInOuterSurface = (self.scriptedEffect.parameter(ARG_CARVE_HOLES_IN_OUTER_SURFACE) == "True")
    splitCavities = (self.scriptedEffect.parameter(ARG_SPLIT_CAVITIES) == "True")
    createShell = (self.scriptedEffect.parameter(ARG_CREATE_SHELL) == "True")
    region = self.scriptedEffect.parameter(ARG_REGION)
    
    self.valueEditWidgets[ARG_CARVE_HOLES_IN_OUTER_SURFACE].enabled = (region == REGION_OUTER_SURFACE or region == REGION_LARGEST_CAVITY)
    self.valueEditWidgets[ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER].enabled = (carveHolesInOuterSurface
      and self.valueEditWidgets[ARG_CARVE_HOLES_IN_OUTER_SURFACE].enabled)

    self.valueEditWidgets[ARG_SPLIT_CAVITIES].enabled = region == REGION_LARGEST_CAVITY
    self.valueEditWidgets[ARG_SPLIT_CAVITIES_DIAMETER].enabled = (splitCavities and self.valueEditWidgets[ARG_SPLIT_CAVITIES].enabled)

    self.valueEditWidgets[ARG_REGION_SEGMENT_ID].enabled = (region == REGION_SEGMENT)

    self.valueEditWidgets[ARG_SHELL_THICKNESS].enabled = createShell
    for widget in self.valueEditWidgets[ARG_SHELL_OFFSET_DIRECTION].buttons():
      widget.enabled = createShell
    self.valueEditWidgets[ARG_SHELL_PRESERVE_CRACKS].enabled = createShell

  def updateMRMLFromGUI(self):
    wasModified = self.scriptedEffect.parameterSetNode().StartModify()
    for argName, widget in self.valueEditWidgets.items():
      widgetClassName = widget.metaObject().getClassName()
      if widgetClassName=="qMRMLSliderWidget" or widgetClassName=="ctkSliderWidget":
        self.scriptedEffect.setParameter(argName, widget.value)
      elif widgetClassName=="QCheckBox":
        self.scriptedEffect.setParameter(argName, "True" if widget.isChecked() else "False")
      elif widgetClassName=="qMRMLNodeComboBox":
        self.scriptedEffect.parameterSetNode().SetNodeReferenceID(argName, widget.currentNodeID)
      elif widgetClassName=="QButtonGroup":
        optionName = ARG_OPTIONS[argName][-2-widget.checkedId()]
        self.scriptedEffect.setParameter(argName, optionName)
      elif widgetClassName=="qMRMLSegmentSelectorWidget":
        segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
        if widget.currentNode() != segmentationNode:
          widget.setCurrentNode(segmentationNode)
        segmentId = widget.currentSegmentID()
        self.scriptedEffect.setParameter(argName, segmentId)
      else:
        raise Exception("Unexpected widget class: {0}".format(widgetClassName))
    self.scriptedEffect.parameterSetNode().EndModify(wasModified)

  def addLog(self, text):
    slicer.util.showStatusMessage(text)
    slicer.app.processEvents() # force update

  def onApply(self):

    if self.ui.applyButton.text == 'Cancel':
      self.logic.requestCancel()
      return

    self.scriptedEffect.saveStateForUndo()

    errorMessage = None
    self.ui.applyButton.text = 'Cancel'
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
      # Set inputs
      self.logic.segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
      
      # Save smoothing factor
      segmentationSmoothingFactor = (
        self.logic.segmentationNode.GetSegmentation().GetConversionParameter(
          'Smoothing factor'
        )
      )

      # Continue setting inputs
      self.logic.segmentId = currentSegmentId = self.scriptedEffect.parameterSetNode().GetSelectedSegmentID()
      self.logic.region = self.scriptedEffect.parameter(ARG_REGION)
      self.logic.regionSegmentId = self.scriptedEffect.parameter(ARG_REGION_SEGMENT_ID) if self.scriptedEffect.parameterDefined(ARG_REGION_SEGMENT_ID) else ""
      self.logic.carveHolesInOuterSurface = (self.scriptedEffect.parameter(ARG_CARVE_HOLES_IN_OUTER_SURFACE) == "True")
      self.logic.carveHolesInOuterSurfaceDiameter = self.scriptedEffect.doubleParameter(ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER)
      self.logic.splitCavities = (self.scriptedEffect.parameter(ARG_SPLIT_CAVITIES) == "True")
      self.logic.splitCavitiesDiameter = self.scriptedEffect.doubleParameter(ARG_SPLIT_CAVITIES_DIAMETER)
      self.logic.createShell = (self.scriptedEffect.parameter(ARG_CREATE_SHELL) == "True")
      self.logic.shellThickness = self.scriptedEffect.doubleParameter(ARG_SHELL_THICKNESS)
      self.logic.shellOffsetDirection = self.scriptedEffect.parameter(ARG_SHELL_OFFSET_DIRECTION)
      self.logic.shellPreserveCracks = (self.scriptedEffect.parameter(ARG_SHELL_PRESERVE_CRACKS) == "True")
      self.logic.outputType = self.scriptedEffect.parameter(ARG_OUTPUT_TYPE)
      self.logic.outputModelNode = self.scriptedEffect.parameterSetNode().GetNodeReference(ARG_OUTPUT_MODEL_NODE)
      self.logic.remeshOversampling = self.scriptedEffect.doubleParameter(ARG_REMESH_OVERSAMPLING)
      self.logic.smoothingFactor = self.scriptedEffect.doubleParameter(ARG_SMOOTHING_FACTOR)
      self.logic.shrinkwrapIterations = self.scriptedEffect.integerParameter(ARG_SHRINKWRAP_ITERATIONS)
      self.logic.saveIntermediateResults = (self.scriptedEffect.parameter(ARG_SAVE_INTERMEDIATE_RESULTS) == "True")
      # Run the algorithm
      self.logic.applyWrapSolidify()
      # Save the output model node (a new model node may have been created in the logic)
      if self.logic.outputType == OUTPUT_MODEL:
        self.scriptedEffect.parameterSetNode().SetNodeReferenceID(ARG_OUTPUT_MODEL_NODE,
          self.logic.outputModelNode.GetID() if self.logic.outputModelNode else "")

      # Restore smoothing factor
      self.logic.segmentationNode.GetSegmentation().SetConversionParameter(
        'Smoothing factor',
        segmentationSmoothingFactor
      )

      self.logic.segmentationNode.GetSegmentation().CreateRepresentation(
        'Closed surface',
         True
      ) # Last parameter forces conversion even if it exists

      self.logic.segmentationNode.Modified() # Update display

    except Exception as e:
      import traceback
      traceback.print_exc()
      errorMessage = str(e)
    slicer.util.showStatusMessage("")
    self.ui.applyButton.text = 'Apply'
    qt.QApplication.restoreOverrideCursor()
    if errorMessage:
      slicer.util.errorDisplay("Wrap solidify failed: " + errorMessage)


class WrapSolidifyLogic(object):

  def __init__(self):
    self.logCallback = None
    self.cancelRequested = False

    # Inputs
    self.segmentationNode = None
    self.segmentId = None
    self.region = ARG_DEFAULTS[ARG_REGION]
    self.regionSegmentId = None
    self.carveHolesInOuterSurface = ARG_DEFAULTS[ARG_CARVE_HOLES_IN_OUTER_SURFACE]
    self.carveHolesInOuterSurfaceDiameter = ARG_DEFAULTS[ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER]
    self.splitCavities = ARG_DEFAULTS[ARG_SPLIT_CAVITIES]
    self.splitCavitiesDiameter = ARG_DEFAULTS[ARG_SPLIT_CAVITIES_DIAMETER]
    self.createShell = ARG_DEFAULTS[ARG_CREATE_SHELL]
    self.shellThickness = ARG_DEFAULTS[ARG_SHELL_THICKNESS]
    self.shellOffsetDirection = ARG_DEFAULTS[ARG_SHELL_OFFSET_DIRECTION]
    self.shellPreserveCracks = ARG_DEFAULTS[ARG_SHELL_PRESERVE_CRACKS]
    self.outputType = ARG_DEFAULTS[ARG_OUTPUT_TYPE]
    self.outputModelNode = None
    self.remeshOversampling = ARG_DEFAULTS[ARG_REMESH_OVERSAMPLING]
    self.smoothingFactor = ARG_DEFAULTS[ARG_SMOOTHING_FACTOR]
    self.shrinkwrapIterations = ARG_DEFAULTS[ARG_SHRINKWRAP_ITERATIONS]
    self.saveIntermediateResults = ARG_DEFAULTS[ARG_SAVE_INTERMEDIATE_RESULTS]

    # Temporary variables
    self._inputPd = None
    self._inputSpacing = None

  def requestCancel(self):
    logging.info("User requested cancelling.")
    self.cancelRequested = True

  def _log(self, message):
    if self.logCallback:
      self.logCallback(message)

  def _checkCancelRequested(self):
    if self.cancelRequested:
      self.checkCancelRequested = False
      raise ValueError("Cancel requested")

  def applyWrapSolidify(self):
    """Applies the Shrinkwrap-Raycast-Shrinkwrap Filter, a surface filter, to the selected passed segment.
    """
    self.cancelRequested = False

    self.intermediateResultCounter = 0
    self.previousIntermediateResult = None

    try:
      self._log('Get input data...')
      self._updateInputPd()

      self._log('Create starting region...')
      regionPd = self._getInitialRegionPd()

      shrunkenPd = vtk.vtkPolyData()
      shrunkenPd.DeepCopy(self._shrinkWrap(regionPd))

      if self.region == REGION_LARGEST_CAVITY:
        self._log('Extract largest cavity...')
        shrunkenPd.DeepCopy(self._extractCavity(shrunkenPd))

      self._log('Smoothing...')
      shrunkenPd.DeepCopy(WrapSolidifyLogic._smoothPolydata(shrunkenPd, self.smoothingFactor))
      self._saveIntermediateResult("Smoothed", shrunkenPd)

      # Create shell
      if self.createShell:
        if self.shellPreserveCracks:
          self._checkCancelRequested()
          self._log('Shell - preserving cracks...')
          shrunkenPd.DeepCopy(self._shellPreserveCracks(shrunkenPd))
          self._saveIntermediateResult("ShellRemovedCaps", shrunkenPd)
        if self.shellThickness > 1e-6:
          self._checkCancelRequested()
          self._log('Shell - solidifying...')
          shrunkenPd.DeepCopy(self._shellSolidify(shrunkenPd, self.shellThickness, self.shellOffsetDirection))
          self._saveIntermediateResult("ShellSolidified", shrunkenPd)

      # Write output to target node
      self._log('Save result...')
      baseSegmentId = self.regionSegmentId if self.region == REGION_SEGMENT else self.segmentId
      if self.outputType == OUTPUT_SEGMENT:
        WrapSolidifyLogic._polydataToSegment(shrunkenPd, self.segmentationNode, baseSegmentId)
      elif self.outputType == OUTPUT_NEW_SEGMENT:
        WrapSolidifyLogic._polydataToNewSegment(shrunkenPd, self.segmentationNode, baseSegmentId)
      elif self.outputType == OUTPUT_MODEL:
        segment = self.segmentationNode.GetSegmentation().GetSegment(baseSegmentId)
        name = segment.GetName()
        color = segment.GetColor()
        if not self.outputModelNode:
          self.outputModelNode = slicer.modules.models.logic().AddModel(shrunkenPd)
          self.outputModelNode.SetName(name)
          self.outputModelNode.GetDisplayNode().SliceIntersectionVisibilityOn()
        else:
          self.outputModelNode.SetAndObservePolyData(shrunkenPd)
        self.outputModelNode.CreateDefaultDisplayNodes()
        self.outputModelNode.GetDisplayNode().SetColor(color)
      else:
        raise ValueError('Unknown output type: '+self.outputType)

    finally:
      self._cleanup()


  def _cleanup(self):
    if self.previousIntermediateResult:
      self.previousIntermediateResult.GetDisplayNode().SetVisibility(False)
    self._inputPd = None
    self._inputSpacing = None

  def _updateInputPd(self):

    segment = self.segmentationNode.GetSegmentation().GetSegment(self.segmentId)
    self._inputPd = vtk.vtkPolyData()

    # Get input polydata and input spacing
    if self.segmentationNode.GetSegmentation().GetMasterRepresentationName() == slicer.vtkSegmentationConverter().GetSegmentationBinaryLabelmapRepresentationName():
      # Master representation is binary labelmap
      # Reconvert to closed surface using chosen chosen smoothing factor
      originalSurfaceSmoothing = float(self.segmentationNode.GetSegmentation().GetConversionParameter(
        slicer.vtkBinaryLabelmapToClosedSurfaceConversionRule().GetSmoothingFactorParameterName()))
      if abs(originalSurfaceSmoothing-self.smoothingFactor) > 0.001:
        self.segmentationNode.GetSegmentation().SetConversionParameter(
          slicer.vtkBinaryLabelmapToClosedSurfaceConversionRule().GetSmoothingFactorParameterName(), str(self.smoothingFactor))
        # Force re-conversion
        self.segmentationNode.RemoveClosedSurfaceRepresentation()
      self.segmentationNode.CreateClosedSurfaceRepresentation()
      self.segmentationNode.GetClosedSurfaceRepresentation(self.segmentId, self._inputPd)
      if self._inputPd.GetNumberOfPoints() == 0:
        raise ValueError("Input segment closed surface representation is empty")
      # Get input spacing
      inputLabelmap = slicer.vtkOrientedImageData()
      self.segmentationNode.GetBinaryLabelmapRepresentation(self.segmentId, inputLabelmap)
      extent = inputLabelmap.GetExtent()
      if extent[0]>extent[1] or extent[2]>extent[3] or extent[4]>extent[5]:
        raise ValueError("Input segment labelmap representation is empty")
      self._inputSpacing = math.sqrt(np.sum(np.array(inputLabelmap.GetSpacing())**2))
    else:
      # Representation is already closed surface
      self.segmentationNode.CreateClosedSurfaceRepresentation()
      self.segmentationNode.GetClosedSurfaceRepresentation(self.segmentId, self._inputPd)
      # set spacing to have an approxmately 250^3 volume
      # this size is not too large for average computing hardware yet
      # it is sufficiently detailed for many applications
      preferredVolumeSizeInVoxels = 250 * 250 * 250
      bounds = np.zeros(6)
      self._inputPd.GetBounds(bounds)
      volumeSizeInMm3 = (bounds[1] - bounds[0]) * (bounds[3] - bounds[2]) * (bounds[5] - bounds[4])
      self._inputSpacing = pow(volumeSizeInMm3 / preferredVolumeSizeInVoxels, 1 / 3.)


  def _getInitialRegionPd(self):
    """Get initial shape that will be snapped to closest point of the input segment"""

    spacing = self._inputSpacing / self.remeshOversampling

    if self.carveHolesInOuterSurface:
      # Grow input polydata to close holes between outer surface and internal cavities.

      # It is less accurate but more robust to dilate labelmap than grow polydata.
      # Since accuracy is not important here, we dilate labelmap.
      # Convert to labelmap
      carveHolesInOuterSurfaceRadius = self.carveHolesInOuterSurfaceDiameter/2.0
      # add self.carveHolesInOuterSurfaceDiameter extra to bounds to ensure that the grown input still has an margin around
      inputLabelmap = WrapSolidifyLogic._polydataToLabelmap(self._inputPd, spacing, extraMarginToBounds=carveHolesInOuterSurfaceRadius)

      self._saveIntermediateResult("InitialRegionResampled", WrapSolidifyLogic._labelmapToPolydata(inputLabelmap, 1))

      # Dilate
      import vtkITK
      margin = vtkITK.vtkITKImageMargin()
      margin.SetInputData(inputLabelmap)
      margin.CalculateMarginInMMOn()
      margin.SetOuterMarginMM(carveHolesInOuterSurfaceRadius)
      margin.Update()
      # extendedInputLabelmap: 255 near original inputLabelmap voxels, 0 elsewhere
      extendedInputLabelmap = margin.GetOutput()
      self._saveIntermediateResult("InitialRegionGrown", WrapSolidifyLogic._labelmapToPolydata(extendedInputLabelmap, 255))

      # Region growing from a corner of the image
      seedPoints = vtk.vtkPoints()
      seedPoints.InsertNextPoint(inputLabelmap.GetOrigin()[0] + spacing / 2,
                                 inputLabelmap.GetOrigin()[1] + spacing / 2,
                                 inputLabelmap.GetOrigin()[2] + spacing / 2)
      seedScalars = vtk.vtkUnsignedCharArray()
      seedScalars.InsertNextValue(255)  # this will be the label value to the grown region
      seedData = vtk.vtkPolyData()
      seedData.SetPoints(seedPoints)
      seedData.GetPointData().SetScalars(seedScalars)

      regionGrowing = vtk.vtkImageConnectivityFilter()
      regionGrowing.SetSeedData(seedData)
      regionGrowing.SetScalarRange(-10, 10)
      regionGrowing.SetInputData(extendedInputLabelmap)
      regionGrowing.Update()

      # outsideObjectImage: 255 outside the object, 0 inside
      outsideObjectLabelmap = regionGrowing.GetOutput()

    # Cavity extraction and outer surface extraction starts from the same outer surface shrinkwrap
    if self.region == REGION_OUTER_SURFACE or self.region == REGION_LARGEST_CAVITY:
      if self.carveHolesInOuterSurface:
        # Convert back to polydata
        initialRegionPd = vtk.vtkPolyData()
        initialRegionPd.DeepCopy(WrapSolidifyLogic._labelmapToPolydata(outsideObjectLabelmap, 255))
      else:
        # create sphere that encloses entire segment content
        bounds = np.zeros(6)
        self._inputPd.GetBounds(bounds)
        diameters = np.array([bounds[1]-bounds[0],bounds[3]-bounds[2],bounds[5]-bounds[4]])
        maxRadius = max(diameters)/2.0
        sphereSource = vtk.vtkSphereSource()
        # to make sure the volume is fully included in the sphere, radius must be sqrt(2) times larger
        sphereSource.SetRadius(maxRadius*1.5)

        # Set resolution to be about one magnitude lower than the final resolution
        # (by creating an initial surface element for about every 100th final element).
        sphereSurfaceArea = 4 * math.pi * maxRadius*maxRadius
        voxelSurfaceArea = spacing * spacing
        numberOfSurfaceElements = sphereSurfaceArea/voxelSurfaceArea
        numberOfIinitialSphereSurfaceElements = numberOfSurfaceElements/100
        sphereResolution = math.sqrt(numberOfIinitialSphereSurfaceElements)
        # Set resolution to minimum 10
        sphereResolution = max(int(sphereResolution), 10)
        sphereSource.SetPhiResolution(sphereResolution)
        sphereSource.SetThetaResolution(sphereResolution)
        sphereSource.SetCenter((bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0)
        sphereSource.Update()
        initialRegionPd = sphereSource.GetOutput()
    elif self.region == REGION_SEGMENT:
      # create initial region from segment (that will be grown)
      if not self.regionSegmentId:
        raise ValueError("Region segment is not set")
      if self.regionSegmentId == self.segmentId:
        raise ValueError("Region segment cannot be the same segment as the current segment")
      initialRegionPd = vtk.vtkPolyData()
      self.segmentationNode.GetClosedSurfaceRepresentation(self.regionSegmentId, initialRegionPd)
      if not initialRegionPd or initialRegionPd.GetNumberOfPoints() == 0:
        raise ValueError("Region segment is empty")
      # initialRegionPd = self._remeshPolydata(initialRegionPd, self._inputSpacing*5.0)  # simplify the mesh
    else:
      raise ValueError("Invalid region: "+self.region)

    cleanPolyData = vtk.vtkCleanPolyData()
    cleanPolyData.SetInputData(initialRegionPd)
    cleanPolyData.Update()
    initialRegionPd = cleanPolyData.GetOutput()

    self._saveIntermediateResult("InitialRegion", initialRegionPd)
    return initialRegionPd


  def _shrinkWrap(self, regionPd):

    shrunkenPd = regionPd
    spacing = self._inputSpacing / self.remeshOversampling

    for iterationIndex in range(self.shrinkwrapIterations):

      # shrink
      self._checkCancelRequested()
      self._log('Shrinking %s/%s...' %(iterationIndex+1, self.shrinkwrapIterations))
      if shrunkenPd.GetNumberOfPoints()<=1 or self._inputPd.GetNumberOfPoints()<=1:
        # we must not feed empty polydata into vtkSmoothPolyDataFilter because it would crash the application
        raise ValueError("Mesh has become empty during shrink-wrap iterations")
      smoothFilter = vtk.vtkSmoothPolyDataFilter()
      smoothFilter.SetInputData(0, shrunkenPd)
      smoothFilter.SetInputData(1, self._inputPd)  # constrain smoothed points to the input surface
      smoothFilter.Update()
      shrunkenPd = vtk.vtkPolyData()
      shrunkenPd.DeepCopy(smoothFilter.GetOutput())
      self._saveIntermediateResult("Shrunken", shrunkenPd)

      # remesh
      self._checkCancelRequested()
      self._log('Remeshing %s/%s...' %(iterationIndex+1, self.shrinkwrapIterations))
      remeshedPd = WrapSolidifyLogic._remeshPolydata(shrunkenPd, spacing)
      shrunkenPd = vtk.vtkPolyData()
      shrunkenPd.DeepCopy(remeshedPd)
      self._saveIntermediateResult("Remeshed", shrunkenPd)

    return shrunkenPd

  def _extractCavity(self, shrunkenPd):

    spacing = self._inputSpacing / self.remeshOversampling
    outsideObjectLabelmap = WrapSolidifyLogic._polydataToLabelmap(shrunkenPd, spacing)  # 0=outside, 1=inside

    inputLabelmap = WrapSolidifyLogic._polydataToLabelmap(self._inputPd, referenceImage=outsideObjectLabelmap)

    if self.splitCavities:
      # It is less accurate but more robust to dilate labelmap than grow polydata.
      # Since accuracy is not important here, we dilate labelmap.
      splitCavitiesRadius = self.splitCavitiesDiameter / 2.0
      # Dilate
      import vtkITK
      margin = vtkITK.vtkITKImageMargin()
      margin.SetInputData(inputLabelmap)
      margin.CalculateMarginInMMOn()
      margin.SetOuterMarginMM(splitCavitiesRadius)
      margin.Update()
      # extendedInputLabelmap: 255 near original inputLabelmap voxels, 0 elsewhere
      extendedInputLabelmap = margin.GetOutput()
      self._saveIntermediateResult("SplitCavitiesGrown",
                                   WrapSolidifyLogic._labelmapToPolydata(extendedInputLabelmap, 255))
    else:
      extendedInputLabelmap = inputLabelmap

    outsideObjectLabelmapInverter = vtk.vtkImageThreshold()
    outsideObjectLabelmapInverter.SetInputData(outsideObjectLabelmap)
    outsideObjectLabelmapInverter.ThresholdByLower(0)
    outsideObjectLabelmapInverter.SetInValue(1)  # backgroundValue
    outsideObjectLabelmapInverter.SetOutValue(0)  # labelValue
    outsideObjectLabelmapInverter.SetOutputScalarType(outsideObjectLabelmap.GetScalarType())
    outsideObjectLabelmapInverter.Update()

    addImage = vtk.vtkImageMathematics()
    addImage.SetInput1Data(outsideObjectLabelmapInverter.GetOutput())
    addImage.SetInput2Data(extendedInputLabelmap)
    addImage.SetOperationToMax()
    addImage.Update()
    internalHolesLabelmap = addImage.GetOutput()
    # internal holes are 0, elsewhere >=1
    self._saveIntermediateResult("SplitCavitiesAll", WrapSolidifyLogic._labelmapToPolydata(internalHolesLabelmap, 0))

    # Find largest internal hole
    largestHoleExtract = vtk.vtkImageConnectivityFilter()
    largestHoleExtract.SetScalarRange(-0.5, 0.5)
    largestHoleExtract.SetInputData(internalHolesLabelmap)
    largestHoleExtract.SetExtractionModeToLargestRegion()
    largestHoleExtract.Update()
    largestHolesLabelmap = largestHoleExtract.GetOutput()

    # Convert back to polydata
    initialRegionPd = vtk.vtkPolyData()
    initialRegionPd.DeepCopy(WrapSolidifyLogic._labelmapToPolydata(largestHolesLabelmap, 0))
    self._saveIntermediateResult("SplitCavitiesLargest", initialRegionPd)

    if self.splitCavities:
      return self._shrinkWrap(initialRegionPd)
    else:
      return initialRegionPd

  @staticmethod
  def _polydataToSegment(polydata, segmentationNode, segmentID):
    # Get existing representations
    segmentation = segmentationNode.GetSegmentation()
    masterRepresentationName = segmentationNode.GetSegmentation().GetMasterRepresentationName()
    representationNames = []
    segmentation.GetContainedRepresentationNames(representationNames)
    # Update
    slicer.vtkSlicerSegmentationsModuleLogic.ClearSegment(segmentationNode, segmentID)
    wasModified = segmentationNode.StartModify()
    segment = segmentation.GetSegment(segmentID)
    segment.RemoveAllRepresentations()
    segment.AddRepresentation(vtkSegmentationCorePython.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName(), polydata)
    segmentation.CreateRepresentation(masterRepresentationName)
    for representationName in representationNames:
      if representationName:
        # already converted
        continue
      segmentation.CreateRepresentation(representationName)
    segmentationNode.EndModify(wasModified)

  @staticmethod
  def _polydataToNewSegment(polydata, segmentationNode, segmentID):
    segmentation = segmentationNode.GetSegmentation()
    baseSegment = segmentation.GetSegment(segmentID)
    segment = slicer.vtkSegment()
    segment.SetName(baseSegment.GetName() + "_solid")
    segment.AddRepresentation(vtkSegmentationCorePython.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName(), polydata)
    segmentation.AddSegment(segment)

  def _saveIntermediateResult(self, name, polydata, color=None):
    if not self.saveIntermediateResults:
      return

    # Show the last intermediate result only, hide previous
    if self.previousIntermediateResult:
      self.previousIntermediateResult.GetDisplayNode().SetVisibility(False)

    polyDataCopy = vtk.vtkPolyData()
    polyDataCopy.DeepCopy(polydata)
    outputModel = slicer.modules.models.logic().AddModel(polyDataCopy)
    outputModel.SetName("WrapSolidify-{0}-{1}".format(self.intermediateResultCounter, name))
    self.intermediateResultCounter += 1
    outputModel.GetDisplayNode().SliceIntersectionVisibilityOn()
    outputModel.GetDisplayNode().SetEdgeVisibility(True)
    outputModel.GetDisplayNode().SetBackfaceCulling(False)
    if color:
      outputModel.GetDisplayNode().SetColor(color)
    else:
      outputModel.GetDisplayNode().SetColor(1.0,1.0,0)
    self.previousIntermediateResult = outputModel

  @staticmethod
  def _polydataToLabelmap(polydata, spacing = 1.0, extraMarginToBounds = 0, referenceImage = None):

    binaryLabelmap = vtk.vtkImageData()

    if referenceImage:
      origin = referenceImage.GetOrigin()
      spacing3 = referenceImage.GetSpacing()
      extent = referenceImage.GetExtent()
    else:
      bounds = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
      polydata.GetBounds(bounds)
      bounds[0] -= extraMarginToBounds
      bounds[2] -= extraMarginToBounds
      bounds[4] -= extraMarginToBounds
      bounds[1] += extraMarginToBounds
      bounds[3] += extraMarginToBounds
      bounds[5] += extraMarginToBounds

      spacing3 = np.ones(3) * spacing
      dim = [0, 0, 0]
      for i in range(3):
        # Add 3 to the dimensions to have at least 1 voxel thickness and 1 voxel margin on both sides
        dim[i] = int(math.ceil((bounds[i * 2 + 1] - bounds[i * 2]) / spacing3[i])) + 3

      # Subtract one spacing to ensure there is a margin
      origin = [
        bounds[0] - spacing3[0],
        bounds[2] - spacing3[1],
        bounds[4] - spacing3[2]]

      extent = [0, dim[0] - 1, 0, dim[1] - 1, 0, dim[2] - 1]

    binaryLabelmap.SetOrigin(origin)
    binaryLabelmap.SetSpacing(spacing3)
    binaryLabelmap.SetExtent(extent)

    binaryLabelmap.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    binaryLabelmap.GetPointData().GetScalars().Fill(0)

    pol2stenc = vtk.vtkPolyDataToImageStencil()
    pol2stenc.SetInputData(polydata)
    pol2stenc.SetOutputOrigin(origin)
    pol2stenc.SetOutputSpacing(spacing3)
    pol2stenc.SetOutputWholeExtent(binaryLabelmap.GetExtent())

    imgstenc = vtk.vtkImageStencil()
    imgstenc.SetInputData(binaryLabelmap)
    imgstenc.SetStencilConnection(pol2stenc.GetOutputPort())
    imgstenc.ReverseStencilOn()
    imgstenc.SetBackgroundValue(1)
    imgstenc.Update()

    return imgstenc.GetOutput()

  @staticmethod
  def _labelmapToPolydata(labelmap, value=1):
    discreteCubes = vtk.vtkDiscreteMarchingCubes()
    discreteCubes.SetInputData(labelmap)
    discreteCubes.SetValue(0, value)

    reverse = vtk.vtkReverseSense()
    reverse.SetInputConnection(discreteCubes.GetOutputPort())
    reverse.ReverseCellsOn()
    reverse.ReverseNormalsOn()
    reverse.Update()

    return reverse.GetOutput()

  @staticmethod
  def _remeshPolydata(polydata, spacing):
    labelmap = WrapSolidifyLogic._polydataToLabelmap(polydata, spacing)
    return WrapSolidifyLogic._labelmapToPolydata(labelmap)

  @staticmethod
  def _smoothPolydata(polydata, smoothingFactor):
    passBand = pow(10.0, -4.0 * smoothingFactor)
    smootherSinc = vtk.vtkWindowedSincPolyDataFilter()
    smootherSinc.SetInputData(polydata)
    smootherSinc.SetNumberOfIterations(20)
    smootherSinc.FeatureEdgeSmoothingOff()
    smootherSinc.BoundarySmoothingOff()
    smootherSinc.NonManifoldSmoothingOn()
    smootherSinc.NormalizeCoordinatesOn()
    smootherSinc.Update()
    return smootherSinc.GetOutput()


  def _shellPreserveCracks(self, shrunkenPd):
    """Remove cells of the mesh that are far from the original surface"""

    # Cells that are far from the input mesh will be removed from this
    shrunkenPdWithCracks = vtk.vtkPolyData()
    shrunkenPdWithCracks.DeepCopy(shrunkenPd)
    shrunkenPdWithCracks.BuildLinks()

    # Measure distance from input mesh
    implicitDistance = vtk.vtkImplicitPolyDataDistance()
    implicitDistance.SetInput(self._inputPd)

    # Determine cutoff distance
    spacing = self._inputSpacing / self.remeshOversampling
    maxDistance = 0.9 * spacing  # 0.9 because it is a bit more than half diameter of a cube (0.5*sqrt(3))

    numberOfCells = shrunkenPdWithCracks.GetNumberOfCells() 
    for c in range(numberOfCells):
      cell = shrunkenPdWithCracks.GetCell(c)
      points = cell.GetPoints()
      for p in range(points.GetNumberOfPoints()):
        point = points.GetPoint(p)
        distance = implicitDistance.EvaluateFunction(point)  # TODO: check if cell locator is faster
        if abs(distance) > maxDistance:
          shrunkenPdWithCracks.DeleteCell(c)
          break
    shrunkenPdWithCracks.RemoveDeletedCells()

    return shrunkenPdWithCracks

  @staticmethod
  def _shellSolidify(surfacePd, shellThickness, shellOffsetDirection):
    """Create a thick shell from a surface by extruding in surface normal direction"""

    # remove double vertices
    cleanPolyData = vtk.vtkCleanPolyData()
    cleanPolyData.SetInputData(surfacePd)

    # create normals
    normals = vtk.vtkPolyDataNormals()
    normals.SetComputeCellNormals(1)
    normals.SetInputConnection(cleanPolyData.GetOutputPort())
    normals.SplittingOff()
    if shellOffsetDirection == SHELL_OFFSET_OUTSIDE:
      normals.FlipNormalsOn()
    normals.Update()

    surfacePd = vtk.vtkPolyData()
    surfacePd.DeepCopy(normals.GetOutput())
    numberOfPoints = surfacePd.GetNumberOfPoints()

    # get boundary edges, used later
    featureEdges = vtk.vtkFeatureEdges()
    featureEdges.BoundaryEdgesOn()
    featureEdges.ColoringOff()
    featureEdges.FeatureEdgesOff()
    featureEdges.NonManifoldEdgesOff()
    featureEdges.ManifoldEdgesOff()
    featureEdges.SetInputData(normals.GetOutput())
    featureEdges.Update()

    addingPoints = []
    addingPolys = []

    allNormalsArray = surfacePd.GetCellData().GetArray('Normals')

    for pointID in range(numberOfPoints):
      cellIDs = vtk.vtkIdList()
      surfacePd.GetPointCells(pointID, cellIDs)
      normalsArray = []

      # ilterate through all cells/faces which contain point
      for i in range(cellIDs.GetNumberOfIds()):
        n = allNormalsArray.GetTuple3(cellIDs.GetId(i))
        normalsArray.append(np.array(n))

      # calculate position of new vert
      dir_vec = np.zeros(3)

      for n in normalsArray:
        dir_vec = dir_vec + np.array(n)

      dir_vec_norm = dir_vec / np.linalg.norm(dir_vec)
      proj_length = np.dot(dir_vec_norm, np.array(normalsArray[0]))
      dir_vec_finallenght = dir_vec_norm * proj_length
      vertex_neu = np.array(surfacePd.GetPoint(pointID)) + (dir_vec_finallenght * shellThickness)

      # append point
      addingPoints.append(vertex_neu)

    for cellID in range(surfacePd.GetNumberOfCells()):
      pointIDs = vtk.vtkIdList()
      surfacePd.GetCellPoints(cellID, pointIDs)

      newPointIDs = vtk.vtkIdList()
      for i in reversed(range(pointIDs.GetNumberOfIds())):
        newPointIDs.InsertNextId(int(pointIDs.GetId(i) + numberOfPoints))

      addingPolys.append(newPointIDs)

    doubleSurfacePoints = vtk.vtkPoints()
    doubleSurfacePolys = vtk.vtkCellArray()

    doubleSurfacePoints.DeepCopy(surfacePd.GetPoints())
    doubleSurfacePolys.DeepCopy(surfacePd.GetPolys())

    for p in addingPoints:
      doubleSurfacePoints.InsertNextPoint(p)
    for p in addingPolys:
      doubleSurfacePolys.InsertNextCell(p)

    doubleSurfacePD = vtk.vtkPolyData()
    doubleSurfacePD.SetPoints(doubleSurfacePoints)
    doubleSurfacePD.SetPolys(doubleSurfacePolys)

    # add faces to boundary edges
    mergePoints = vtk.vtkMergePoints()
    mergePoints.InitPointInsertion(doubleSurfacePD.GetPoints(), doubleSurfacePD.GetBounds())
    mergePoints.SetDataSet(doubleSurfacePD)
    mergePoints.BuildLocator()

    manifoldPolys = vtk.vtkCellArray()
    manifoldPolys.DeepCopy(doubleSurfacePD.GetPolys())
    manifoldPoints = vtk.vtkPoints()
    manifoldPoints.DeepCopy(doubleSurfacePD.GetPoints())

    for e in range(featureEdges.GetOutput().GetNumberOfCells()):
      pointIDs = vtk.vtkIdList()
      featureEdges.GetOutput().GetCellPoints(e, pointIDs)
      if pointIDs.GetNumberOfIds() == 2: # -> Edge
        matchingPointIDs = []
        newPointIDs = vtk.vtkIdList()
        for p in range(2):
          matchingPointIDs.append(mergePoints.IsInsertedPoint(featureEdges.GetOutput().GetPoint(pointIDs.GetId(p))))
        if not (-1) in matchingPointIDs: # edge vertex not found in original pd, should not happen
          newPointIDs.InsertNextId(matchingPointIDs[1])
          newPointIDs.InsertNextId(matchingPointIDs[0])
          newPointIDs.InsertNextId(matchingPointIDs[0]+numberOfPoints)
          newPointIDs.InsertNextId(matchingPointIDs[1]+numberOfPoints)
          manifoldPolys.InsertNextCell(newPointIDs)

    manifoldPD = vtk.vtkPolyData()
    manifoldPD.SetPoints(manifoldPoints)
    manifoldPD.SetPolys(manifoldPolys)

    triangleFilter = vtk.vtkTriangleFilter()
    triangleFilter.SetInputData(manifoldPD)

    # Compute normals to make the result look smooth
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(triangleFilter.GetOutputPort())
    normals.Update()

    return normals.GetOutput()


ARG_DEFAULTS = {}
ARG_OPTIONS = {}

ARG_REGION = 'region'
REGION_OUTER_SURFACE = 'outerSurface'
REGION_LARGEST_CAVITY = 'largestCavity'
REGION_SEGMENT = 'segment'
ARG_OPTIONS[ARG_REGION] = [REGION_OUTER_SURFACE, REGION_LARGEST_CAVITY, REGION_SEGMENT]
ARG_DEFAULTS[ARG_REGION] = REGION_OUTER_SURFACE

ARG_REGION_SEGMENT_ID = 'regionSegmentID'
ARG_DEFAULTS[ARG_REGION_SEGMENT_ID] = ''

ARG_CARVE_HOLES_IN_OUTER_SURFACE = 'carveHolesInOuterSurface'
ARG_DEFAULTS[ARG_CARVE_HOLES_IN_OUTER_SURFACE] = False

ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER = 'carveHolesInOuterSurfaceDiameter'
ARG_DEFAULTS[ARG_CARVE_HOLES_IN_OUTER_SURFACE_DIAMETER] = 10.0

ARG_SPLIT_CAVITIES = 'splitCavities'
ARG_DEFAULTS[ARG_SPLIT_CAVITIES] = False

ARG_SPLIT_CAVITIES_DIAMETER = 'splitCavitiesDiameter'
ARG_DEFAULTS[ARG_SPLIT_CAVITIES_DIAMETER] = 5

ARG_CREATE_SHELL = 'createShell'
ARG_DEFAULTS[ARG_CREATE_SHELL] = False

ARG_SHELL_THICKNESS = 'shellThickness'
ARG_DEFAULTS[ARG_SHELL_THICKNESS] = 1.5

ARG_SHELL_OFFSET_DIRECTION = 'shellOffsetDirection'
SHELL_OFFSET_INSIDE = 'inside'
SHELL_OFFSET_OUTSIDE = 'outside'
ARG_OPTIONS[ARG_SHELL_OFFSET_DIRECTION] = [SHELL_OFFSET_INSIDE, SHELL_OFFSET_OUTSIDE]
ARG_DEFAULTS[ARG_SHELL_OFFSET_DIRECTION] = SHELL_OFFSET_INSIDE

ARG_SHELL_PRESERVE_CRACKS = 'preserveCracks'
ARG_DEFAULTS[ARG_SHELL_PRESERVE_CRACKS] = True

ARG_OUTPUT_TYPE = 'outputType'
OUTPUT_SEGMENT = 'segment'
OUTPUT_NEW_SEGMENT = 'newSegment'
OUTPUT_MODEL = 'model'
ARG_OPTIONS[ARG_OUTPUT_TYPE] = [OUTPUT_SEGMENT, OUTPUT_NEW_SEGMENT, OUTPUT_MODEL]
ARG_DEFAULTS[ARG_OUTPUT_TYPE] = OUTPUT_SEGMENT

ARG_OUTPUT_MODEL_NODE = 'WrapSolidify.OutputModelNodeID'

ARG_REMESH_OVERSAMPLING = 'remeshOversampling'
ARG_DEFAULTS[ARG_REMESH_OVERSAMPLING] = 1.5  # 1.5x oversampling by default

ARG_SMOOTHING_FACTOR = 'smoothingFactor'
ARG_DEFAULTS[ARG_SMOOTHING_FACTOR] = 0.2

ARG_SHRINKWRAP_ITERATIONS = 'shrinkwrapIterations'
ARG_DEFAULTS[ARG_SHRINKWRAP_ITERATIONS] = 6

ARG_SAVE_INTERMEDIATE_RESULTS = 'saveIntermediateResults'
ARG_DEFAULTS[ARG_SAVE_INTERMEDIATE_RESULTS] = False
