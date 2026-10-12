"""Render the actual enclosure solids and the board component envelopes."""
import json
import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mechanical import CAD, OUT, PLACEMENT, W,D,H

def mesh(ax,shape,color,alpha=1,offset=(0,0,0)):
    vertices,faces=shape.tessellate(.25,.2)
    points=[(v.x+offset[0],v.y+offset[1],v.z+offset[2]) for v in vertices]
    ax._faces.extend([[points[i] for i in face] for face in faces]);ax._colors.extend([color]*len(faces))

def block(ax,x,y,z,w,d,h,color):
    p=[(x,y,z),(x+w,y,z),(x+w,y+d,z),(x,y+d,z),(x,y,z+h),(x+w,y,z+h),(x+w,y+d,z+h),(x,y+d,z+h)]
    faces=[[p[i] for i in ids] for ids in [(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
    ax._faces.extend(faces);ax._colors.extend([color]*len(faces))

def main():
    fig=plt.figure(figsize=(14,8),facecolor='#edf1f4')
    ax=fig.add_subplot(121,projection='3d');bx=fig.add_subplot(122,projection='3d')
    for a in (ax,bx):a.set_facecolor('#edf1f4');a.set_axis_off();a.view_init(35,-55);a._faces=[];a._colors=[]
    mesh(ax,cq.importers.importStep(str(CAD/'enclosure_base.step')).val(),'#28414c')
    mesh(ax,cq.importers.importStep(str(CAD/'enclosure_lid.step')).val(),'#526975',offset=(0,0,H-3))
    block(ax,59.5,47,73,30.6,17,.4,'#0d1d26')
    mesh(ax,cq.Workplane('YZ').center(96,40).circle(5.5).extrude(4).translate((-3,0,0)).val(),'#f69239')
    for x in (77.25,94.25,111.25):block(ax,x-2.8,85.45,74,5.6,5.6,1,'#f69239')
    ax.text(73,59,75,'7.100 MHz',color='#93f1cf',fontsize=8,ha='center')
    ax.set(xlim=(0,W),ylim=(0,D),zlim=(0,H+10));ax.set_box_aspect((W,D,H+10))
    ax.set_title('Gabinete de bancada • 164 × 120 × 74 mm',fontsize=12,pad=10)
    bounds=json.loads((CAD/'component_envelopes.json').read_text())
    for name,(dx,dy,z) in PLACEMENT.items():
        dz={'control':100,'hf':55}.get(name,0);height=z+dz
        bare=cq.importers.importStep(str(CAD/(name+'_bare_board.step'))).val()
        mesh(bx,bare,'#087c62',offset=(dx,dy,height))
        for part in bounds[name]:
            x,y,pz,w,d,h=part['bbox'];color='#b7ae8c' if part['ref'].startswith('C') else '#303640'
            block(bx,x+dx,y+dy,pz+height,w,d,h,color)
        bx.text(dx+(20 if name.startswith('lpf') else 30),dy-5,height+5,name.upper(),fontsize=8,color='#28414c')
    bx.set(xlim=(0,W),ylim=(0,D+20),zlim=(0,175));bx.set_box_aspect((W,D+20,175))
    bx.set_title('Montagem explodida • envelopes dos componentes',fontsize=12,pad=10)
    for a in (ax,bx):a.add_collection3d(Poly3DCollection(a._faces,facecolors=a._colors,edgecolors='none',zsort='average',rasterized=True))
    fig.suptitle('SKYWAVE SDR / D1',fontsize=23,fontweight='bold',color='#233a46',y=.97)
    fig.text(.5,.045,'ESP32-S3 · OLED · PTT · HF I/Q · VHF/UHF FM modular',ha='center',fontsize=13,color='#36515e')
    fig.text(.5,.015,'Modelo paramétrico de protótipo — encaixes de acessórios e montagem física ainda não ensaiados.',ha='center',fontsize=10,color='#5b6770')
    fig.savefig(OUT/'renders/assembly.png',dpi=170,bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':main()
