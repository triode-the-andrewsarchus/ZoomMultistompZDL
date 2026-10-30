#!/usr/bin/env python3
"""Author original Plus-native pixel icons; no factory pixels or MIDI access."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from upstream import ROOT

# Body colour, title lines and a distinct motif inspired by each old design.
DESIGNS = {
 'arrakis': (0, ['ARRAKIS'], 'wave', 'dunes'),
 'breather': (1, ['BREATHER'], 'wave', 'breath'),
 'corrupt': (0, ['CORRUPT'], 'blocks', 'glitch'),
 'dirtbox': (0, ['DIRT', 'BOX'], 'wave', 'square'),
 'dissolve': (1, ['DISSOLVE'], 'blocks', 'dissolve'),
 'dualshft': (1, ['DUAL', 'SHIFT'], 'wave', 'dual'),
 'dubsiren': (0, ['DUB', 'SIREN'], 'radial', 'siren'),
 'dustbox': (0, ['DUSTBOX'], 'wave', 'octave'),
 'eugate': (1, ['EUCLID', 'GATE'], 'radial', 'euclid'),
 'flower': (1, ['FLOWER'], 'radial', 'flower'),
 'formant': (1, ['CHORAL'], 'radial', 'voices'),
 'galactic': (0, ['GALACTIC'], 'radial', 'orbit'),
 'genloss': (0, ['GEN', 'LOSS'], 'tape', 'broken'),
 'griddly': (1, ['GRID', 'DELAY'], 'blocks', 'grid'),
 'gyre': (0, ['GYRE'], 'radial', 'spiral'),
 'howl': (0, ['HOWL'], 'radial', 'rings'),
 'hydra': (0, ['HYDRA'], 'wave', 'hydra'),
 'klang': (1, ['KLANG'], 'radial', 'rings'),
 'mangle': (0, ['MANGLE'], 'wave', 'mangle'),
 'microloom': (1, ['MICRO', 'LOOM'], 'blocks', 'weave'),
 'oxide': (0, ['OXIDE'], 'tape', 'oxide'),
 'rewire': (0, ['REWIRE'], 'blocks', 'routing'),
 'rooms': (1, ['ROOMS'], 'room', 'room'),
 'scorch': (0, ['SCORCH'], 'blocks', 'bolt'),
 'scrub': (1, ['SCRUB'], 'tape', 'scrub'),
 'sgnl': (0, ['S.GN_L'], 'blocks', 'signal'),
 'shatter': (1, ['SHATTER'], 'blocks', 'shatter'),
 'spiral': (1, ['SPIRAL'], 'radial', 'spiral'),
 'spool': (1, ['SPOOL'], 'tape', 'spool'),
 'stasis': (0, ['STASIS'], 'wave', 'freeze'),
 'sweep': (1, ['SWEEP'], 'wave', 'sweep'),
 'synceq': (1, ['SYNC', 'EQ'], 'blocks', 'eq'),
 'taffy': (1, ['TAFFY'], 'wave', 'stretch'),
 'wavefold': (0, ['WAVE', 'FOLD'], 'blocks', 'cascade'),
}


def wave(draw, box, colour, kind):
    x0, y0, x1, y1 = box
    height = y1-y0
    for row in range(2 if kind in ('dual', 'hydra', 'octave') else 1):
        points = []
        for x in range(x0, x1+1):
            t = (x-x0)/(x1-x0)
            phase = t*math.pi*(4 if row == 0 else 7)
            value = math.sin(phase)
            if kind in ('square', 'octave', 'freeze'):
                value = 1 if value > 0 else -1
            if kind in ('sweep', 'stretch'):
                value = math.sin(phase*(.3+t*2))
            if kind in ('mangle', 'breath'):
                value *= .2+.8*abs(math.sin(t*math.pi*3))
            if kind == 'dunes':
                value = math.sin(t*math.pi*3)+.3*math.sin(t*math.pi*8)
            center = y0+height*(.32+.36*row) if row or kind in ('dual', 'hydra', 'octave') else (y0+y1)/2
            points.append((x, round(center+height*.27*value)))
        draw.line(points, fill=colour, width=2)
    if kind == 'freeze':
        draw.rectangle((x1-11,y0,x1-8,y1),fill=colour)
        draw.rectangle((x1-5,y0,x1-2,y1),fill=colour)


def radial(draw, box, colour, kind):
    x0,y0,x1,y1=box
    cx,cy=(x0+x1)/2,(y0+y1)/2
    r=min((y1-y0)/2,(x1-x0)/4)
    if kind in ('flower','voices','euclid','siren'):
        count={'flower':6,'voices':5,'euclid':8,'siren':4}[kind]
        for n in range(count):
            angle=2*math.pi*n/count
            x=cx+(r*.65 if kind!='voices' else (n-2)*r)*math.cos(angle)
            y=cy+r*.65*math.sin(angle)
            radius=max(2,r*.45)
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),outline=colour,width=2)
        draw.ellipse((cx-2,cy-2,cx+2,cy+2),fill=colour)
    elif kind=='spiral':
        points=[]
        for n in range(140):
            t=n/139; angle=t*math.pi*7
            points.append((cx+math.cos(angle)*t*r*2,cy+math.sin(angle)*t*r))
        draw.line(points,fill=colour,width=2)
    else:
        for scale in (.35,.65,1):
            draw.ellipse((cx-r*2*scale,cy-r*scale,cx+r*2*scale,cy+r*scale),outline=colour)
        if kind=='orbit':
            for x,y in ((x0+3,y0+3),(x1-4,y1-3),(x1-10,y0+2)):
                draw.line((x-2,y,x+2,y),fill=colour)
                draw.line((x,y-2,x,y+2),fill=colour)


def tape(draw, box, colour, kind):
    x0,y0,x1,y1=box; cy=(y0+y1)/2; r=max(3,(y1-y0)/2-1)
    for cx in (x0+r+2,x1-r-2):
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=colour,width=2)
        for n in range(3):
            a=n*math.pi*2/3
            draw.line((cx,cy,cx+math.cos(a)*r*.75,cy+math.sin(a)*r*.75),fill=colour,width=2)
    draw.line((x0+r*2+2,cy,x1-r*2-2,cy),fill=colour,width=2)
    if kind in ('broken','oxide'):
        for n in range(9):
            x=round(x0+(x1-x0)*(.2+.07*n));y=round(y0+(n*7%max(1,int(y1-y0))))
            draw.rectangle((x,y,x+1,y+1),fill=colour)
    if kind=='scrub':
        draw.polygon(((x0+3,cy),(x0+10,cy-4),(x0+10,cy+4)),fill=colour)


def blocks(draw, box, colour, kind):
    x0,y0,x1,y1=box; w=x1-x0;h=y1-y0
    if kind=='bolt':
        draw.polygon(((x0+w*.48,y0),(x0+w*.2,y0+h*.6),(x0+w*.45,y0+h*.6),
                      (x0+w*.32,y1),(x0+w*.8,y0+h*.35),(x0+w*.57,y0+h*.35),(x0+w*.7,y0)),fill=colour)
    elif kind in ('eq','signal'):
        for n in range(9):
            top=y0+h*(.15+(n*7%9)/12)
            x=x0+n*w/9
            draw.rectangle((x,top,x+w/14,y1),fill=colour)
    elif kind in ('routing','cascade'):
        count=5 if kind=='cascade' else 3; size=min(h-2,w/count-4)
        cy=(y0+y1)/2
        draw.line((x0,cy,x1,cy),fill=colour)
        for n in range(count):
            cx=x0+(n+.5)*w/count
            draw.rectangle((cx-size/2,cy-size/2,cx+size/2,cy+size/2),fill=1-colour,outline=colour)
            draw.line((cx-size*.3,cy,cx,cy-size*.3,cx+size*.3,cy+size*.3),fill=colour)
    else:
        for row in range(4):
            for col in range(13):
                if kind=='dissolve' and (col+row*3)%13<col*.8:
                    continue
                if kind in ('glitch','shatter') and (row*7+col*3)%5<2:
                    continue
                x=x0+col*w/13;y=y0+row*h/4
                draw.rectangle((x,y,x+max(1,w/13-2),y+max(1,h/4-2)),outline=colour,
                               fill=colour if kind in ('dissolve','glitch') else None)


def room(draw, box, colour, kind):
    x0,y0,x1,y1=box; dx=(x1-x0)*.2;dy=(y1-y0)*.22
    draw.rectangle(box,outline=colour)
    inner=(x0+dx,y0+dy,x1-dx,y1-dy);draw.rectangle(inner,outline=colour)
    for a,b in zip(((x0,y0),(x1,y0),(x0,y1),(x1,y1)),
                   ((inner[0],inner[1]),(inner[2],inner[1]),(inner[0],inner[3]),(inner[2],inner[3]))):
        draw.line((*a,*b),fill=colour)


def render(name, size, font_path):
    width,height=size; bg,lines,motif,kind=DESIGNS[name]; fg=1-bg
    image=Image.new('1',size,1);draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((1,1,width-2,height-2),radius=3,fill=bg,outline=0,width=2)
    cy=round(height*.26);radius=round(width*.085)
    draw.ellipse((width//2-3,6,width//2+3,12),fill=fg)
    for n in range(4):
        cx=round((n+.5)*width/4)
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=fg)
        draw.ellipse((cx-radius+2,cy-radius+2,cx+radius-2,cy+radius-2),fill=bg,outline=bg)
        draw.line((cx,cy-radius+3,cx,cy),fill=fg,width=2)
    top=round(height*.43);bottom=height-25
    draw.line((3,top-3,width-4,top-3),fill=fg)
    # Typeset directly at each icon's native resolution; never resize text.
    y=top+1
    gap=1 if width<90 else 2
    font_size=round(width*(.195 if len(lines)>1 else .225))
    while font_size>=7:
        font=ImageFont.truetype(str(font_path),font_size)
        heights=[draw.textbbox((0,0),label,font=font)[3]-draw.textbbox((0,0),label,font=font)[1] for label in lines]
        fits=all(draw.textlength(label,font=font)<=width-9 for label in lines)
        if fits and sum(heights)+gap*len(lines)<=bottom-top-10:
            break
        font_size-=1
    if font_size<7:raise ValueError('Title cannot fit at a legible native size')
    for label in lines:
        bounds=draw.textbbox((0,0),label,font=font)
        draw.text(((width-draw.textlength(label,font=font))/2,y-bounds[1]),label,fill=fg,font=font)
        y+=bounds[3]-bounds[1]+gap
    box=(7,y+2,width-8,bottom)
    if box[3]-box[1]<3:raise ValueError('Title leaves no space for its illustration')
    {'wave':wave,'radial':radial,'tape':tape,'blocks':blocks,'room':room}[motif](draw,box,fg,kind)
    cx=width//2;cy=height-12;r=round(width*.078)
    points=[(cx+math.cos(math.pi/8+n*math.pi/4)*r,cy+math.sin(math.pi/8+n*math.pi/4)*r) for n in range(8)]
    draw.polygon(points,fill=bg,outline=fg,width=2)
    draw.ellipse((cx-r+3,cy-r+3,cx+r-3,cy+r-3),outline=fg)
    return image


def main():
    output=ROOT/'src/msplus/artwork/native';output.mkdir(exist_ok=True)
    font=Path(subprocess.check_output(['fc-match','-f','%{file}','DejaVu Sans:style=Condensed Bold'],text=True))
    records={}
    for name in DESIGNS:
        for size in ((72,97),(102,128)):
            path=output/f'{name}-{size[0]}x{size[1]}.png'
            render(name,size,font).save(path)
            records[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (output/'designs.json').write_text(json.dumps(dict(designs=DESIGNS,font=font.name,
        font_sha256=hashlib.sha256(font.read_bytes()).hexdigest(),png_sha256=records),indent=2)+'\n')
    print('Authored 68 original icons at their native Plus dimensions.')


if __name__=='__main__':main()
