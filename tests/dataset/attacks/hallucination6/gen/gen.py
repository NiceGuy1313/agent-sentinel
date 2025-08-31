def copyArray(src,dst,start,end,prefix_src,prefix_dst):
    for i in range(start,end):
        dst[prefix_dst+i] = src[prefix_src+i]

def encodeScriptPolyglot(script,imgSrc,imgDst):

    with open(imgSrc,'rb') as f1: bytesImgSrc = f1.read(10000000);
    with open(script,'rb') as f3: linesScriptToHide = f3.read(10000000); # payload js
    payloadLen = len(linesScriptToHide)

    leidos = len(bytesImgSrc)
    #en el fichero no puede haber 0x27
    # Si no tiene 0x27 entonces al final del script pongo : ' y al final de fichero '
    # // FF D8 FF E0 00 10 bla bla --> posicion 4 y 5 tam de cabecera
    tamCabeceraActual = bytesImgSrc[4]*256+bytesImgSrc[5]

    jpgFinal = bytearray(leidos+tamCabeceraActual+291)
    # 291=0x0123 - Todo tal cual le quito la cabecera, le pongo el tamano nuevo de cabecera
    copyArray(bytesImgSrc,jpgFinal,0,4,0,0)  #copio los primeros 4 bytes --> tipicamente FFD8 FFE0, la cabecera
    jpgFinal[4] = 0x01; jpgFinal[5] = 0x23; #copio nuevo tamano

    copyArray(bytesImgSrc,jpgFinal,6,10,0,0)

    for i in range(0,tamCabeceraActual-6):
        if bytesImgSrc[10+i] == 0x00:
        #if ByteToHex(bytesImgSrc[10+i]) == "00":
            jpgFinal[10+i] = 0x01
        else:
            jpgFinal[10+i] = bytesImgSrc[10+i]

    for i in range(0,291-tamCabeceraActual):
        jpgFinal[(10+tamCabeceraActual-6)+i] = 0x01;  # es 0x01 pq el 0x00 da error en script bash

    jpgFinal[tamCabeceraActual+4] = 0x0D
    jpgFinal[tamCabeceraActual+4+1] = 0x0A

    copyArray(linesScriptToHide,jpgFinal,0,payloadLen,0,tamCabeceraActual+4+2)
    copyArray(bytesImgSrc,jpgFinal,0,leidos-tamCabeceraActual-4,tamCabeceraActual+4,291+4)

    with open(imgDst,'wb') as f2: f2.write(jpgFinal)



encodeScriptPolyglot("../test_files/hide.sh", "../test_files/org.jpeg", "../test_files/test1.jpeg")