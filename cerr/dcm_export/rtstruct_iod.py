# Module to export structures to RTSTRUCT DICOM
#
# APA, 11/13/2023

import SimpleITK as sitk
import os
from datetime import datetime
import numpy as np
from pydicom import dcmread
from pydicom.uid import generate_uid
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ImplicitVRLittleEndian
import scipy.io as sio
import argparse
from random import randint
from cerr.dcm_export import iod_helper
from cerr.dataclasses import scan as scn

org_root = '1.3.6.1.4.1.9590.100.1.2.'

def get_dcm_tag_vals(structNumV, planC, seriesDescription):

    assocScanNum = scn.getScanNumFromUID(planC.structure[structNumV[0]].assocScanUID,planC)
    pat_tags = {"PatientName": planC.scan[assocScanNum].scanInfo[0].patientName,
        "PatientID": planC.scan[assocScanNum].scanInfo[0].patientID,
        "PatientBirthDate": planC.scan[assocScanNum].scanInfo[0].patientBirthDate,
        "PatientSex": planC.scan[assocScanNum].scanInfo[0].patientSex,
        "PatientAge": "", #planC.scan[assocScanNum].scanInfo[0].patientAge
        "PatientSize": planC.scan[assocScanNum].scanInfo[0].patientSize,
        "PatientWeight": planC.scan[assocScanNum].scanInfo[0].patientWeight
                }

    study_tags = {"StudyDate": planC.scan[assocScanNum].scanInfo[0].studyDate,
        "StudyTime": planC.scan[assocScanNum].scanInfo[0].studyTime,
        "StudyDescription": planC.scan[assocScanNum].scanInfo[0].studyDescription,
        "StudyInstanceUID": planC.scan[assocScanNum].scanInfo[0].studyInstanceUID,
        "StudyID": "" #planC.scan[assocScanNum].scanInfo[0].studyID
                }

    dt = datetime.now()
    series_tags = {
        'Modality': 'RTSTRUCT',
        'SeriesDate': dt.strftime("%Y%m%d"),
        'SeriesTime': dt.strftime("%H%M%S.%f"),
        'SeriesDescription': seriesDescription,
        'SeriesInstanceUID': generate_uid(prefix=org_root),
        'SeriesNumber': str(randint(9010, 9900))
    }

    equiqmt_tags = {"Manufacturer": "",
        "ManufacturerModelName": "",
        "InstitutionName": ""
                    }

    content_tags = {"ContentDescription": "",
        "ContentLabel": ""}

    struct_set_tags = {"InstanceNumber": "",
                     "StructureSetDescription": "",
                     "StructureSetLabel": ""
                       }

    return pat_tags, study_tags, series_tags, equiqmt_tags, content_tags, struct_set_tags

def get_ref_FOR_seq(structNumV, planC):
    # 3006,0010 Referenced Frame of Reference Sequence
        # 0020,0052  Frame of Reference UID
        # 3006,0012  RT Referenced Study Sequence
            # 0008,1150  Referenced SOP Class UID
            # 0008,1155  Referenced SOP Instance UID
            # 3006,0014  RT Referenced Series Sequence
                # 0020,000E  Series Instance UID
                # 3006,0016  Contour Image Sequence
                    # 0008,1150  Referenced SOP Class UID
                    # 0008,1155  Referenced SOP Instance UID
                    # 0008,1160  Referenced Frame Number (currently not implemented)
    refFORSeq = Sequence()
    assocScanNum = scn.getScanNumFromUID(planC.structure[structNumV[0]].assocScanUID,planC)
    dsRefFOR = Dataset()
    dsRefFOR.FrameOfReferenceUID = planC.scan[assocScanNum].scanInfo[0].frameOfReferenceUID
    dsRefFOR.RTReferencedStudySequence = Sequence()
    dsStudy = Dataset()
    dsStudy.ReferencedSOPClassUID = planC.scan[assocScanNum].scanInfo[0].sopClassUID # add to import
    dsStudy.ReferencedSOPInstanceUID = planC.scan[assocScanNum].scanInfo[0].studyInstanceUID
    dsStudy.RTReferencedSeriesSequence = Sequence()
    dsSeries = Dataset()
    dsSeries.SeriesInstanceUID = planC.scan[assocScanNum].scanInfo[0].seriesInstanceUID
    dsSeries.ContourImageSequence = Sequence()
    for sInfo in planC.scan[assocScanNum].scanInfo:
        dsContourImage = Dataset()
        dsContourImage.ReferencedSOPClassUID = sInfo.sopClassUID
        dsContourImage.ReferencedSOPInstanceUID = sInfo.sopInstanceUID
        dsSeries.ContourImageSequence.append(dsContourImage)
    dsStudy.RTReferencedSeriesSequence.append(dsSeries)
    dsRefFOR.RTReferencedStudySequence.append(dsStudy)
    refFORSeq.append(dsRefFOR)
    return refFORSeq


