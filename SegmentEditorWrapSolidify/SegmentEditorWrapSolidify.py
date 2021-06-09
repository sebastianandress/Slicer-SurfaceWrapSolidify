import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

class SegmentEditorWrapSolidify(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    import string
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SegmentEditorWrapSolidify"
    self.parent.categories = ["Segmentation"]
    self.parent.dependencies = []
    self.parent.contributors = ["Sebastian Andress (LMU Munich)"]
    self.parent.hidden = True
    self.parent.helpText = "This hidden module registers the segment editor effect."
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
      This filter was created by Sebastian Andress (LMU University Hospital Munich, Germany, Department of General-, Trauma- and Reconstructive Surgery).
      """
    slicer.app.connect("startupCompleted()", self.registerEditorEffect)

  def registerEditorEffect(self):
    import qSlicerSegmentationsEditorEffectsPythonQt as qSlicerSegmentationsEditorEffects
    instance = qSlicerSegmentationsEditorEffects.qSlicerSegmentEditorScriptedEffect(None)
    effectFilename = os.path.join(os.path.dirname(__file__), self.__class__.__name__+'Lib/SegmentEditorEffect.py')
    instance.setPythonSource(effectFilename.replace('\\','/'))
    instance.self().register()

# class SegmentEditorWrapSolidifyWidget(ScriptedLoadableModuleWidget):

#   def setup(self):
#     ScriptedLoadableModuleWidget.setup(self)

class SegmentEditorWrapSolidifyTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_WrapSolidify1()

  def test_WrapSolidify1(self):
    """
    Basic automated test of the segmentation method:
    - Create segmentation by placing sphere-shaped seeds
    - Run segmentation
    - Verify results using segment statistics
    The test can be executed from SelfTests module (test name: SegmentEditorWrapSolidify)
    """

    self.delayDisplay("Starting test_WrapSolidify1")

    import vtkSegmentationCorePython as vtkSegmentationCore
    import vtkSlicerSegmentationsModuleLogicPython as vtkSlicerSegmentationsModuleLogic
    import SampleData
    from SegmentStatistics import SegmentStatisticsLogic

    ##################################
    self.delayDisplay("Load master volume")

    masterVolumeNode = SampleData.downloadSample('MRBrainTumor1')

    ##################################
    self.delayDisplay("Create segmentation containing a two spheres")

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
    segmentationNode.CreateDefaultDisplayNodes()
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)
    
    features = ["none", "carveCavities", "createShell", "both"]
    spheres = [
      [20, 5, 5, 5],
      [20, -5,-5,-5]]
    appender = vtk.vtkAppendPolyData()
    for sphere in spheres:
      sphereSource = vtk.vtkSphereSource()
      sphereSource.SetRadius(sphere[0])
      sphereSource.SetCenter(sphere[1], sphere[2], sphere[3])
      appender.AddInputConnection(sphereSource.GetOutputPort())

    for m in features:
      segmentName = str(m)
      segment = vtkSegmentationCore.vtkSegment()
      segment.SetName(segmentationNode.GetSegmentation().GenerateUniqueSegmentID(segmentName))
      appender.Update()
      segment.AddRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName(), appender.GetOutput())
      segmentationNode.GetSegmentation().AddSegment(segment)

    ##################################
    self.delayDisplay("Create segment editor")

    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    segmentEditorWidget.show()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
    slicer.mrmlScene.AddNode(segmentEditorNode)
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

    ##################################
    self.delayDisplay("Run WrapSolidify Effect")
    segmentEditorWidget.setActiveEffectByName("Wrap Solidify")
    effect = segmentEditorWidget.activeEffect()

    for t in ["SEGMENTATION", "MODEL"]:
      effect.setParameter("outputType", t)

      self.delayDisplay("Creating Output Type %s, activated feature none" %(t))
      segmentEditorWidget.setCurrentSegmentID(segmentationNode.GetSegmentation().GetSegmentIdBySegmentName('none'))
      effect.setParameter("carveCavities", False)
      effect.setParameter("createShell", False)
      effect.self().onApply()

      self.delayDisplay("Creating Output Type %s, activated feature carveCavities" %(t))
      effect.setParameter("carveCavities", True)
      effect.setParameter("createShell", False)
      segmentEditorWidget.setCurrentSegmentID(segmentationNode.GetSegmentation().GetSegmentIdBySegmentName('carveCavities'))
      effect.self().onApply()

      self.delayDisplay("Creating Output Type %s, activated feature createShell" %(t))
      effect.setParameter("carveCavities", False)
      effect.setParameter("createShell", True)
      segmentEditorWidget.setCurrentSegmentID(segmentationNode.GetSegmentation().GetSegmentIdBySegmentName('createShell'))
      effect.self().onApply()

      self.delayDisplay("Creating Output Type %s, activated feature both" %(t))
      effect.setParameter("carveCavities", True)
      effect.setParameter("createShell", True)
      segmentEditorWidget.setCurrentSegmentID(segmentationNode.GetSegmentation().GetSegmentIdBySegmentName('both'))
      effect.self().onApply()

    ##################################
    self.delayDisplay("Creating Segments from Models")
    for m in features:
      model = slicer.util.getNode(m)
      segmentName = "MODEL_%s" % m
      segment = vtkSegmentationCore.vtkSegment()
      segment.SetName(segmentationNode.GetSegmentation().GenerateUniqueSegmentID(segmentName))
      segment.SetColor(model.GetDisplayNode().GetColor())
      segment.AddRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName(), model.GetPolyData())
      segmentationNode.GetSegmentation().AddSegment(segment)

    ##################################
    self.delayDisplay("Compute statistics")
    segStatLogic = SegmentStatisticsLogic()
    segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    segStatLogic.getParameterNode().SetParameter("ScalarVolume", masterVolumeNode.GetID())
    segStatLogic.computeStatistics()
    statistics = segStatLogic.getStatistics()

    ##################################
    self.delayDisplay("Check a few numerical results")
    
    # logging.info(round(statistics["none",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["MODEL_none",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["carveCavities",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["MODEL_carveCavities",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["createShell",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["MODEL_createShell",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["both",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))
    # logging.info(round(statistics["MODEL_both",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']))

    self.assertEqual( round(statistics["none",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 46605)
    self.assertEqual( round(statistics["MODEL_none",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 46320)

    self.assertEqual( round(statistics["carveCavities",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 46605)
    self.assertEqual( round(statistics["MODEL_carveCavities",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 46321)

    self.assertEqual( round(statistics["createShell",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 9257)
    self.assertEqual( round(statistics["MODEL_createShell",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 9230)

    self.assertEqual( round(statistics["both",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 9254)
    self.assertEqual( round(statistics["MODEL_both",'ScalarVolumeSegmentStatisticsPlugin.volume_mm3']), 9245)
    
    self.delayDisplay('test_WrapSolidify1 passed')
