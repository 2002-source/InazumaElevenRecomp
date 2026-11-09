#!/usr/bin/env python3
"""
Desensambla codigo ARM del juego a partir de los binarios extraidos.

Uso (desde C:/dev/ie1recomp):
  python scripts/desensamblar.py 0x02009BE0            ARM9 principal / ITCM
  python scripts/desensamblar.py 0x021306E0 --ov 15    dentro del overlay 15
  python scripts/desensamblar.py 0x02009BE0 --n 120    mas instrucciones
Imprime hasta encontrar el final de la funcion (ldm ...pc / bx lr) o --n.
"""
import argparse, json, os, struct

IMG = "images"


def cargar(ov, cap=None):
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
    arm9 = open(os.path.join(IMG, "arm9.bin"), "rb").read()
    imgs = [(int(info["arm9"]["ram_address"], 16), arm9)]
    for a in info["autoloads"]:
        off = int(a["origen_en_arm9"], 16)
        imgs.append((int(a["destino"], 16), arm9[off:off + a["tamano"]]))
    if ov is not None:
        o = [x for x in info["overlays_arm9"] if x["id"] == ov][0]
        data = open(os.path.join(IMG, "overlays", f"ov9_{ov:03d}.bin"), "rb").read()
        imgs.insert(0, (int(o["ram_address"], 16), data))
    if cap:
        data = open(cap, "rb").read()
        base = int(os.path.basename(cap).split("_")[1].split(".")[0], 16)
        imgs.insert(0, (base, data))
    return imgs


IMGS = []


def w(a):
    for base, data in IMGS:
        if base <= a and a + 4 <= base + len(data):
            return struct.unpack_from("<I", data, a - base)[0]
    return None


COND=['eq','ne','cs','cc','mi','pl','vs','vc','hi','ls','ge','lt','gt','le','','nv']
OPS=['and','eor','sub','rsb','add','adc','sbc','rsc','tst','teq','cmp','cmn','orr','mov','bic','mvn']
def reg(r): return {13:'sp',14:'lr',15:'pc'}.get(r,'r%d'%r)
def rl(m): return '{'+','.join(reg(i) for i in range(16) if m>>i&1)+'}'
def sh(i):
    rm=i&15; t=(i>>5)&3
    if i>>4&1: return '%s,%s %s'%(reg(rm),['lsl','lsr','asr','ror'][t],reg(i>>8&15))
    amt=i>>7&31
    return reg(rm)+('' if amt==0 and t==0 else ', %s #%d'%(['lsl','lsr','asr','ror'][t],amt))
def dis(addr,i):
    c=COND[i>>28]
    if (i&0x0FFFFFF0)==0x012FFF10: return 'bx%s %s'%(c,reg(i&15))
    if (i&0x0FFFFFF0)==0x012FFF30: return 'blx%s %s'%(c,reg(i&15))
    if (i&0x0FB00FF0)==0x01000000: return 'mrs %s'%reg(i>>12&15)
    if (i&0x0FB0FFF0)==0x0120F000: return 'msr cpsr, %s'%reg(i&15)
    if (i&0x0E000000)==0x0A000000:
        off=((i&0xFFFFFF)^0x800000)-0x800000
        return ('bl' if i>>24&1 else 'b')+c+' 0x%08X'%(addr+8+off*4)
    if (i&0x0E000000)==0x08000000:
        L=i>>20&1; return ('ldm' if L else 'stm')+c+['da','ia','db','ib'][i>>23&3]+' %s%s, %s'%(reg(i>>16&15),'!' if i>>21&1 else '',rl(i&0xFFFF))
    if (i&0x0C000000)==0x04000000:
        L=i>>20&1;B=i>>22&1;U=i>>23&1;P=i>>24&1;W=i>>21&1;rn=i>>16&15;rd=i>>12&15
        off=('#%s0x%X'%('' if U else '-',i&0xFFF)) if not (i>>25&1) else (('' if U else '-')+sh(i))
        s=(('ldr' if L else 'str')+c+('b' if B else '')+' %s, [%s, %s]%s'%(reg(rd),reg(rn),off,'!' if W else '')) if P else (('ldr' if L else 'str')+c+('b' if B else '')+' %s, [%s], %s'%(reg(rd),reg(rn),off))
        if rn==15 and P and not (i>>25&1):
            t=addr+8+((i&0xFFF) if U else -(i&0xFFF)); v=w(t); s+=('  ; =0x%08X'%v) if v is not None else ''
        return s
    if (i&0x0FC000F0)==0x00000090: return ('mla' if i>>21&1 else 'mul')+c+' %s, %s, %s'%(reg(i>>16&15),reg(i&15),reg(i>>8&15))
    if (i&0x0E000090)==0x00000090:
        L=i>>20&1; return ('ldr' if L else 'str')+'h/sb/sh %s,[%s,...] (%08X)'%(reg(i>>12&15),reg(i>>16&15),i)
    if (i&0x0C000000)==0x00000000:
        op=OPS[i>>21&15]; S=i>>20&1; rn=reg(i>>16&15); rd=reg(i>>12&15)
        if i>>25&1:
            rot=(i>>8&15)*2; v=i&0xFF; v=((v>>rot)|(v<<(32-rot)))&0xFFFFFFFF; o2='#0x%X'%v
        else: o2=sh(i)
        if op in('tst','teq','cmp','cmn'): return '%s%s %s, %s'%(op,c,rn,o2)
        if op in('mov','mvn'): return '%s%s%s %s, %s'%(op,c,'s' if S else '',rd,o2)
        return '%s%s%s %s, %s, %s'%(op,c,'s' if S else '',rd,rn,o2)
    return '??? %08X'%i


def main():
    global IMGS
    ap = argparse.ArgumentParser()
    ap.add_argument("addr")
    ap.add_argument("--ov", type=int)
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--cap", help="imagen capturada, p. ej. images/capturas/cap_02174000.bin")
    ap.add_argument("--quien-llama", action="store_true",
                    help="lista las instrucciones BL que llaman a esa direccion")
    ap.add_argument("--inicio", action="store_true",
                    help="retrocede hasta el inicio de la funcion (push ...lr)")
    a = ap.parse_args()
    IMGS = cargar(a.ov, a.cap)
    pc = int(a.addr, 16)
    if a.quien_llama:
        for base, data in IMGS:
            for off in range(0, len(data) - 3, 4):
                i = struct.unpack_from("<I", data, off)[0]
                if (i & 0x0F000000) == 0x0B000000:          # BL
                    o = ((i & 0xFFFFFF) ^ 0x800000) - 0x800000
                    if base + off + 8 + o * 4 == pc:
                        print(f"{base + off:08X}  BL {pc:08X}")
        return
    if a.inicio:
        p = pc
        while p > pc - 0x800:
            i = w(p)
            if i is not None and (i & 0xFFFF4000) == 0xE92D4000:
                break
            p -= 4
        print(f"(inicio de la funcion: {p:08X})")
        pc = p
    for _ in range(a.n):
        i = w(pc)
        if i is None:
            print(f"{pc:08X}  (fuera de los binarios cargados; usa --ov N si es un overlay)")
            return
        print(f"{pc:08X}  {i:08X}  {dis(pc, i)}")
        if (i & 0xFFFF8000) == 0xE8BD8000 or i == 0xE12FFF1E:
            return
        pc += 4


if __name__ == "__main__":
    main()
