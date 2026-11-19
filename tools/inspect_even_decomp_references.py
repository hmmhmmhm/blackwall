"""Audit pinned G1 references and limited source overlap with G2 g2flash; no device operations."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
PIN='f571782aedb6fdefbcbfe2a4d1e309bb47143581'
G2_PIN='845f665e0dfdcfd06b7d3a294388de6f17a5bd59'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;r=s/'even-decomp-research-01';src=r/'source';manifest=json.loads((r/'sources.json').read_text());tree=json.loads((r/'tree.json').read_text())['tree'];checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 check('pinned-commit',manifest['commit']==PIN and not manifest['executed_upstream_code'])
 check('archive-pin',hashlib.sha256((r/'snapshot.tar.gz').read_bytes()).hexdigest()==manifest['archive_sha256'])
 for item in manifest['files']:
  raw=(src/item['path']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  check(item['path']+'-pin',hashlib.sha256(raw).hexdigest()==item['sha256'] and blob==item['git_blob']==next(x['sha'] for x in tree if x['path']==item['path']))
 read=lambda n:(src/n).read_text()
 check('G1-target','Even Realities G1' in read('README.md'))
 check('nrf5340-source-context','nRF5340' in read('helpers/ai/function_discovery_workflow.md'))
 check('sample-only-build','src/app/sample_main.c' in read('CMakeLists.txt') and 'src/app/main.c' not in read('CMakeLists.txt'))
 check('linux-helper-not-apollo','<linux/spi/spidev.h>' in read('src/app/jdb013vga/hal_driver.c'))
 check('pointer-size-transfer-length','transfer[0].len = sizeof(param);' in read('src/app/jdb013vga/hal_driver.c'))
 rootlicenses=[x['path'] for x in tree if x['type']=='blob' and '/' not in x['path'] and re.search(r'license|copying|notice',x['path'],re.I)]
 check('no-root-license-found',not rootlicenses)
 g2=s/'upstream/g2flash-845f665';head=subprocess.run(['git','-C',str(g2),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip();check('g2-pinned-commit',head==G2_PIN)
 g2_sources=[]
 for name in ['patches/panel.c','patches/draw.c','patches/zlib_glue.c']:
  raw=(g2/name).read_bytes();original=subprocess.run(['git','-C',str(g2),'show',G2_PIN+':'+name],capture_output=True,check=True).stdout
  check(name+'-commit-bytes',raw==original);g2_sources.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),git_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()))
 panel=(g2/'patches/panel.c').read_text();header=read('src/app/jdb013vga/jbd013_api.h');defines={n:int(v,0) for n,v in re.findall(r'^#define\s+(SPI_\w+)\s+(0x[0-9a-fA-F]+)',header,re.M)}
 literal_calls={int(v,0) for v in re.findall(r'panel_(?:read|write)\((0x[0-9a-fA-F]+|\d+),',panel)}
 names=['SPI_SYNC','SPI_DISPLAY_ENABLE','SPI_WR_ENABLE','SPI_RD_STATUS_REG1','SPI_RD_STATUS_REG2','SPI_RD_LUM_REG','SPI_RD_CURRENT_REG','SPI_RD_ID']
 matched=[]
 for name in names:
  check(name+'-G2-source-overlap',defines[name] in literal_calls);matched.append(dict(name=name,opcode=defines[name]))
 check('G1-id-read3','spi_rx_frame(SPI_RD_ID, pBuf, 3)' in read('src/app/jdb013vga/jbd013_api.c'))
 check('G2-id-read4','panel_read(0x9f,id,4,0)' in panel)
 check('G1-4bpp-loop','param_6 << 4' in read('src/app/gui_bitmap_draw.c') and 'param_1 / 2' in read('src/app/gui_bitmap_draw.c'))
 glue=(g2/'patches/zlib_glue.c').read_text();check('G2-raw-panel-definitions','#define PANEL_W 640u' in glue and '#define PANEL_H 480u' in glue and '#define PANEL_STRIDE (PANEL_W / 2u)' in glue)
 result=dict(passed=True,count=len(checks),checks=checks,repository=manifest['repository'],commit=PIN,selected_files=len(manifest['files']),matched_opcode_candidates=matched,g2_commit=G2_PIN,physical_validated=False,wire_compatibility_verified=False,build_verified=False,license_scope='root project license not found; isolated SPDX/nested license not treated as whole-repository permission',recommendation='Use G1 naming/call-graph and panel-format hypotheses; validate against pinned G2 ARM or g2flash before implementing; do not reuse peripheral addresses, OTA, generated memory map or Linux helper code')
 result['g2_sources']=g2_sources
 a.output.mkdir(mode=0o700);(a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),matched=len(matched),files=len(manifest['files']))))
if __name__=='__main__':main()