def get_struct_set_roi_seq(structNumV, planC):
    # 3006,0020 Structure Set ROI Sequence
        # 3006,0022  ROI Number
        # 3006,0024  Referenced Frame of Reference UID
        # 3006,0026  ROI Name
        # 3006,0028  ROI Description
        # 3006,002C  ROI Volume
        # 3006,0036  ROI Generation Algorithm
        # 3006,0038  ROI Generation Description
    assocScanNum = scn.getScanNumFromUID(planC.structure[structNumV[0]].assocScanUID,planC)
    strSetROISeq = Sequence()
    for iStr in structNumV:
        dsStrSet = Dataset()
        dsStrSet.ROINumber = iStr + 1
        dsStrSet.ReferencedFrameOfReferenceUID = planC.scan[assocScanNum].scanInfo[0].frameOfReferenceUID
        dsStrSet.ROIName = planC.structure[iStr].structureName
        dsStrSet.ROIDescription = ""
        dsStrSet.ROIGenerationAlgorithm = planC.structure[iStr].roiGenerationAlgorithm
        dsStrSet.ROIGenerationDescription = planC.structure[iStr].roiGenerationDescription
        strSetROISeq.append(dsStrSet)
    return strSetROISeq


def convertCerrToDcmCoords(pointsM,planC):
    return pointsM

def get_roi_contour_seq(structNumV, planC):
    # 3006, 0039   ROI Contour Sequence
        #3006,0084   Referenced ROI Number
        #3006,002A   ROI Display Color
        #3006,0048   Contour Sequence
            # 3006,0048  Contour Number
            # 3006,0049  Attached Contours
            # 3006,0016 Contour Image Sequence
            #     0008,1150  Referenced SOP Class UID
            #     0008,1155  Referenced SOP Instance UID
            #     0008,1160  Referenced Frame Number
            # 3006,0042  Contour Geometric Type
            # 3006,0044  Contour Slab Thickness
            # 3006,0045  Contour Offset Vector
            # 3006,0046  Number of Contour Points
            # 3006,0050  Contour Data
    assocScanNum = scn.getScanNumFromUID(planC.structure[structNumV[0]].assocScanUID,planC)
    Image2VirtualPhysicalTransM = planC.scan[assocScanNum].Image2VirtualPhysicalTransM
    Image2PhysicalTransM = planC.scan[assocScanNum].Image2PhysicalTransM
    transM = np.matmul(Image2PhysicalTransM, np.linalg.inv(Image2VirtualPhysicalTransM))
    transM[:,:3] = transM[:,:3] * 10 # cm to mm
    roiContourSeq = Sequence()
    for iStr in structNumV:
        dsROIContour = Dataset()
        dsROIContour.ReferencedROINumber = iStr + 1 #planC.structure[iStr].roiNumber
        if len(planC.structure[0].structureColor) > 0:
            dsROIContour.ROIDisplayColor = planC.structure[iStr].structureColor
        contourSeq = Sequence()
        for slcNum in range(len(planC.scan[assocScanNum].scanInfo)):
            if not hasattr(planC.structure[iStr].contour[slcNum],'segments'):
                continue
            for seg in planC.structure[iStr].contour[slcNum].segments:
                contourImgSeq = Sequence()
                dsContour = Dataset()
                dsImg = Dataset()
                dsImg.ReferencedSOPClassUID = planC.scan[assocScanNum].scanInfo[slcNum].sopClassUID
                dsImg.ReferencedSOPInstanceUID = planC.scan[assocScanNum].scanInfo[slcNum].sopInstanceUID
                contourImgSeq.append(dsImg)
                dsImg.ContourImageSequence = contourImgSeq
                geom_type = 'CLOSED_PLANAR'
                if seg.points.shape[0] == 1:
                    geom_type = 'POINT'
                dsContour.ContourGeometricType = geom_type
                dsContour.NumberOfContourPoints = seg.points.shape[0]
                #pointsArray = convertCerrToDcmCoords(seg.points,planC)
                tempPtsM = np.hstack((seg.points, np.ones((seg.points.shape[0], 1))))
                #tempPtsM = np.matmul(np.linalg.inv(Image2VirtualPhysicalTransM), tempPtsM.T)
                #tempPtsM = np.matmult(Image2PhysicalTransM,tempPtsM)
                tempPtsM = np.matmul(transM, tempPtsM.T)
                dsContour.ContourData = tempPtsM[:3,:].flatten(order = "F").tolist()
                contourSeq.append(dsContour)
        dsROIContour.ContourSequence = contourSeq
        roiContourSeq.append(dsROIContour)

    return roiContourSeq

