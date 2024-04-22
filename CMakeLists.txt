cmake_minimum_required(VERSION 3.5)

project(SurfaceWrapSolidify)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Sebastian Andress (LMU Munich)")
set(EXTENSION_DESCRIPTION "A Segment Editor Extension that filters the surface of a segment using a combination of shrinkwrapping and raycasting.")
set(EXTENSION_ICONURL "https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify/raw/master/SurfaceWrapSolidify.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/sebastianandress/Slicer-SurfaceWrapSolidify/master/Resources/Screenshots/screenshot4.png")
set(EXTENSION_DEPENDS "NA")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(SegmentEditorWrapSolidify)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
