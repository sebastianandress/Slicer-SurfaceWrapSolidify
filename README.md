**Copyright &copy; 2020, Sebastian Andreß**\
All rights reserved. Please find the license [here](https://github.com/sebastianandress/Slicer-SurfaceWrapSolidify/blob/master/LICENSE.md).

Please cite the corresponding paper when using this filter for publications:

    @article{3DPrintWrapSolidify,
        author      = {Weidert, Simon and Andress, Sebastian and Linhart, Christoph and Suero, Eduardo M. and Greiner, Axel and Böcker, Wolfgang and Kammerlander, Christian and Becker, Christopher A.},
        title       = {3D printing method for next-day acetabular fracture surgery using a surface filtering pipeline: feasibility and 1-year clinical results},
        journal     = {International Journal of Computer Assisted Radiology and Surgery},
        publisher   = {Springer},
        date        = {2020-01-02},
    }


For further collaborations, patient studies or any help, do not hesitate to contact [Sebastian Andreß](mailto:sebastian.andress@med.uni-muenchen.de).
Thanks a lot to [Andras Lasso](https://github.com/lassoan) for also contributing and improving the module.

![Header](/Resources/Media/header.png)

# Surface Wrap Solidify

## Introduction
This effect was designed for creating fractured bone models for fast 3D printing. Especially in orthopedic trauma surgery, the editing time, as well as the printing time should be as short as possible. Using this effect helps to fulfil both features. Also, by removing inner cancellous structures, it is possible to achieve a fracture reduction on the printed model.

In our use-case, we used this effect after applying a simple threshold operation and separating the bone with simple brushing and island techniques. Please watch the [workflow example](#Workflow-Example) videos. The effect was tested on more than 30 acetabular fracture models, it reduced the printing time about 70%.

![Screenshot](/Resources/Screenshots/screenshot4.png)

## Description
The Wrap Solidify Effect uses the following pipeline:

1. A surface representation of the selected segment is created (segmented model).
    * _Smoothing Factor_ defines smoothing of the input surface representation
2. Around this segmented model a sphere is created (sphere/surface model).
3. Shrinkwrapping (iteratively shrinking and remeshing the sphere model to the segmented model) is used for surface definition.
    * _Number of Shrinkwrap Iterations_ is used to define the number of iterations.
    * _Smoothing Factor_ is used for smoothing between iterations.
    * _Spacing_ is used to define resolution of remesh.
4. (optional) The resulting surface model is converted into a segmentation.

### Optional Steps

* **Carve out Cavities**:
    1. Three initial shrinking and remeshing iterations ([Step 1-3](#Description)).
        * _Minimal Cavities Diameter_ and _Minimal Cavities Depth_ is used to define cavities (like in the example images the acetabular cup)
    2. Vertices of the surface model get projected into cavities.
    3. Final shrinkwrap iterations ([Step 3-4](#Description)).

* **Create Shell**:
    1. Initial Shrinkwrapping ([Step 1-3](#Description)).
    2. After the shrinkwrapping, all vertices of the surface model, that are not touching the segmented model, are deleted.
        * _Shell to Input Distance_ is used to define maximal allowed distance between the vertices of the surface model and the segmented model.
    3. The surface model gets converted to a solid shell model.
        * _Output Shell Thickness_ is used to define the thickness of this shell.
    4. (optional) [Step 4](#Description).


<!-- ### Kwargs for code implementation
| Parameter | Key | Default | Possible Values | Unit | Type | Feature
| - | - | - | - | - | - | - |
| Output Type | `outputType` | `SEGMENTATION` | `SEGMENTATION`, `MODEL` | | `string` | |
| Smoothing Factor | `smoothingFactor` | `0.2` | `0-1` | | `float` | |
| Carve out Cavities | `carveCavities` | `False` | `True`, `False` | | `bool` | |
| Minimal Cavities Diameter | `cavitiesDiameter` | `20.0` | `>0` |  |  `float` | |
| Minimal Cavities Depth | `cavitiesDepth` | `100.0` | `>0` | mm | `float` | |
| Create Shell | `createShell` | `False` | `True`, `False` | | `bool` | |
| Shell Thickness | `shellThickness` | `1.5` | `>=-0.1` | mm | `float` | If <0, a non-solid model will be created. |
| Number of Shrinkwrap Iterations | `iterationsNr` | `7` | `>0` | `int` | |
| Spacing | `spacing` | `1.0` | `>0` | mm^3 | `float` | |
| Shell to Input Distance | `shellDistance` | `0.7` | `>=-0.1` | mm | `float` | If <0, no vertex gets deleted. | -->


## Results
To see the creation of the results, please see the [Workflow Example](#Workflow-Example) section.

![Results Image](/Resources/Media/result.gif)


## Workflow Example

As described in the [Introduction](#Introduction), this effect was designed to create fast printable bones as easy and least time consuming as possible. The parameters are especially fitted for hemipelvic bones. The threshold and manual edit takes about 3 minutes, the effect itself another 2 minutes resulting in an printable bone. The effect itself reduces the printing time about 70 percent.

### Threshold
[![Threshold Video Preview Image](/Resources/Media/threshold.png)](https://1drv.ms/v/s!AqzdGuIdWLfeiNpPJhrVKhDsuxqw7w?e=6DOqgo)

A thresholding operation between 300 and the maximal Houndsfiled Unit was performed, using the __Threshold__ effect. By using the sphere brush, first the femoral head, and subsequently connecting parts in the sacroiliac joint were erased. Using the __Islands__ effect, the exempted hemipelvis was added to an own segment.

### Filter process
[![Processing Video Preview Image](/Resources/Media/processing.png)](https://1drv.ms/v/s!AqzdGuIdWLfeiNpO1rx9ZGbbhk6frQ?e=5NFQMt)

In this example, the processing time was 1:46 min on a Apple MacBook Pro 2017 (3,1 GHz Intel Core i7, Memory 16 GB).


## How to install
The Extension is available in the [Extension Manager](http://slicer.kitware.com/midas3/slicerappstore/extension/view?extensionId=330842) for Slicer Versions greater than 4.11.
To install it manually, please follow the description on the official [3D Slicer page](https://www.slicer.org/wiki/Documentation/Nightly/Developers/FAQ/Extensions). 
