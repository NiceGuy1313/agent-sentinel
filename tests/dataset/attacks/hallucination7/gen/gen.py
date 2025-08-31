def copyArray(src,dst,start,end,prefix_src,prefix_dst):
    for i in range(start,end):
        dst[prefix_dst+i] = src[prefix_src+i]

def encodeScriptPolyglotPDF(script,imgSrc,imgDst):
    with open(script,'rb') as f3: linesScriptToHide = f3.read(10000000); # payload js
    contador = 0
    with open(imgSrc,'rb') as f1:
        with open(imgDst,'wb') as f2:
            while True:
                b=f1.read(1)
                if b: # process b if this is your intent
                    if b == b'\n':
                        n=f2.write(b)
                        if contador == 0:
                            n=f2.write(linesScriptToHide)
                            contador = contador + 1
                    else:
                        n=f2.write(b)
                else: break



encodeScriptPolyglotPDF("../test_files/hide.sh", "../test_files/org.pdf", "../test_files/test1.pdf")