def get_roi_observ_seq(structNumV, planC):
    #3006,0080 RT Observation Sequence
        # 3006,0082  Observation Number
        # 3006,0084  Referenced ROI Number
        # 3006,0085  ROI Observation Label
        # 3006,0088  ROI Observation Description
        # 3006,0030  RT Related ROI Sequence
            # 30060084 Referenced ROI Number
            # 30060033 RT ROI Relationship
        # 3006,0086  RT ROI Identification Code Sequence
        # 3006,00A0  Related RT ROI Observations Sequence
            # 3006,0082 Observation Number
        # 3006,00A4  RT ROI Interpreted Type
        # 3006,00A6  ROI Interpreter
        # 300A,00E1  Material ID
        # 3006,00B0  ROI Physical Properties Sequence
            # 3006,00B2 ROI Physical Property
            # 3006 00B4 ROI Physical Property Value
    rtObsSeq = Sequence()
    for iStr in structNumV:
        dsRtObs = Dataset()
        dsRtObs.ObservationNumber = iStr
        dsRtObs.ReferencedROINumber = iStr
        dsRtObs.ROIObservationLabel = planC.structure[iStr].structureName
        #dsRtObs.RTROIInterpreted Type =
        #dsRtObs.ROIInterpreter =
        rtObsSeq.append(dsRtObs)

    return rtObsSeq

def create(structNumV, filePath, planC, seriesDescription = "Generated by pyCERR"):
    # Make sure that all structures in structNumV are associated with the same sane

    # Get related UIDs for structNumV
    pat_tags, study_tags, series_tags, equiqmt_tags, content_tags, struct_set_tags = \
        get_dcm_tag_vals(structNumV, planC, seriesDescription)

    # Initialize RTSTRUCT series
    # ds = create_reg_dataset(base_series_data, filePath)
    file_meta = iod_helper.get_file_meta('RTSTRUCT')
    ds = FileDataset(filePath, {}, file_meta=file_meta, preamble=b"\0" * 128)

    ds = iod_helper.add_sop_common_tags(ds)

    # Add Patient tags
    ds = iod_helper.add_patient_tags(ds, pat_tags)

    # Add Study tags
    ds = iod_helper.add_study_tags(ds, study_tags)

    # Add Series tags
    ds = iod_helper.add_series_tags(ds, series_tags)

    # Add Equipment tags
    ds = iod_helper.add_equipment_tags(ds, equiqmt_tags)

    # Add Content tags
    ds = iod_helper.add_content_tags(ds, content_tags)

    # Add Structure Set tags
    ds = iod_helper.add_structure_set_tags(ds, struct_set_tags)
    ds.ReferencedFrameOfReferenceSequence = get_ref_FOR_seq(structNumV, planC)
    ds.StructureSetROISequence = get_struct_set_roi_seq(structNumV, planC)
    ds.ROIContourSequence = get_roi_contour_seq(structNumV, planC)
    ds.RTROIObservationsSequence = get_roi_observ_seq(structNumV, planC)

    print("Writing RTSTRUCT file ...", filePath)
    ds.save_as(filePath)
    print("File saved.")

