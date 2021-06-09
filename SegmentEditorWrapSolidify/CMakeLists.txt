
#-----------------------------------------------------------------------------
set(MODULE_NAME SegmentEditorWrapSolidify)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  ${MODULE_NAME}Lib/__init__.py
  ${MODULE_NAME}Lib/SegmentEditorEffect.py
  )

set(MODULE_PYTHON_RESOURCES
  ${MODULE_NAME}Lib/SegmentEditorEffect.png
  ${MODULE_NAME}Lib/SegmentEditorEffect.ui
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  #slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  #add_subdirectory(Testing)
endif()
