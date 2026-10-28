"""Read/write ASS Fonts blocks without mistaking uuencoded '[' for a section.
Font data occupies ASCII 33..96, so a bare line starting '[' is not a delimiter.
"""
import re
from pack_shape_glyphs import encode_ass,decode_ass
HEADER=re.compile(rb'(?m)^\[(?:Script Info|Aegisub Project Garbage|V4\+? Styles|Events|Fonts|Graphics|Aegisub Extradata)\][ \t]*\r?\n')
FONT=re.compile(rb'(?m)^fontname: ([^\r\n]+)\r?\n')
def section_span(blob):
 headers=list(HEADER.finditer(blob));matches=[i for i,m in enumerate(headers)if m[0].strip()==b'[Fonts]'];assert len(matches)==1,'Expected one Fonts section';i=matches[0];return headers[i].end(),headers[i+1].start()if i+1<len(headers)else len(blob)
def blocks(blob):
 start,end=section_span(blob);found=list(FONT.finditer(blob,start,end));out=[]
 for i,m in enumerate(found):
  z=found[i+1].start()if i+1<len(found)else end;out.append((m[1].decode(),m.start(),m.end(),z))
 return out
def read_fonts(blob):
 return {name:decode_ass(blob[body:end].decode())for name,start,body,end in blocks(blob)}
def replace_font(blob,name,newname,data):
 found=[v for v in blocks(blob)if v[0]==name];assert len(found)==1,(name,'Expected one attachment');_,start,body,end=found[0];nl=b'\r\n'if blob[body-2:body]==b'\r\n'else b'\n';block=b'fontname: '+newname.encode()+nl+encode_ass(data).replace('\n',nl.decode()).encode()+nl+nl;new=blob[:start]+block+blob[end:];fonts=read_fonts(new);assert fonts[newname]==data;return new
def append_font(blob,name,data):
 start,end=section_span(blob);assert name not in read_fonts(blob);nl=b'\r\n'if b'\r\n'in blob[:200]else b'\n';block=b'fontname: '+name.encode()+nl+encode_ass(data).replace('\n',nl.decode()).encode()+nl+nl;new=blob[:end]+block+blob[end:];assert read_fonts(new)[name]==data;return new
