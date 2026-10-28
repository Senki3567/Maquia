"""Union the overlapping cloud contours before using them as an ASS clip.
ASS vector clips treat overlapping contours differently from filled drawings.
GEOS produces disjoint outer rings, avoiding false holes through the letters.
Bezier sampling: 16 samples/quarter; coordinate rounding 0.1 native pixel.
"""
import ctypes as C
import ctypes.util
import re

lib=C.CDLL(ctypes.util.find_library('geos_c') or 'libgeos_c.so.1')
for name,args,result in [
 ('initGEOS',[C.c_void_p,C.c_void_p],None),
 ('GEOSWKTReader_create',[],C.c_void_p),
 ('GEOSWKTReader_read',[C.c_void_p,C.c_char_p],C.c_void_p),
 ('GEOSUnaryUnion',[C.c_void_p],C.c_void_p),
 ('GEOSWKTWriter_create',[],C.c_void_p),
 ('GEOSWKTWriter_setRoundingPrecision',[C.c_void_p,C.c_int],None),
 ('GEOSWKTWriter_write',[C.c_void_p,C.c_void_p],C.c_void_p),
 ('GEOSGeom_destroy',[C.c_void_p],None),
 ('GEOSFree',[C.c_void_p],None),
]:
 fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
lib.initGEOS(None,None)
reader=lib.GEOSWKTReader_create();writer=lib.GEOSWKTWriter_create()
lib.GEOSWKTWriter_setRoundingPrecision(writer,1)

def union_clip(path):
    if not path:return ''
    polygons=[]
    for contour in re.findall(r'm\s+([^m]+)',path):
        n=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',contour)))
        pts=list(zip(n[::2],n[1::2]));out=[pts[0]]
        for i in range(1,len(pts),3):
            a=out[-1];b,c,d=pts[i:i+3]
            for j in range(1,17):
                t=j/16;v=1-t
                out.append((v**3*a[0]+3*v*v*t*b[0]+3*v*t*t*c[0]+t**3*d[0],v**3*a[1]+3*v*v*t*b[1]+3*v*t*t*c[1]+t**3*d[1]))
        out[-1]=out[0]
        polygons.append('(('+','.join(f'{x:.4f} {y:.4f}' for x,y in out)+'))')
    geom=lib.GEOSWKTReader_read(reader,('MULTIPOLYGON ('+','.join(polygons)+')').encode())
    if not geom:raise ValueError('Cannot parse cloud geometry')
    merged=None;data=None
    try:
        merged=lib.GEOSUnaryUnion(geom)
        if not merged:raise ValueError('Cannot union cloud geometry')
        data=lib.GEOSWKTWriter_write(writer,merged)
        if not data:raise ValueError('Cannot export cloud clip')
        wkt=C.string_at(data).decode()
        rings=re.findall(r'\(([^()]+)\)',wkt)
        return ' '.join('m '+ring.replace(',',' l ') for ring in rings)
    finally:
        if data:lib.GEOSFree(data)
        if merged:lib.GEOSGeom_destroy(merged)
        lib.GEOSGeom_destroy(geom)
