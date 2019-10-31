import sys
import skimage
import os

from ..constants import OCRD_TOOL

from ocrd import Processor
from ocrd_modelfactory import page_from_file
from ocrd_utils import getLogger, concat_padded, MIMETYPE_PAGE

import warnings
import ocrolib
warnings.filterwarnings('ignore',category=FutureWarning) 
import tensorflow as tf
from pathlib import Path
import numpy as np

from ocrd_anybaseocr.mrcnn import model
#from ocrd_anybaseocr.mrcnn import visualize
from ocrd_anybaseocr.mrcnn.config import Config


from ocrd_models.ocrd_page import (
    CoordsType,
    TextRegionType,
    AlternativeImageType,
    to_xml,
    MetadataItemType,
    LabelsType, LabelType,
)
from ocrd_models.ocrd_page_generateds import CoordsType



TOOL = 'ocrd-anybaseocr-block-segmentation'
LOG = getLogger('OcrdAnybaseocrBlockSegmenter')
FALLBACK_IMAGE_GRP = 'OCR-D-IMG-BLOCK-SEGMENT'

class InferenceConfig(Config):
    NAME = "block"    
    IMAGES_PER_GPU = 1  
    NUM_CLASSES = 1 + 14      
    DETECTION_MIN_CONFIDENCE = 0.9

class OcrdAnybaseocrBlockSegmenter(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools'][TOOL]
        kwargs['version'] = OCRD_TOOL['version']
        super(OcrdAnybaseocrBlockSegmenter, self).__init__(*args, **kwargs) 

    def process(self):
        
        if not tf.test.is_gpu_available():
            LOG.error("Your system has no CUDA installed. No GPU detected.")
            sys.exit(1)
        
        try:
            print("OUTPUT FILE ", self.output_file_grp)
            self.page_grp, self.image_grp = self.output_file_grp.split(',')
        except ValueError:
            self.page_grp = self.output_file_grp
            self.image_grp = FALLBACK_IMAGE_GRP
            LOG.info("No output file group for images specified, falling back to '%s'", FALLBACK_IMAGE_GRP)
            
        model_path = Path(self.parameter['block_segmentation_model'])
        
        model_weights = Path(self.parameter['block_segmentation_weights'])
        class_names = ['BG','page-number', 'paragraph', 'catch-word', 'heading', 'drop-capital', 'signature-mark','header',
                       'marginalia', 'footnote', 'footnote-continued', 'caption', 'endnote', 'footer','keynote']
        
        if not Path(model_path).is_dir():
            LOG.error("""\
                Block Segmentation model was not found at '%s'. Make sure the `model_path` parameter
                points to the local model path.

                model can be downloaded from http://url
                """ % model_path)
            sys.exit(1)
            
        config = InferenceConfig()
        mrcnn_model = model.MaskRCNN(mode="inference", model_dir=str(model_path), config=config)
        mrcnn_model.load_weights(str(model_weights), by_name=True)

        oplevel = self.parameter['operation_level']
        for (n, input_file) in enumerate(self.input_files):
            
            pcgts = page_from_file(self.workspace.download_file(input_file))
            page = pcgts.get_Page()
            page_id = input_file.pageId or input_file.ID 
            
#             fname = pcgts.get_Page().imageFilename
#             LOG.info("INPUT FILE %s", fname)

            
#             file_name=fname.split(".tif")[0]
            
            #code added for workspace
            page_image, page_xywh, page_image_info = self.workspace.image_from_page(page, page_id) 

            
            if oplevel=="page":
                self._process_segment(page_image, page, page_xywh, page_id, input_file, n, mrcnn_model,class_names)
            else:
                LOG.warning('Operation level %s, but should be "page".', oplevel)
                break
            file_id = input_file.ID.replace(self.input_file_grp, self.output_file_grp)

            # Use input_file's basename for the new file -
            # this way the files retain the same basenames:
            if file_id == input_file.ID:
                file_id = concat_padded(self.output_file_grp, n)
            self.workspace.add_file(
                ID=file_id,
                file_grp=self.output_file_grp,
                pageId=input_file.pageId,
                mimetype=MIMETYPE_PAGE,
                local_filename=os.path.join(self.output_file_grp,
                                            file_id + '.xml'),
                content=to_xml(pcgts).encode('utf-8')
            )

    def _process_segment(self,page_image, page, page_xywh, page_id, input_file, n, mrcnn_model,class_names):
        
        img_array = ocrolib.pil2array(page_image)
        results = mrcnn_model.detect([img_array], verbose=1)    
        r = results[0]        
        for i in range(len(r['rois'])):                
            LOG.info("Block Class: %s", class_names[i])            
            min_x = r['rois'][i][0]
            min_y = r['rois'][i][1]
            max_x = r['rois'][i][2]
            max_y = r['rois'][i][3]
            
            page_xywh['features'] += ',blksegmented'
            
            region_img = img_array[min_x:max_x,min_y:max_y] #extract from points and img_array
            region_img = ocrolib.array2pil(region_img)
            file_id = input_file.ID.replace(self.input_file_grp, self.image_grp)
            if file_id == input_file.ID:
                file_id = concat_padded(self.image_grp, n)
                
            
            file_path = self.workspace.save_image_file(region_img,
                                   file_id+"_"+str(i),
                                   page_id=page_id,
                                   file_grp=self.image_grp)        
            ai = AlternativeImageType(filename=file_path, comments=page_xywh['features'])
            coords = CoordsType("%i,%i %i,%i %i,%i %i,%i" % (
            min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y))
            textregion = TextRegionType(Coords=coords, type_=class_names[r['class_ids'][i]])
            textregion.add_AlternativeImage(ai)
            page.add_TextRegion(textregion)
        
