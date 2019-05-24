import builtins as python
import random as pyrandom
import sys,os,re,glob,argparse,codecs
from pylab import median, imread

from PIL import Image
import ocrolib
from ocrolib import hocr
from re import split
from ParserAnybaseocr import *

# limits
#parser.add_argument('--minscale',type=float,default=8.0,
#                    help='minimum scale permitted (%(default)s)') # default was 12.0, Ajraf, Mohsin and Saqib chnaged it into 8.0


def addzeros(file):
	F = open(file, "r")
	D = F.read()
	D = split("\n", D)
	D = D[:-1]
	F.close()
	F = open(file, "w")
	for d in D:
		d += " 0 0 0 0\n"
		F.write(d)

def textline(arg):
	image = ocrolib.read_image_binary(arg)
	height, width = image.shape
	H = height
	W = width
	base,_ = ocrolib.allsplitext(arg)
	base2 = os.path.splitext(arg)[0]

	if not os.path.exists("%s/lines" % base) :
		os.system("mkdir -p %s/lines" % base)
		#if os.path.exists(base2 + ".ts.png") :
		#    f = ocrolib.read_image_binary(base2 + ".ts.png")
		#    height, width = f.shape
		#    os.system("python "+args.libpath+"/anyBaseOCR-nlbin.py %s.pf.bin.png" % base2)
		#else:
		#    os.system("python "+args.libpath+"/anyBaseOCR-nlbin.py %s" % arg)
		#print("convert %s.ts.png %s/block-000.bin.png" % (base,base))
		#os.system("convert %s.ts.png %s/block-000.bin.png" % (base,base))
		#os.system("rm %s.bin.png %s.nrm.png" % (base, base))
		file = open('%s/sorted_cuts.dat' % base, 'w')
		l = "0 0 " + str(int(width)) + " " + str(int(height)) + " 0 0 0 0\n"
		file.write(l)
		file.close()

	#if not os.path.exists("%s/lines" % base) :
	#    os.system("mkdir %s/lines" % base)

	blockarray = []
	if os.path.exists(base + "/sorted_cuts.dat") :
		blocks = open(base + "/sorted_cuts.dat", "r")
		i = 0
		for block in blocks:
			words = block.split()
			blockarray.append((int(words[0]), -int(words[1]),int(words[2]), int(words[3]), i))
			i += 1;
	else:
		blockarray.append((0, 0, width, height, 0))

	i = 0
	j = 0
	lines=[]
	for block in blockarray:
		(x0, y0, x1, y1, i) = block
		y0 = -y0
		#blockImage = "%s/block-%03d" % (base, i)
		os.system("convert %s.ts.png %s/temp.png" % (base, base))
		img = Image.open("%s.ts.png" % base, 'r')
		img_w, img_h = img.size
		background = Image.new('RGBA', (W, H), (255, 255, 255, 255))
		bg_w, bg_h = background.size
		offX = (bg_w - img_w) // 2
		offY = (bg_h - img_h) // 2
		offset = (offX, offY)
		background.paste(img, offset)
		background.save("%s/temp.png" % base)
		command = "python "+args.libpath+"/anyBaseOCR-gpageseg.py %s/temp.png -n --minscale %f --maxlines %f --scale %f --hscale %f --vscale %f --threshold %f --noise %d --maxseps %d --sepwiden %d --maxcolseps %d --csminaspect %f --csminheight %f -p %d -e %d -Q %d" % (base, args.minscale, args.maxlines, args.scale, args.hscale, args.vscale, args.threshold, args.noise, args.maxseps, args.sepwiden, args.maxcolseps, args.csminaspect, args.csminheight, args.pad, args.expand, args.parallel)
		if(args.blackseps):
			command = command + " -b"
		if(args.usegauss):
			command = command + " --usegauss"
		os.system(command)
		pseg = ocrolib.read_page_segmentation("%s/temp.pseg.png" % base)
		regions = ocrolib.RegionExtractor()
		regions.setPageLines(pseg)
		file = open('%s/sorted_lines.dat' % base, 'w')
		for h in range(1,regions.length()):
			id = regions.id(h)
			y0,x0,y1,x1 = regions.bbox(h)
			l = str(int(x0 - offX)) + " " + str(int(img_h - (y1 - offY))) + " " + str(int(x1 - offX)) + " " + str(int(img_h - (y0 - offY))) + " 0 0 0 0\n"
			file.write(l)
		filelist = glob.glob("%s/temp/*" % base)
		for infile in sorted(filelist): 
			os.system("convert %s %s/lines/01%02x%02x.bin.png" % (infile, base, i + 1, j + 1))
			lines.append("%s/lines/01%02x%02x.bin.png" % (base, i + 1, j + 1))
			j += 1
		os.system("rm -r %s/temp/" % base)
		os.system("rm %s/temp.png %s/temp.pseg.png" % (base, base))
		i += 1
	return lines


if __name__ == "__main__":
	myparser = ParserAnybaseocr()
	args = myparser.get_parameters('ocrd-anybaseocr-textline')

	files = myparser.parseXML()
	fname = []
	block=[]
	for i, f in enumerate(files):
		myparser.print_info("Process file: %s" % str(f))
		block.append(textline(str(f)))
		fname.append(str(f))

	myparser.write_to_xml(fname, 'TL_', block)