"""Verify first-access abort and absence of later guest side effects in Renode."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--image', default='blackwall-renode:1.17.0-local')
    parser.add_argument('--with-startup-fixtures', action='store_true')
    parser.add_argument('--with-startup-controls', action='store_true')
    parser.add_argument('--with-adc-first-trigger', action='store_true')
    parser.add_argument('--with-adc-enable-latch', action='store_true')
    parser.add_argument('--with-adc-disabled-config', action='store_true')
    parser.add_argument('--with-adc-trigger-config', action='store_true')
    parser.add_argument('--with-adc-power-response', action='store_true')
    parser.add_argument('--with-adc-calibration-control', action='store_true')
    parser.add_argument('--with-adc-info-zero', action='store_true')
    parser.add_argument('--with-info1-fixtures', action='store_true')
    parser.add_argument('--with-prefetch-storage', action='store_true')
    parser.add_argument('--with-buck-status', action='store_true')
    parser.add_argument('--with-buck-response', action='store_true')
    parser.add_argument('--with-mcu-clock-response', action='store_true')
    parser.add_argument('--with-gfx-power-storage', action='store_true')
    parser.add_argument('--with-hfrc-force-control', action='store_true')
    parser.add_argument('--with-gpu-power-preparation', action='store_true')
    parser.add_argument('--with-gpu-power-response', action='store_true')
    parser.add_argument('--with-gpu-interrupt-clear', action='store_true')
    parser.add_argument('--with-gpu-id-initialization', action='store_true')
    parser.add_argument('--with-gpu-ring-configuration', action='store_true')
    parser.add_argument('--with-gpu-identity-response', action='store_true')
    parser.add_argument('--with-gpu-initial-resets', action='store_true')
    parser.add_argument('--with-gpu-raster-init-storage', action='store_true')
    parser.add_argument('--with-gpu-config-response', action='store_true')
    parser.add_argument('--with-gpio-output', action='store_true')
    parser.add_argument('--with-gpio-interrupt-idle', action='store_true')
    parser.add_argument('--with-gpio-config', action='store_true')
    parser.add_argument('--with-gpu-off-sequence', action='store_true')
    parser.add_argument('--with-gpu-power-off', action='store_true')
    parser.add_argument('--with-gpu-initial-status', action='store_true')
    parser.add_argument('--with-memldo-setup', action='store_true')
    parser.add_argument('--with-coreldo-reduction', action='store_true')
    parser.add_argument('--with-buck-start', action='store_true')
    parser.add_argument('--with-buck-override', action='store_true')
    parser.add_argument('--with-mram-control', action='store_true')
    parser.add_argument('--with-hal-storage', action='store_true')
    parser.add_argument('--with-memory-fixtures', action='store_true')
    parser.add_argument('--with-silicon-fixtures', action='store_true')
    parser.add_argument('--case', action='append', help='Run only named cases; repeatable')
    args = parser.parse_args()
    if args.with_adc_first_trigger and not args.with_adc_enable_latch:
        raise ValueError('ADC first trigger tests require enable latch tests')
    if args.with_adc_enable_latch and not (args.with_adc_disabled_config and args.with_adc_trigger_config):
        raise ValueError('ADC enable tests require config bank and timer tests')
    if args.with_adc_disabled_config and not args.with_adc_power_response:
        raise ValueError('ADC disabled config tests require ADC power tests')
    if args.with_adc_trigger_config and not args.with_adc_power_response:
        raise ValueError('ADC trigger tests require ADC power tests')
    if args.with_adc_power_response and not (args.with_gpu_power_off and args.with_adc_calibration_control):
        raise ValueError('ADC power tests require GPU off and ADC calibration control cases')
    if args.with_adc_info_zero and not args.with_info1_fixtures:
        raise ValueError('ADC info tests require Info1 fixtures')
    if args.with_gpio_output and not args.with_gpio_config:
        raise ValueError('GPIO output tests require GPIO config cases')
    if args.with_gpio_interrupt_idle and not args.with_gpio_config:
        raise ValueError('GPIO idle tests require GPIO config cases')
    if args.with_gpu_off_sequence and not args.with_gpu_power_off:
        raise ValueError('GPU off sequence tests require off response tests')
    if args.with_gpu_power_off and not args.with_gpu_initial_status:
        raise ValueError('GPU off tests require initial STATUS tests')
    if args.with_gpu_initial_status and not args.with_gpu_config_response:
        raise ValueError('Initial STATUS cases require CONFIG cases')
    if args.with_gpu_config_response and not args.with_gpu_raster_init_storage:
        raise ValueError('GPU CONFIG cases require raster trace storage')
    if args.with_gpu_raster_init_storage and not args.with_gpu_initial_resets:
        raise ValueError('Raster init storage cases require initial reset cases')
    if args.with_gpu_initial_resets and not args.with_gpu_identity_response:
        raise ValueError('GPU initial reset cases require identity response')
    if args.with_gpu_identity_response and not args.with_gpu_ring_configuration:
        raise ValueError('GPU identity cases require ring configuration')
    if args.with_gpu_ring_configuration and not args.with_gpu_id_initialization:
        raise ValueError('GPU ring cases require ID cases')
    if args.with_gpu_id_initialization and not args.with_gpu_interrupt_clear:
        raise ValueError('GPU ID cases require IRQ clear cases')
    if args.with_gpu_interrupt_clear and not args.with_gpu_power_response:
        raise ValueError('GPU IRQ clear cases require power response')
    if args.with_gpu_power_response and not args.with_gpu_power_preparation:
        raise ValueError('GPU response cases require preparation cases')
    if args.with_gpu_power_preparation and not (args.with_hfrc_force_control and args.with_gfx_power_storage):
        raise ValueError('GPU preparation cases require HFRC and GFX cases')
    if args.with_hfrc_force_control and not args.with_mcu_clock_response:
        raise ValueError('HFRC force cases require MCU clock cases')
    if args.with_gfx_power_storage and not args.with_buck_response:
        raise ValueError('GFX cases require buck response cases')
    if args.with_mcu_clock_response and not args.with_buck_response:
        raise ValueError('MCU clock cases require buck response cases')
    if args.with_buck_status and not args.with_memldo_setup:
        raise ValueError('Buck status cases require memory LDO cases')
    if args.with_buck_response and not args.with_memldo_setup:
        raise ValueError('Buck response cases require memory LDO cases')
    if args.with_memldo_setup and not args.with_coreldo_reduction:
        raise ValueError('Memory LDO cases require core LDO cases')
    if args.with_coreldo_reduction and not (args.with_hal_storage and args.with_buck_start and args.with_buck_override):
        raise ValueError('Core LDO cases require HAL, buck start and override test fixtures')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image],
                                       text=True, timeout=15).strip()
    cases = {}
    selections = [dict(address=0x40021000, width=width, operation=operation)
                  for width in (1, 2, 4) for operation in ('read', 'write')]
    selections.append(dict(address=0xe001e300, width=4, operation='read'))
    if args.with_startup_fixtures:
        selections += [
            dict(name='lp-read', address=0x40021000, width=4, operation='read', mode='lp', returned=13, power_reads=1),
            dict(name='hp-read', address=0x40021000, width=4, operation='read', mode='hp', returned=22, power_reads=1),
            dict(name='lp-partial', address=0x40021000, width=2, operation='read', mode='lp'),
            dict(name='lp-write', address=0x40021000, width=4, operation='write', mode='lp'),
            dict(name='latch-read', address=0x4000885c, width=4, operation='read', latch=6, returned=6, latch_reads=1),
            dict(name='latch-clear', address=0x4000885c, width=4, operation='write', latch=6, write_value=2,
                 returned=2, latch_reads=1, latch_writes=1, final_latch=2),
            dict(name='latch-bad-write', address=0x4000885c, width=4, operation='write', latch=2, write_value=0),
            dict(name='latch-partial', address=0x4000885c, width=1, operation='read', latch=6),
            dict(name='latch-neighbor', address=0x40008860, width=4, operation='read', latch=6)]
    if args.with_startup_controls:
        selections += [
            dict(name='device-enable-read',address=0x40021004,width=4,operation='read',returned=0,controls={'device_reads':1}),
            dict(name='device-status-read',address=0x40021008,width=4,operation='read',returned=0,controls={'device_reads':1}),
            dict(name='device-unchanged-write',address=0x40021004,width=4,operation='write',write_value=0,returned=0,controls={'device_reads':1,'device_writes':1}),
            dict(name='device-powerup-reject',address=0x40021004,width=4,operation='write',write_value=1,controls={}),
            dict(name='device-status-write-reject',address=0x40021008,width=4,operation='write',write_value=0,controls={}),
            dict(name='device-partial-reject',address=0x40021004,width=1,operation='read',controls={}),
            dict(name='debug-read',address=0x40020250,width=4,operation='read',returned=0,controls={'debug_reads':1}),
            dict(name='debug-unchanged-write',address=0x40020250,width=4,operation='write',write_value=0,returned=0,controls={'debug_reads':1,'debug_writes':1}),
            dict(name='debug-enable-reject',address=0x40020250,width=4,operation='write',write_value=1,controls={}),
            dict(name='core-on-read',address=0xe001e300,width=4,operation='read',returned=0,controls={'core_reads':1}),
            dict(name='core-on-write',address=0xe001e300,width=4,operation='write',write_value=0,returned=0,controls={'core_reads':1,'core_writes':1}),
            dict(name='core-transition-reject',address=0xe001e300,width=4,operation='write',write_value=2,controls={}),
            dict(name='wic-read',address=0x4002021c,width=4,operation='read',returned=0,controls={'wic_reads':1}),
            dict(name='wic-store',address=0x4002021c,width=4,operation='write',write_value=1,returned=1,controls={'wic_reads':1,'wic_writes':1,'wic_value':1}),
            dict(name='wic-unknown-reject',address=0x4002021c,width=4,operation='write',write_value=2,controls={})]
    if args.with_info1_fixtures:
        for source, value in (('mram', 1), ('otp', 9)):
            selections += [dict(name='shadow-'+source,address=0x400201bc,width=4,operation='read',
                                source=source,returned=value,info_reads=1)]
        selections += [dict(name='shadow-write-reject',address=0x400201bc,width=4,operation='write',source='mram'),
                       dict(name='shadow-partial-reject',address=0x400201bc,width=2,operation='read',source='mram'),
                       dict(name='shadow-no-calibration',address=0x42003244,width=4,operation='read',source='otp')]
        for kind, value in (('zero',0),('erased',0xffffffff)):
            for address in (0x42003240,0x42003310,0x42003314):
                selections.append(dict(name=f'info1-{kind}-{address:x}',address=address,width=4,
                    operation='read',metadata=kind,returned=value,info_reads=1))
            selections += [dict(name='info1-'+kind+'-write-reject',address=0x42003310,width=4,
                                operation='write',metadata=kind),
                           dict(name='info1-'+kind+'-partial-reject',address=0x42003240,width=1,
                                operation='read',metadata=kind),
                           dict(name='info1-'+kind+'-neighbor-reject',address=0x42003318,width=4,
                                operation='read',metadata=kind)]
    if args.with_silicon_fixtures:
        for revision in (0x21,0x22,0x23,0x24):
            selections.append(dict(name=f'chiprev-{revision:x}',address=0x4002000c,width=4,
                operation='read',revision=revision,returned=revision,silicon={'revision_reads':1}))
        selections += [dict(name='chiprev-write-reject',address=0x4002000c,width=4,operation='write',revision=0x23,silicon={}),
                       dict(name='chiprev-partial-reject',address=0x4002000c,width=2,operation='read',revision=0x23,silicon={}),
                       dict(name='chiprev-neighbor-reject',address=0x40020010,width=4,operation='read',revision=0x23,silicon={})]
        for name,address,initial,values in [('acrg',0x40020028,0x78,(0x78,0x79)),('vrctrl',0x40020060,0,(0,0x8000,0xc000,0xe000))]:
            selections.append(dict(name=name+'-initial',address=address,width=4,operation='read',spot=True,
                returned=initial,silicon={name+'_reads':1}))
            for value in values:
                selections.append(dict(name=f'{name}-store-{value:x}',address=address,width=4,operation='write',spot=True,
                    write_value=value,returned=value,silicon={name+'_reads':1,name+'_writes':1,name+'_value':value}))
            selections += [dict(name=name+'-bad-write',address=address,width=4,operation='write',spot=True,write_value=1,silicon={}),
                           dict(name=name+'-partial',address=address,width=1,operation='read',spot=True,silicon={})]
    if args.with_memory_fixtures:
        for address,value in [(0x40021014,0x3f),(0x40021018,0xcf),(0x4002101c,2),
                              (0x40021024,7),(0x40021028,7),(0x4002102c,0x7e38),(0x40021040,0x1b0c)]:
            selections.append(dict(name=f'memory-read-{address:x}',address=address,width=4,operation='read',
                returned=value,memory={hex(address):{'reads':1}}))
        for address,values in [(0x40021014,(0x3f,0x1f)),(0x4002101c,(0,1,2,3)),
                               (0x40021024,(7,)),(0x4002102c,(0,0x7e3f)),(0x40021040,(0x1b0c,0x30c,0xc))]:
            for value in values:
                changes={hex(address):{'value':value,'reads':1,'writes':1}}
                if address==0x40021014 and value==0x1f: changes['0x40021018']={'value':0x4f}
                selections.append(dict(name=f'memory-store-{address:x}-{value:x}',address=address,width=4,operation='write',
                    write_value=value,returned=value,memory=changes,rom_disables=int(address==0x40021014 and value==0x1f)))
        for name,address,value,width,operation in [
            ('memory-bad-domain-transition',0x40021014,0,4,'write'),
            ('memory-status-write',0x40021018,0,4,'write'),
            ('memory-bad-retention-bit',0x4002101c,4,4,'write'),
            ('memory-shared-off',0x40021024,0,4,'write'),
            ('memory-shared-status-write',0x40021028,7,4,'write'),
            ('memory-shared-reserved',0x4002102c,0x8000,4,'write'),
            ('memory-bad-override',0x40021040,0,4,'write'),
            ('memory-partial',0x40021018,0,2,'read'),
            ('memory-neighbor',0x40021020,0,4,'read')]:
            selections.append(dict(name=name,address=address,width=width,operation=operation,write_value=value,memory={}))
    if args.with_memory_fixtures:
        selections += [
            dict(name='memory-disabled',address=0x40021018,width=4,operation='read',mode='lp'),
            dict(name='memory-rom-disable-repeat',address=0x40021014,width=4,operation='write',write_value=0x1f,
                 pre_write=0x1f,returned=0x1f,rom_disables=1,
                 memory={'0x40021014':{'value':0x1f,'writes':2,'reads':1},'0x40021018':{'value':0x4f}}),
            dict(name='memory-rom-status-after-disable',address=0x40021014,width=4,operation='write',write_value=0x1f,
                 readback_address=0x40021018,returned=0x4f,rom_disables=1,
                 memory={'0x40021014':{'value':0x1f,'writes':1},'0x40021018':{'value':0x4f,'reads':1}}),
            dict(name='memory-rom-restore-reject',address=0x40021014,width=4,operation='write',write_value=0x3f,
                 pre_write=0x1f,rom_disables=1,
                 memory={'0x40021014':{'value':0x1f,'writes':1},'0x40021018':{'value':0x4f}})]
    if args.with_hal_storage:
        import hashlib
        from simulator_trim_fixture import CATALOG, CATALOG_SHA256
        raw=CATALOG.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CATALOG_SHA256: raise ValueError('Trim catalog changed')
        catalog=json.loads(raw)
        hal_initial={int(a,16):r['reset'] for a,r in catalog['registers'].items()}
        writable={0x40004044:(0,(0,0xfbbfc0)),0x40004120:(0,(0,)),0x40020448:(0x200,(0x200,0x400)),
            0x4002037c:(0x80,(0x80,0x40000080)),0x40020380:(0,(0,0x10000,0x11000)),
            0x400211a0:(0,(0,0x3e80000)),0x400211a4:(0,(0,0x320)),0x400211a8:(0,(0,)),
            0x400211ac:(0,(0,0x1c2)),0x400211b4:(0,(0,0x258)),0x400211bc:(0,(0,0xfa)),
            0x40008858:(0,(0,0x5af00000))}
        hal_initial.update({a:r[0] for a,r in writable.items()})
        hal_initial[0x40004020]=0x25b800
        read_code='result[0]=0;'; checksum=0
        for address,value in hal_initial.items():
            read_code+=f'result[0]+=(*(volatile uint32_t*)0x{address:x}!=0x{value:x});'
        selections.append(dict(name='hal-read-all',address=0x40004044,width=4,operation='read',returned=checksum,
            code=read_code,hal={hex(a):{'reads':1} for a in hal_initial}))
        write_code='result[0]=0;';checksum=0;changes={}
        for address,(_,values) in writable.items():
            for value in values:
                write_code+=f'*(volatile uint32_t*)0x{address:x}=0x{value:x};result[0]+=(*(volatile uint32_t*)0x{address:x}!=0x{value:x});'
            changes[hex(address)]={'value':values[-1],'reads':len(values),'writes':len(values)}
        selections.append(dict(name='hal-store-observed-sequence',address=0x40004044,width=4,operation='read',
            returned=checksum,code=write_code,hal=changes))
        for address in hal_initial:
            selections.append(dict(name=f'hal-reject-write-{address:x}',address=address,width=4,operation='write',
                write_value=0xffffffff,hal={}))
        selections += [dict(name='hal-reject-same-reset-write',address=0x40020088,width=4,operation='write',write_value=0x207c0774,hal={}),
            dict(name='hal-reject-ton-enable',address=0x400211a0,width=4,operation='write',write_value=0x3e80001,hal={}),
            dict(name='hal-partial-clock',address=0x40004044,width=1,operation='read',hal={}),
            dict(name='hal-partial-trim',address=0x40020088,width=2,operation='read',hal={}),
            dict(name='hal-neighbor',address=0x40004048,width=4,operation='read',hal={}),
            dict(name='hal-disabled',address=0x40004044,width=4,operation='read',mode='lp')]
    if args.with_mram_control:
        selections += [
            dict(name='mram-initial',address=0x400211c8,width=4,operation='read',returned=2,mram={'reads':1}),
            dict(name='mram-unchanged',address=0x400211c8,width=4,operation='write',write_value=2,returned=2,mram={'reads':1,'writes':1}),
            dict(name='mram-disable-auto',address=0x400211c8,width=4,operation='write',write_value=6,returned=6,mram={'value':6,'reads':1,'writes':1}),
            dict(name='mram-disable-repeat',address=0x400211c8,width=4,operation='write',pre_write=6,write_value=6,returned=6,mram={'value':6,'reads':1,'writes':2}),
            dict(name='mram-restore-reject',address=0x400211c8,width=4,operation='write',pre_write=6,write_value=2,mram={'value':6,'writes':1}),
            dict(name='mram-partial-read',address=0x400211c8,width=1,operation='read',mram={}),
            dict(name='mram-partial-write',address=0x400211c8,width=2,operation='write',write_value=6,mram={}),
            dict(name='mram-neighbor',address=0x400211cc,width=4,operation='read',mram={}),
            dict(name='mram-disabled',address=0x400211c8,width=4,operation='read',mode='lp')]
        for value in (0,3,0xa,0x12,0x20):
            selections.append(dict(name=f'mram-bad-value-{value:x}',address=0x400211c8,width=4,operation='write',write_value=value,mram={}))
    if args.with_buck_override:
        sequence=(0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        for count in range(1,11):
            code='result[0]=0;*(volatile uint32_t*)0x40020060=0xe000;'
            for value in sequence[:count]:
                code+=f'*(volatile uint32_t*)0x40020060=0x{value:x};result[0]+=(*(volatile uint32_t*)0x40020060!=0x{value:x});'
            selections.append(dict(name=f'buck-prefix-{count}',address=0x40020060,width=4,operation='read',
                returned=0,code=code,spot=True,buck=count,
                silicon={'vrctrl_value':sequence[count-1],'vrctrl_reads':count,'vrctrl_writes':count+1}))
        for name,prefix,bad in [('missing-analog',(),0x2e000),('early-override',(0xe000,),0xfe000),
            ('skip-reset',(0xe000,0x2e000),0xee000),('change-analog',(0xe000,0x2e000),0x20000),
            ('skip-duplicate',(0xe000,)+sequence[:4],0xfe00e),('reentry-change',(0xe000,)+sequence,0xfe1ee)]:
            code=''.join(f'*(volatile uint32_t*)0x40020060=0x{v:x};' for v in prefix)
            code+=f'*(volatile uint32_t*)0x40020060=0x{bad:x};'
            selections.append(dict(name='buck-reject-'+name,address=0x40020060,width=4,operation='write',write_value=bad,
                code=code,spot=True,buck=max(0,len(prefix)-1),
                silicon={'vrctrl_value':prefix[-1] if prefix else 0,'vrctrl_writes':len(prefix)}))
        repeated=''.join(f'*(volatile uint32_t*)0x40020060=0x{v:x};' for v in (0xe000,)+sequence)
        repeated+=''.join(f'*(volatile uint32_t*)0x40020060|=0x{v:x};' for v in (0x8000,0x4000,0x2000))
        repeated+='result[0]=*(volatile uint32_t*)0x40020060;'
        selections.append(dict(name='buck-complete-repeat',address=0x40020060,width=4,operation='read',returned=0xfe1ef,
            code=repeated,spot=True,buck=10,silicon={'vrctrl_value':0xfe1ef,'vrctrl_reads':4,'vrctrl_writes':14}))
        selections += [dict(name='buck-partial-read',address=0x40020060,width=1,operation='read',spot=True,buck=0,silicon={}),
            dict(name='buck-partial-write',address=0x40020060,width=2,operation='write',write_value=0xe000,spot=True,buck=0,silicon={}),
            dict(name='buck-disabled',address=0x40020060,width=4,operation='write',write_value=0x2e000,spot=True,silicon={})]
    if args.with_buck_start:
        vr=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        prime=''.join(f'*(volatile uint32_t*)0x40020060=0x{v:x};' for v in vr)
        steps=((0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1))
        def changes(count,reads=False):
            return {hex(a):dict(value=v,writes=1,reads=int(reads)) for a,v in steps[:count]}
        for count in (1,2,3):
            code=prime+'result[0]=0;'
            for a,v in steps[:count]:code+=f'*(volatile uint32_t*)0x{a:x}=0x{v:x};result[0]+=(*(volatile uint32_t*)0x{a:x}!=0x{v:x});'
            selections.append(dict(name=f'buck-start-prefix-{count}',address=steps[count-1][0],width=4,operation='read',
                code=code,returned=0,spot=True,buck=10,silicon={'vrctrl_value':0xfe1ef,'vrctrl_writes':11},start=count,start_registers=changes(count,True)))
        for name,count,address,value in [('no-override',0,0x40020378,0x80000000),
            ('comp-first',0,0x4002033c,0xf),('enable-early',1,0x40021100,1),
            ('trim-bits',0,0x40020378,0x80000001),('comp-reserved',1,0x4002033c,0x1f),
            ('disable-unmodeled',3,0x40021100,0)]:
            priming='' if name=='no-override' else prime
            code=priming+''.join(f'*(volatile uint32_t*)0x{a:x}=0x{v:x};' for a,v in steps[:count])
            code+=f'*(volatile uint32_t*)0x{address:x}=0x{value:x};'
            selections.append(dict(name='buck-start-reject-'+name,address=address,width=4,operation='write',write_value=value,code=code,
                spot=True,buck=0 if name=='no-override' else 10,silicon={} if name=='no-override' else {'vrctrl_value':0xfe1ef,'vrctrl_writes':11},start=count,start_registers=changes(count)))
        code=prime+''.join(f'*(volatile uint32_t*)0x{a:x}=0x{v:x};' for a,v in steps)+'result[0]=*(volatile uint32_t*)0x40021108;'
        selections.append(dict(name='buck-start-readiness-guard',address=0x40021108,width=4,operation='read',code=code,
            spot=True,buck=10,silicon={'vrctrl_value':0xfe1ef,'vrctrl_writes':11},start=3,start_registers=changes(3),**({'hal':{}} if args.with_hal_storage else {})))
        selections += [dict(name='buck-start-disabled',address=0x40020378,width=4,operation='write',write_value=0x80000000,
            code=prime+'*(volatile uint32_t*)0x40020378=0x80000000;',spot=True,buck=10,silicon={'vrctrl_value':0xfe1ef,'vrctrl_writes':11}),
            dict(name='buck-start-partial-read',address=0x40020378,width=1,operation='read',spot=True,buck=0,silicon={},start=0),
            dict(name='buck-start-partial-write',address=0x40021100,width=2,operation='write',write_value=1,spot=True,buck=0,silicon={},start=0)]
    if args.with_coreldo_reduction:
        vr=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        startup=((0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1))
        readonly={int(a,16) for a in catalog['registers']}
        cache=''.join(f'(void)*(volatile uint32_t*)0x{a:x};' for a in sorted(readonly))
        prime=''.join(f'*(volatile uint32_t*)0x40020060=0x{v:x};' for v in vr)
        initial=hal_initial[0x40020080];expected_word=(initial&~0x3ff)|max((initial&0x3ff)-7,0)
        for name,stage,cached,bad,repeated,enabled,width in [
            ('valid',2,True,expected_word,False,True,4),
            ('wrong-trim',2,True,expected_word^1,False,True,4),
            ('other-field',2,True,expected_word^0x1000,False,True,4),
            ('missing-cache',2,False,expected_word,False,True,4),
            ('early',0,True,expected_word,False,True,4),
            ('after-enable',3,True,expected_word,False,True,4),
            ('repeat',2,True,expected_word,True,True,4),
            ('partial',2,True,expected_word&0xffff,False,True,2),
            ('disabled',2,True,expected_word,False,False,4)]:
            code=(cache if cached else '')+prime+''.join(f'*(volatile uint32_t*)0x{a:x}=0x{v:x};' for a,v in startup[:stage])
            if repeated:code+=f'*(volatile uint32_t*)0x40020080=0x{expected_word:x};'
            code+=f'*(volatile uint{width*8}_t*)0x40020080=0x{bad:x};'
            good=name=='valid'
            if good:code+='result[0]=*(volatile uint32_t*)0x40020080;'
            hal={hex(a):{'reads':1} for a in readonly} if cached else {}
            if good or repeated:
                hal['0x40020080']=dict(value=expected_word,writes=1,reads=int(cached)+int(good))
            spec=dict(name='coreldo-'+name,address=0x40020080,width=width,operation='write',write_value=bad,code=code,
                spot=True,buck=10,silicon={'vrctrl_value':0xfe1ef,'vrctrl_writes':11},start=stage,
                start_registers={hex(a):dict(value=v,writes=1) for a,v in startup[:stage]},hal=hal)
            if enabled:spec['coreldo']=dict(applied=good or repeated,cache_witness=cached)
            if good:spec['returned']=expected_word
            selections.append(spec)
    if args.with_memldo_setup:
        mem,ref=0x40020088,0x400201b0
        mem_word=(hal_initial[mem]&~0x3f)|1
        ref_word=(hal_initial[ref]&~0x18000)|0x10000
        good_writes=[(mem,4,mem_word),(ref,4,ref_word)]
        for name,attempts,completed,start_stage,core_applied,enabled,ready in [
            ('valid',good_writes,2,3,True,True,False),
            ('readiness-guard',good_writes,2,3,True,True,True),
            ('wrong-trim',[(mem,4,mem_word^1)],0,3,True,True,False),
            ('other-memory-field',[(mem,4,mem_word^0x80)],0,3,True,True,False),
            ('wrong-reference',[good_writes[0],(ref,4,0x18000)],1,3,True,True,False),
            ('other-reference-field',[good_writes[0],(ref,4,ref_word^1)],1,3,True,True,False),
            ('reverse',[good_writes[1]],0,3,True,True,False),
            ('early',[good_writes[0]],0,2,True,True,False),
            ('missing-core',[good_writes[0]],0,3,False,True,False),
            ('repeat',[good_writes[0],good_writes[0]],1,3,True,True,False),
            ('after-complete',good_writes+[good_writes[1]],2,3,True,True,False),
            ('partial',[(mem,2,mem_word&0xffff)],0,3,True,True,False),
            ('disabled',[good_writes[0]],0,3,True,False,False)]:
            code=cache+prime+''.join(f'*(volatile uint32_t*)0x{a:x}=0x{v:x};' for a,v in startup[:2])
            if core_applied:code+=f'*(volatile uint32_t*)0x40020080=0x{expected_word:x};'
            if start_stage==3:code+='*(volatile uint32_t*)0x40021100=1;'
            code+=''.join(f'*(volatile uint{w*8}_t*)0x{a:x}=0x{v:x};' for a,w,v in attempts)
            good=name=='valid'
            if good:code+='result[0]=(*(volatile uint32_t*)0x40020088)^(*(volatile uint32_t*)0x400201b0);'
            if ready:code+='result[0]=*(volatile uint32_t*)0x40021108;'
            hal={hex(a):{'reads':1} for a in readonly}
            if core_applied:hal['0x40020080'].update(value=expected_word,writes=1)
            for a,_,v in good_writes[:completed]:hal[hex(a)].update(value=v,writes=1,reads=1+int(good))
            a,w,v=attempts[-1]
            spec=dict(name='memldo-'+name,address=0x40021108 if ready else a,width=4 if ready else w,
                operation='read' if ready else 'write',write_value=v,code=code,spot=True,buck=10,
                silicon={'vrctrl_value':0xfe1ef,'vrctrl_writes':11},start=start_stage,
                start_registers={hex(a):dict(value=v,writes=1) for a,v in startup[:start_stage]},hal=hal,
                coreldo=dict(applied=core_applied,cache_witness=True))
            if enabled:spec['memldo']=dict(steps_completed=completed)
            if good:spec['returned']=mem_word^ref_word
            selections.append(spec)
    if args.with_buck_status:
        import copy
        template=next(item for item in selections if item.get('name')=='memldo-valid')
        prefix=template['code'].split('result[0]=',1)[0]
        for label,status,operation,width,repeated,memory_done in [
            ('off',0,'read',4,False,True),('lp',2,'read',4,False,True),('active',3,'read',4,False,True),
            ('off-repeat',0,'read',4,True,True),('lp-repeat',2,'read',4,True,True),('active-repeat',3,'read',4,True,True),
            ('partial',3,'read',2,False,True),('byte',3,'read',1,False,True),
            ('write',3,'write',4,False,True),('before-memory',3,'read',4,False,False)]:
            spec=copy.deepcopy(template)
            spec.update(name='buck-status-'+label,address=0x40021108,width=width,operation=operation,write_value=0x30)
            spec.pop('returned',None)
            for a in (0x40020088,0x400201b0):spec['hal'][hex(a)]['reads']=1
            code=prefix
            if not memory_done:
                code=prefix.split('*(volatile uint32_t*)0x40020088=',1)[0]
                spec['memldo']={'steps_completed':0}
                for a in (0x40020088,0x400201b0):spec['hal'][hex(a)]={'reads':1}
            if repeated:code+='(void)*(volatile uint32_t*)0x40021108;'
            code+=f'result[0]=*(volatile uint{width*8}_t*)0x40021108;' if operation=='read' else '*(volatile uint32_t*)0x40021108=0x30;'
            spec['code']=code
            sampled=memory_done and width==4 and operation=='read'
            spec['status']={'code':status,'reads':int(sampled)}
            if sampled and not repeated:spec['returned']=status<<4
            selections.append(spec)
    if args.with_buck_response:
        import copy
        template=next(item for item in selections if item.get('name')=='memldo-valid')
        prefix=template['code'].split('result[0]=',1)[0]
        for label,profile,op,width,reads,setup in [
            ('active',3,'read',4,3,True),('stuck-off',0,'read',4,3,True),
            ('before-setup',3,'read',4,0,False),('byte',3,'read',1,0,True),
            ('halfword',3,'read',2,0,True),('write',3,'write',4,0,True)]:
            spec=copy.deepcopy(template);spec.pop('returned',None)
            spec.update(name='buck-response-'+label,address=0x40021108,width=width,operation=op,write_value=0x30)
            for a in (0x40020088,0x400201b0):spec['hal'][hex(a)]['reads']=1
            code=prefix
            if not setup:
                code=prefix.split('*(volatile uint32_t*)0x40020088=',1)[0];spec['memldo']={'steps_completed':0}
                for a in (0x40020088,0x400201b0):spec['hal'][hex(a)]={'reads':1}
            if reads:
                code+=''.join('result[0]=*(volatile uint32_t*)0x40021108;' for _ in range(reads))
                spec['returned']=profile<<4
            else:code+=f'result[0]=*(volatile uint{width*8}_t*)0x40021108;' if op=='read' else '*(volatile uint32_t*)0x40021108=0x30;'
            spec['code']=code
            spec['response']=dict(profile=profile,phase=('active' if profile==3 else 'stuck-off') if reads else 'requested',reads=reads,transitions=2 if reads else 1)
            selections.append(spec)
        initial=hal_initial[0x4002004c];reduced=(initial&~127)|max((initial&127)-10,0)
        for label,profile,sample,enabled,width,value,repeat in [
            ('valid',3,True,True,4,reduced,False),('wrong-value',3,True,True,4,reduced^0x80,False),
            ('premature',3,False,True,4,reduced,False),('stuck-off',0,True,True,4,reduced,False),
            ('repeat',3,True,True,4,reduced,True),('partial',3,True,True,2,reduced&0xffff,False),
            ('disabled',3,True,False,4,reduced,False)]:
            spec=copy.deepcopy(template);spec.pop('returned',None)
            spec.update(name='vddf-tempco-'+label,address=0x4002004c,width=width,operation='write',write_value=value)
            for a in (0x40020088,0x400201b0):spec['hal'][hex(a)]['reads']=1
            code=prefix+('(void)*(volatile uint32_t*)0x40021108;' if sample else '')+'(void)*(volatile uint32_t*)0x4002004c;'
            if repeat:code+=f'*(volatile uint32_t*)0x4002004c=0x{reduced:x};'
            code+=f'*(volatile uint{width*8}_t*)0x4002004c=0x{value:x};'
            good=label in ('valid','repeat')
            if good:code+='result[0]=*(volatile uint32_t*)0x4002004c;';spec['returned']=reduced
            applied=good or repeat
            spec['hal']['0x4002004c']=dict(value=reduced if applied else initial,reads=2+int(good),writes=(1+int(repeat)) if good else int(applied))
            spec['response']=dict(profile=profile,phase=('active' if profile==3 else 'stuck-off') if sample else 'requested',reads=int(sample),transitions=2 if sample else 1)
            spec['tempco']=dict(applied=applied,original_word=initial,reduced_trim=max((initial&127)-10,0)) if enabled else None
            spec['code']=code;selections.append(spec)
        template=next(item for item in selections if item.get('name')=='vddf-tempco-valid')
        warm_prefix=template['code'].split('result[0]=',1)[0]
        for label,values in [('main-reduce',[44]),('field-range',list(range(128))),('same',[54,54,54])]:
            spec=copy.deepcopy(template)
            final=(initial&~127)|values[-1]
            spec.update(name='vddf-tempco-warm-'+label,returned=final,
                code=warm_prefix+''.join(f'*(volatile uint32_t*)0x4002004c=0x{((initial&~127)|v):x};' for v in values)+'result[0]=*(volatile uint32_t*)0x4002004c;')
            spec['hal']['0x4002004c']=dict(value=final,reads=3,writes=1+len(values))
            selections.append(spec)
        spec=copy.deepcopy(template)
        spec.update(name='vddf-tempco-warm-other-field',write_value=reduced^0x80,
            code=warm_prefix+f'*(volatile uint32_t*)0x4002004c=0x{reduced^0x80:x};')
        spec.pop('returned',None)
        spec['hal']['0x4002004c']=dict(value=reduced,reads=2,writes=1)
        selections.append(spec)
    if args.with_mcu_clock_response:
        import copy
        template=next(item for item in selections if item.get('name')=='vddf-tempco-valid')
        prefix=template['code'].split('result[0]=',1)[0]
        bootstrap='*(volatile uint32_t*)0x40004044=0xfbbfc0;'
        force='*(volatile uint32_t*)0x40004044=0xfbbfe0;'
        release='*(volatile uint32_t*)0x40004044=0xfbbfc0;'
        poll='(void)*(volatile uint32_t*)0x40004030;'
        request='*(volatile uint32_t*)0x40021000=14;'
        finish='result[0]=*(volatile uint32_t*)0x40021000 ^ *(volatile uint32_t*)0x40004030;'
        for label,profile,code,address,width,value,returned,fw,cr,mr,mw,tr,word,phase,misc in [
            ('nominal',0,force+poll+request+release+finish,0x40021000,4,14,0x81000016,2,2,1,1,1,22,'acked',0xfbbfc0),
            ('no-ack',2,force+poll+request+release+finish,0x40021000,4,14,10,2,2,1,1,0,10,'pending',0xfbbfc0),
            ('denied',3,force+poll+request+release+finish,0x40021000,4,14,14,2,2,1,1,0,14,'denied',0xfbbfc0),
            ('unready',1,force+poll+release+'result[0]=*(volatile uint32_t*)0x40004030;',0x40004030,4,0,0,2,2,0,0,0,13,'clock-requested',0xfbbfc0),
            ('unready-request',1,force+request,0x40021000,4,14,None,1,0,0,0,0,13,'clock-requested',0xfbbfe0),
            ('without-force',0,request,0x40021000,4,14,None,0,0,0,0,0,13,'initial',0xfbbfc0),
            ('misc-reserved',0,'*(volatile uint32_t*)0x40004044=0xfbbfe1;',0x40004044,4,0xfbbfe1,None,0,0,0,0,0,13,'initial',0xfbbfc0),
            ('byte-force',0,'*(volatile uint8_t*)0x40004044=32;',0x40004044,1,32,None,0,0,0,0,0,13,'initial',0xfbbfc0),
            ('mode-readonly',0,force+'*(volatile uint32_t*)0x40021000=2;',0x40021000,4,2,None,1,0,0,0,0,13,'clock-requested',0xfbbfe0),
            ('invalid-mode-zero',0,force+'*(volatile uint32_t*)0x40021000=12;',0x40021000,4,12,None,1,0,0,0,0,13,'clock-requested',0xfbbfe0),
            ('status-write',0,'*(volatile uint32_t*)0x40004030=0;',0x40004030,4,0,None,0,0,0,0,0,13,'initial',0xfbbfc0),
            ('repeat-request',0,force+request+'*(volatile uint32_t*)0x40021000=22;'+release+finish,0x40021000,4,22,0x81000016,2,1,1,2,1,22,'acked',0xfbbfc0)]:
            spec=copy.deepcopy(template);spec.pop('returned',None)
            spec.update(name='mcu-clock-'+label,mode='lp',power_reads=mr,address=address,width=width,
                        operation='write',write_value=value,code=prefix+bootstrap+code)
            spec['hal']['0x4002004c']['reads']=2
            spec['hal']['0x40004044']=dict(value=misc,reads=0,writes=1+fw)
            enabled=bool(misc&32) or ((word>>3)&3)==2
            spec['clock']=dict(profile=profile,phase=phase,mode_word=word,force_writes=fw,
                clock_reads=cr,mode_reads=mr,mode_writes=mw,transitions=tr,misc_word=misc,
                enabled=enabled,ready=enabled and profile!=1)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_hfrc_force_control:
        import copy
        template=next(item for item in selections if item.get('name')=='mcu-clock-nominal')
        prefix=template['code'].split('result[0]=',1)[0]
        for label,enabled,code,address,width,value,returned,misc,extra_writes,extra_reads in [
            ('enable',True,'*(volatile uint32_t*)0x40004044=0xfbbfc1;result[0]=*(volatile uint32_t*)0x40004030;',0x40004044,4,0xfbbfc1,0xc1000000,0xfbbfc1,1,1),
            ('release',True,'*(volatile uint32_t*)0x40004044=0xfbbfc1;*(volatile uint32_t*)0x40004044=0xfbbfc0;result[0]=*(volatile uint32_t*)0x40004030;',0x40004044,4,0xfbbfc0,0x81000000,0xfbbfc0,2,1),
            ('both-forces',True,'*(volatile uint32_t*)0x40004044=0xfbbfe1;result[0]=*(volatile uint32_t*)0x40004030;',0x40004044,4,0xfbbfe1,0xc1000000,0xfbbfe1,1,1),
            ('reserved',True,'*(volatile uint32_t*)0x40004044=0xfbbfc3;',0x40004044,4,0xfbbfc3,None,0xfbbfc0,0,0),
            ('byte',True,'*(volatile uint8_t*)0x40004044=1;',0x40004044,1,1,None,0xfbbfc0,0,0),
            ('status-write',True,'*(volatile uint32_t*)0x40004030=0;',0x40004030,4,0,None,0xfbbfc0,0,0),
            ('disabled',False,'*(volatile uint32_t*)0x40004044=0xfbbfc1;',0x40004044,4,0xfbbfc1,None,0xfbbfc0,0,0)]:
            spec=copy.deepcopy(template);spec.pop('returned',None)
            spec.update(name='hfrc-force-'+label,hfrc=enabled,power_reads=0,address=address,width=width,
                        operation='write',write_value=value,code=prefix+code)
            spec['clock'].update(misc_word=misc,force_writes=2+extra_writes,clock_reads=1+extra_reads,mode_reads=0)
            spec['hal']['0x40004044']=dict(value=misc,reads=0,writes=3+extra_writes)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gfx_power_storage:
        import copy
        active_template=next(item for item in selections if item.get('name')=='vddf-tempco-valid')
        active_prefix=active_template['code'].split('result[0]=',1)[0]
        for label,active,code,address,width,operation,value,returned,sel,perf,sr,pr,sw,pw in [
            ('initial',False,'result[0]=*(volatile uint32_t*)0x40021090 ^ *(volatile uint32_t*)0x4002108c;',0x40021090,4,'read',0,0,0,0,1,1,0,0),
            ('lp',False,'*(volatile uint32_t*)0x40021090=0;*(volatile uint32_t*)0x4002108c=0;result[0]=*(volatile uint32_t*)0x4002108c;',0x4002108c,4,'write',0,0,0,0,0,1,1,1),
            ('hp',True,'*(volatile uint32_t*)0x40021090=1;*(volatile uint32_t*)0x4002108c=3;result[0]=*(volatile uint32_t*)0x40021090 ^ *(volatile uint32_t*)0x4002108c;',0x4002108c,4,'write',3,2,1,3,1,1,1,1),
            ('repeat',True,'*(volatile uint32_t*)0x40021090=1;*(volatile uint32_t*)0x4002108c=3;*(volatile uint32_t*)0x40021090=1;*(volatile uint32_t*)0x4002108c=3;result[0]=*(volatile uint32_t*)0x4002108c;',0x4002108c,4,'write',3,3,1,3,0,1,2,2),
            ('without-buck',False,'*(volatile uint32_t*)0x40021090=1;',0x40021090,4,'write',1,None,0,0,0,0,0,0),
            ('before-supply',True,'*(volatile uint32_t*)0x4002108c=3;',0x4002108c,4,'write',3,None,0,0,0,0,0,0),
            ('wrong-supply-lp',True,'*(volatile uint32_t*)0x40021090=1;*(volatile uint32_t*)0x4002108c=0;',0x4002108c,4,'write',0,None,1,0,0,0,1,0),
            ('supply-reserved',True,'*(volatile uint32_t*)0x40021090=2;',0x40021090,4,'write',2,None,0,0,0,0,0,0),
            ('mode-reserved',True,'*(volatile uint32_t*)0x4002108c=4;',0x4002108c,4,'write',4,None,0,0,0,0,0,0),
            ('hp1-unsupported',True,'*(volatile uint32_t*)0x4002108c=1;',0x4002108c,4,'write',1,None,0,0,0,0,0,0),
            ('hp2-unsupported',True,'*(volatile uint32_t*)0x4002108c=2;',0x4002108c,4,'write',2,None,0,0,0,0,0,0),
            ('supply-byte',False,'result[0]=*(volatile uint8_t*)0x40021090;',0x40021090,1,'read',0,None,0,0,0,0,0,0),
            ('mode-halfword',False,'*(volatile uint16_t*)0x4002108c=0;',0x4002108c,2,'write',0,None,0,0,0,0,0,0),
            ('neighbor',False,'result[0]=*(volatile uint32_t*)0x40021094;',0x40021094,4,'read',0,None,0,0,0,0,0,0),
            ('disabled',False,'result[0]=*(volatile uint32_t*)0x40021090;',0x40021090,4,'read',0,None,0,0,0,0,0,0)]:
            spec=copy.deepcopy(active_template) if active else dict(controls={})
            spec.pop('returned',None)
            if active:
                spec['hal']['0x4002004c']['reads']=2
                spec['controls']={}
            spec.update(name='gfx-power-'+label,address=address,width=width,operation=operation,
                        write_value=value,code=(active_prefix if active else '')+code)
            if label!='disabled':spec['gfx']=dict(selection=sel,request=perf,selection_reads=sr,
                request_reads=pr,selection_writes=sw,request_writes=pw)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_power_preparation:
        import copy
        template=next(item for item in selections if item.get('name')=='hfrc-force-both-forces')
        prefix=template['code'].split('result[0]=',1)[0]
        def field(address,mask,value):
            return f'*(volatile uint32_t*)0x{address:x}=(*(volatile uint32_t*)0x{address:x}&~0x{mask:x}u)|0x{value:x}u;'
        actions=[(0x40020080,'uint32_t savedCore=*(volatile uint32_t*)0x40020080;uint32_t boost=(savedCore&1023)>1011?1023:(savedCore&1023)+12;*(volatile uint32_t*)0x40020080=(savedCore&~1023u)|boost;',0x6d3d9),
            (0x40020088,field(0x40020088,63,5),0x207c0745)]
        for bit,word in ((29,0x20011000),(28,0x30011000),(31,0xb0011000),(30,0xf0011000)):
            actions.append((0x40020380,field(0x40020380,1<<bit,1<<bit),word))
        for address,mask,value,word in ((0x40020344,0x3e000000,6<<25,0xc000000),
            (0x40020344,0xf800,6<<11,0xc003000),(0x4002034c,0x3e000000,5<<25,0xa000000),
            (0x4002034c,0xf800,5<<11,0xa002800),(0x40020358,0x1f00,13<<8,0xd00),
            (0x40020354,0x3e0000,19<<17,0x260000)):
            actions.append((address,field(address,mask,value),word))
        for bit,word in ((29,0xd0011000),(28,0xc0011000),(31,0x40011000),(30,0x11000)):
            actions.append((0x40020380,field(0x40020380,1<<bit,0),word))
        actions += [(0x40020080,'*(volatile uint32_t*)0x40020080=(*(volatile uint32_t*)0x40020080&~1023u)|(savedCore&1023);',0x6d3cd),
                    (0x40020088,field(0x40020088,63,1),0x207c0741)]
        for label,n,enabled,gfx,hfrc,bad_address,width,bad_value,bad_code,returned in [
            ('complete',18,True,True,True,0x40020080,4,0,'',0x6d3cd),
            ('wrong-first',0,True,True,True,0x40020080,4,0x6d7d9,'*(volatile uint32_t*)0x40020080=0x6d7d9;',None),
            ('without-gfx',0,True,False,True,0x40020080,4,0x6d3d9,actions[0][1],None),
            ('without-hfrc',0,True,True,False,0x40020080,4,0x6d3d9,actions[0][1],None),
            ('out-of-order',1,True,True,True,0x40020380,4,0x20011000,'*(volatile uint32_t*)0x40020380=0x20011000;',None),
            ('wrong-mem-trim',1,True,True,True,0x40020088,4,0x207c0746,'*(volatile uint32_t*)0x40020088=0x207c0746;',None),
            ('wrong-rail',2,True,True,True,0x40020380,4,0x10011000,'*(volatile uint32_t*)0x40020380=0x10011000;',None),
            ('partial',0,True,True,True,0x40020080,2,0xd3d9,'*(volatile uint16_t*)0x40020080=0xd3d9;',None),
            ('repeat',18,True,True,True,0x40020080,4,0x6d3d9,'*(volatile uint32_t*)0x40020080=0x6d3d9;',None),
            ('disabled',0,False,True,True,0x40020080,4,0x6d3d9,actions[0][1],None)]:
            spec=copy.deepcopy(template);spec.pop('returned',None)
            before=prefix if hfrc else prefix.replace('*(volatile uint32_t*)0x40004044=0xfbbfe1;','')
            before+='*(volatile uint32_t*)0x40020380=0x10000;*(volatile uint32_t*)0x40020380=0x11000;'
            if gfx:before+='*(volatile uint32_t*)0x40021090=1;*(volatile uint32_t*)0x4002108c=3;'
            spec.update(name='gpu-preparation-'+label,controls={},address=bad_address,width=width,
                operation='write',write_value=bad_value,code=before+''.join(a[1] for a in actions[:n])+bad_code)
            spec['clock'].update(force_writes=3 if hfrc else 2,clock_reads=1,misc_word=0xfbbfe1 if hfrc else 0xfbbfc0)
            spec['hal']['0x40004044']['writes']=4 if hfrc else 3
            spec['hal']['0x40004044']['value']=spec['clock']['misc_word']
            spec['hal']['0x40020380']=dict(value=0x11000,reads=0,writes=2)
            spec['gfx']=dict(selection=int(gfx),request=3 if gfx else 0,selection_reads=0,request_reads=0,
                            selection_writes=int(gfx),request_writes=int(gfx))
            for address,_,word in actions[:n]:
                r=spec['hal'].setdefault(hex(address),dict(value=hal_initial[address],reads=0,writes=0))
                r['value']=word;r['reads']=r.get('reads',0)+1;r['writes']=r.get('writes',0)+1
            if label in ('without-gfx','without-hfrc','disabled'):
                spec['hal']['0x40020080']['reads']+=1
            if returned is not None:
                spec['code']+='result[0]=*(volatile uint32_t*)0x40020080;';spec['returned']=returned
                spec['hal']['0x40020080']['reads']+=1
            if enabled:spec['preparation']=dict(steps_completed=n,complete=n==18,original_core_word=0x6d3cd if n else 0,boost_delta=12 if n else 0)
            selections.append(spec)
    if args.with_gpu_power_response:
        import copy
        complete=next(item for item in selections if item.get('name')=='gpu-preparation-complete')
        early=next(item for item in selections if item.get('name')=='gpu-preparation-partial')
        enable='*(volatile uint32_t*)0x40021004=0x40000;'
        cancel='*(volatile uint32_t*)0x40021004=0;'
        poll='(void)*(volatile uint32_t*)0x40021008;'
        final='result[0]=*(volatile uint32_t*)0x40021008;'
        for label,profile,ready,code,addr,width,value,returned,phase,request,status,er,sr,ew,tr in [
            ('active',1,True,enable+poll+poll+'result[0]=*(volatile uint32_t*)0x40021004 ^ *(volatile uint32_t*)0x40021008;',0x40021004,4,0x40000,0,'on',0x40000,0x40000,1,3,1,2),
            ('stuck-off',0,True,enable+poll+poll+'result[0]=*(volatile uint32_t*)0x40021004 ^ *(volatile uint32_t*)0x40021008;',0x40021004,4,0x40000,0x40000,'stuck-off',0x40000,0,1,3,1,2),
            ('unrequested',1,True,final,0x40021008,4,0,0,'off',0,0,0,1,0,0),
            ('premature',1,False,enable,0x40021004,4,0x40000,None,'off',0,0,0,0,0,0),
            ('other-device',1,True,'*(volatile uint32_t*)0x40021004=0x40001;',0x40021004,4,0x40001,None,'off',0,0,0,0,0,0),
            ('reserved',1,True,'*(volatile uint32_t*)0x40021004=0x80040000;',0x40021004,4,0x80040000,None,'off',0,0,0,0,0,0),
            ('status-write',1,True,'*(volatile uint32_t*)0x40021008=0x40000;',0x40021008,4,0x40000,None,'off',0,0,0,0,0,0),
            ('partial',1,True,'*(volatile uint16_t*)0x40021004=0;',0x40021004,2,0,None,'off',0,0,0,0,0,0),
            ('active-disable',1,True,enable+poll+cancel,0x40021004,4,0,None,'on',0x40000,0x40000,0,1,1,2),
            ('idempotent',1,True,enable+enable+final,0x40021004,4,0x40000,0x40000,'on',0x40000,0x40000,0,1,2,2),
            ('cancel-pending',1,True,enable+cancel+final,0x40021004,4,0,0,'cancelled',0,0,0,1,2,2),
            ('cancel-stuck',0,True,enable+poll+cancel+final,0x40021004,4,0,0,'cancelled',0,0,0,2,2,3),
            ('disabled',None,True,enable,0x40021004,4,0x40000,None,'off',0,0,0,0,0,0)]:
            spec=copy.deepcopy(complete if ready else early);spec.pop('returned',None)
            before=spec['code'].split('result[0]=',1)[0] if ready else spec['code'].rsplit('*(volatile uint16_t*)',1)[0]
            if ready:spec['hal']['0x40020080']['reads']-=1
            spec.update(name='gpu-response-'+label,address=addr,width=width,operation='write',write_value=value,code=before+code)
            spec['controls'].update(device_reads=er+sr,device_writes=ew)
            if returned is not None:spec['returned']=returned
            if profile is not None:spec['power']=dict(profile=profile,phase=phase,request_word=request,status_word=status,enable_reads=er,status_reads=sr,enable_writes=ew,transitions=tr)
            selections.append(spec)
    if args.with_gpu_interrupt_clear:
        import copy
        for label,base,code,addr,width,op,value,returned,clears,enabled in [
            ('idle','active','*(volatile uint32_t*)0x400900f8=0;result[0]=17;',0x400900f8,4,'write',0,17,1,True),
            ('repeat','active','*(volatile uint32_t*)0x400900f8=0;*(volatile uint32_t*)0x400900f8=0;result[0]=17;',0x400900f8,4,'write',0,17,2,True),
            ('nonzero','active','*(volatile uint32_t*)0x400900f8=1;',0x400900f8,4,'write',1,None,0,True),
            ('read','active','result[0]=*(volatile uint32_t*)0x400900f8;',0x400900f8,4,'read',0,None,0,True),
            ('partial','active','*(volatile uint16_t*)0x400900f8=0;',0x400900f8,2,'write',0,None,0,True),
            ('neighbor','active','*(volatile uint32_t*)0x400900fc=0;',0x400900fc,4,'write',0,None,0,True),
            ('stuck-off','stuck-off','*(volatile uint32_t*)0x400900f8=0;',0x400900f8,4,'write',0,None,0,True),
            ('unrequested','unrequested','*(volatile uint32_t*)0x400900f8=0;',0x400900f8,4,'write',0,None,0,True),
            ('disabled','active','*(volatile uint32_t*)0x400900f8=0;',0x400900f8,4,'write',0,None,0,False)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-response-'+base))
            prefix=spec['code'].split('result[0]=',1)[0]
            if base in ('active','stuck-off'):
                # Remove the two reads in the old XOR result expression.
                spec['power']['enable_reads']-=1;spec['power']['status_reads']-=1
                spec['controls']['device_reads']-=2
            else:
                spec['power']['status_reads']-=1;spec['controls']['device_reads']-=1
            spec.pop('returned',None)
            spec.update(name='gpu-irq-clear-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_irq_clear']=clears
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_id_initialization:
        import copy
        initialize='*(volatile uint32_t*)0x40090148=0;'
        clear='*(volatile uint32_t*)0x400900f8=0;'
        for label,base,code,addr,width,op,value,returned,initialized,enabled,remove_clear in [
            ('initial','idle',initialize+'result[0]=17;',0x40090148,4,'write',0,17,True,True,False),
            ('nonzero','idle','*(volatile uint32_t*)0x40090148=1;',0x40090148,4,'write',1,None,False,True,False),
            ('before-clear','idle',initialize,0x40090148,4,'write',0,None,False,True,True),
            ('repeat','idle',initialize+initialize,0x40090148,4,'write',0,None,True,True,False),
            ('read','idle',initialize+'result[0]=*(volatile uint32_t*)0x40090148;',0x40090148,4,'read',0,None,True,True,False),
            ('partial','idle','*(volatile uint16_t*)0x40090148=0;',0x40090148,2,'write',0,None,False,True,False),
            ('ring-request','idle',initialize+'*(volatile uint32_t*)0x400900ec=6;',0x400900ec,4,'write',6,None,True,True,False),
            ('stuck-off','stuck-off',initialize,0x40090148,4,'write',0,None,False,True,True),
            ('disabled','idle',initialize,0x40090148,4,'write',0,None,False,False,False)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-irq-clear-'+base))
            prefix=spec['code'].split('result[0]=',1)[0]
            if remove_clear:
                assert prefix.endswith(clear)
                prefix=prefix[:-len(clear)];spec['gpu_irq_clear']=0
            spec.pop('returned',None)
            spec.update(name='gpu-id-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_id']=initialized
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_ring_configuration:
        import copy
        request='*(volatile uint32_t*)0x400900ec=0x20010006;'
        base='*(volatile uint32_t*)0x400900f0=0x20010000;'
        length='*(volatile uint32_t*)0x400900f4=4864;'
        for label,code,addr,width,op,value,returned,step,start,size,enabled,ready in [
            ('complete',request+base+length+'result[0]=17;',0x400900f4,4,'write',4864,17,3,0x20010000,4864,True,True),
            ('minimum',request+base+'*(volatile uint32_t*)0x400900f4=16;result[0]=17;',0x400900f4,4,'write',16,17,3,0x20010000,16,True,True),
            ('maximum',request+base+'*(volatile uint32_t*)0x400900f4=65536;result[0]=17;',0x400900f4,4,'write',65536,17,3,0x20010000,65536,True,True),
            ('order',base,0x400900f0,4,'write',0x20010000,None,0,0,0,True,True),
            ('flags','*(volatile uint32_t*)0x400900ec=0x20010004;',0x400900ec,4,'write',0x20010004,None,0,0,0,True,True),
            ('outside','*(volatile uint32_t*)0x400900ec=0x40010006;',0x400900ec,4,'write',0x40010006,None,0,0,0,True,True),
            ('base-mismatch',request+'*(volatile uint32_t*)0x400900f0=0x20010008;',0x400900f0,4,'write',0x20010008,None,1,0x20010000,0,True,True),
            ('early-size',request+length,0x400900f4,4,'write',4864,None,1,0x20010000,0,True,True),
            ('zero-size',request+base+'*(volatile uint32_t*)0x400900f4=0;',0x400900f4,4,'write',0,None,2,0x20010000,0,True,True),
            ('unaligned-size',request+base+'*(volatile uint32_t*)0x400900f4=4865;',0x400900f4,4,'write',4865,None,2,0x20010000,0,True,True),
            ('overflow','*(volatile uint32_t*)0x400900ec=0x2037fff6;*(volatile uint32_t*)0x400900f0=0x2037fff0;*(volatile uint32_t*)0x400900f4=32;',0x400900f4,4,'write',32,None,2,0x2037fff0,0,True,True),
            ('read',request+base+length+'result[0]=*(volatile uint32_t*)0x400900f0;',0x400900f0,4,'read',0,None,3,0x20010000,4864,True,True),
            ('repeat',request+base+length+request,0x400900ec,4,'write',0x20010006,None,3,0x20010000,4864,True,True),
            ('submit',request+base+length+'*(volatile uint32_t*)0x400900ec=0x20010014;',0x400900ec,4,'write',0x20010014,None,3,0x20010000,4864,True,True),
            ('partial',request+'*(volatile uint16_t*)0x400900f0=0;',0x400900f0,2,'write',0,None,1,0x20010000,0,True,True),
            ('before-id',request,0x400900ec,4,'write',0x20010006,None,0,0,0,True,False),
            ('disabled',request,0x400900ec,4,'write',0x20010006,None,0,0,0,False,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-id-initial'))
            prefix=spec['code'].split('result[0]=',1)[0]
            if not ready:
                init='*(volatile uint32_t*)0x40090148=0;'
                assert prefix.endswith(init)
                prefix=prefix[:-len(init)];spec['gpu_id']=False
            spec.pop('returned',None)
            spec.update(name='gpu-ring-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_ring']=dict(steps_completed=step,request_word=(start|6) if step else 0,base_address=start,byte_length=size)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_identity_response:
        import copy
        for label,code,addr,width,op,value,returned,profile,reads,ready in [
            ('source','result[0]=*(volatile uint32_t*)0x400901ec;',0x400901ec,4,'read',0,0x86362000,1,1,True),
            ('repeat','result[0]=*(volatile uint32_t*)0x400901ec ^ *(volatile uint32_t*)0x400901ec;',0x400901ec,4,'read',0,0,1,2,True),
            ('absent','result[0]=*(volatile uint32_t*)0x400901ec;',0x400901ec,4,'read',0,0,0,1,True),
            ('write','*(volatile uint32_t*)0x400901ec=0x86362000;',0x400901ec,4,'write',0x86362000,None,1,0,True),
            ('partial','result[0]=*(volatile uint16_t*)0x400901ec;',0x400901ec,2,'read',0,None,1,0,True),
            ('before-ring','result[0]=*(volatile uint32_t*)0x400901ec;',0x400901ec,4,'read',0,None,1,0,False),
            ('neighbor','result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,1,0,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x400901ec;',0x400901ec,4,'read',0,None,None,0,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-ring-complete'))
            prefix=spec['code'].split('result[0]=',1)[0]
            if not ready:
                prefix=prefix.split('*(volatile uint32_t*)0x400900ec=',1)[0]
                spec['gpu_ring']=dict(steps_completed=0,request_word=0,base_address=0,byte_length=0)
            spec.pop('returned',None)
            spec.update(name='gpu-identity-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if profile is not None:spec['gpu_identity']=dict(profile=profile,reads=reads)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_initial_resets:
        import copy
        cp='*(volatile uint32_t*)0x400900e8=0;'
        gpu='*(volatile uint32_t*)0x400900fc=0;'
        identity='(void)*(volatile uint32_t*)0x400901ec;'
        for label,code,addr,width,op,value,returned,steps,enabled,read_identity in [
            ('complete',cp+gpu+'result[0]=17;',0x400900fc,4,'write',0,17,2,True,True),
            ('command-only',cp+'result[0]=17;',0x400900e8,4,'write',0,17,1,True,True),
            ('order',gpu,0x400900fc,4,'write',0,None,0,True,True),
            ('nonzero','*(volatile uint32_t*)0x400900e8=1;',0x400900e8,4,'write',1,None,0,True,True),
            ('repeat',cp+cp,0x400900e8,4,'write',0,None,1,True,True),
            ('bad-gpu',cp+'*(volatile uint32_t*)0x400900fc=1;',0x400900fc,4,'write',1,None,1,True,True),
            ('status-read',cp+gpu+'result[0]=*(volatile uint32_t*)0x400900e8;',0x400900e8,4,'read',0,None,2,True,True),
            ('extension',cp+gpu+'*(volatile uint32_t*)0x40090388=1;',0x40090388,4,'write',1,None,2,True,True),
            ('before-identity',cp,0x400900e8,4,'write',0,None,0,True,False),
            ('partial','*(volatile uint16_t*)0x400900e8=0;',0x400900e8,2,'write',0,None,0,True,True),
            ('disabled',cp,0x400900e8,4,'write',0,None,0,False,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-identity-source'))
            prefix=spec['code'].split('result[0]=',1)[0]
            if read_identity:prefix+=identity
            spec['gpu_identity']['reads']=1 if read_identity else 0
            spec.pop('returned',None)
            spec.update(name='gpu-reset-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_reset']=dict(steps_completed=steps,command_processor_resets=1 if steps else 0,gpu_resets=1 if steps==2 else 0,ring_requires_revalidation=bool(steps))
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_raster_init_storage:
        import copy
        store='*(volatile uint32_t*)0x40090388=1;'
        for label,code,addr,width,op,value,returned,stored,enabled,ready in [
            ('store',store+'result[0]=17;',0x40090388,4,'write',1,17,True,True,True),
            ('zero','*(volatile uint32_t*)0x40090388=0;',0x40090388,4,'write',0,None,False,True,True),
            ('other','*(volatile uint32_t*)0x40090388=2;',0x40090388,4,'write',2,None,False,True,True),
            ('repeat',store+store,0x40090388,4,'write',1,None,True,True,True),
            ('before-reset',store,0x40090388,4,'write',1,None,False,True,False),
            ('read',store+'result[0]=*(volatile uint32_t*)0x40090388;',0x40090388,4,'read',0,None,True,True,True),
            ('partial','*(volatile uint16_t*)0x40090388=1;',0x40090388,2,'write',1,None,False,True,True),
            ('neighbor','*(volatile uint32_t*)0x40090384=1;',0x40090384,4,'write',1,None,False,True,True),
            ('disabled',store,0x40090388,4,'write',1,None,False,False,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-reset-complete'))
            prefix=spec['code'].split('result[0]=',1)[0]
            if not ready:
                reset='*(volatile uint32_t*)0x400900e8=0;*(volatile uint32_t*)0x400900fc=0;'
                assert prefix.endswith(reset)
                prefix=prefix[:-len(reset)]
                spec['gpu_reset']=dict(steps_completed=0,command_processor_resets=0,gpu_resets=0,ring_requires_revalidation=False)
            spec.pop('returned',None)
            spec.update(name='gpu-raster-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_raster']=stored
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_config_response:
        import copy
        for label,code,addr,width,op,value,returned,lowreads,highreads,high,enabled,ready in [
            ('low','result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,0xf4030105,1,0,-1,True,True),
            ('repeat','result[0]=*(volatile uint32_t*)0x400901f0 ^ *(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,0,2,0,-1,True,True),
            ('high-zero','result[0]=*(volatile uint32_t*)0x400901f4;',0x400901f4,4,'read',0,0,0,1,0,True,True),
            ('high-bit9','result[0]=*(volatile uint32_t*)0x400901f4;',0x400901f4,4,'read',0,512,0,1,512,True,True),
            ('high-unknown','(void)*(volatile uint32_t*)0x400901f0;result[0]=*(volatile uint32_t*)0x400901f4;',0x400901f4,4,'read',0,None,1,0,-1,True,True),
            ('before-store','result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,0,0,-1,True,False),
            ('write-low','*(volatile uint32_t*)0x400901f0=0xf4030105;',0x400901f0,4,'write',0xf4030105,None,0,0,-1,True,True),
            ('write-high','*(volatile uint32_t*)0x400901f4=0;',0x400901f4,4,'write',0,None,0,0,0,True,True),
            ('partial','result[0]=*(volatile uint16_t*)0x400901f0;',0x400901f0,2,'read',0,None,0,0,-1,True,True),
            ('neighbor','result[0]=*(volatile uint32_t*)0x400901f8;',0x400901f8,4,'read',0,None,0,0,-1,True,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,0,0,-1,False,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-raster-store'))
            prefix=spec['code'].split('result[0]=',1)[0]
            if not ready:
                store='*(volatile uint32_t*)0x40090388=1;';assert prefix.endswith(store)
                prefix=prefix[:-len(store)];spec['gpu_raster']=False
            spec.pop('returned',None)
            spec.update(name='gpu-config-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if enabled:spec['gpu_config']=dict(low_reads=lowreads,high_reads=highreads,high_hypothesis=high)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_initial_status:
        import copy
        for label,code,addr,width,op,value,returned,profile,reads,ready in [
            ('zero','result[0]=*(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,0,0,1,True),
            ('nonzero','result[0]=*(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,1,1,1,True),
            ('repeat','result[0]=*(volatile uint32_t*)0x400900fc ^ *(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,0,0,2,True),
            ('before-store','result[0]=*(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,None,0,0,False),
            ('partial','result[0]=*(volatile uint16_t*)0x400900fc;',0x400900fc,2,'read',0,None,0,0,True),
            ('write','*(volatile uint32_t*)0x400900fc=0;',0x400900fc,4,'write',0,None,0,0,True),
            ('neighbor','result[0]=*(volatile uint32_t*)0x400900e4;',0x400900e4,4,'read',0,None,0,0,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,None,None,0,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-config-low'))
            prefix=spec['code'].split('result[0]=',1)[0]
            spec['gpu_config']=dict(low_reads=0,high_reads=0,high_hypothesis=0)
            if not ready:
                store='*(volatile uint32_t*)0x40090388=1;';assert prefix.endswith(store)
                prefix=prefix[:-len(store)];spec['gpu_raster']=False
            spec.pop('returned',None)
            spec.update(name='gpu-status-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if profile is not None:spec['gpu_status']=dict(profile=profile,reads=reads)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_power_off:
        import copy
        off='*(volatile uint32_t*)0x40021004=0;'
        poll='(void)*(volatile uint32_t*)0x40021008;'
        for label,profile,code,addr,width,op,value,returned,polls,phase,status in [
            ('off',1,off+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0,1,'powered-off',0),
            ('stuck-on',0,off+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x40000,1,'stuck-on',0x40000),
            ('request',1,off+'result[0]=*(volatile uint32_t*)0x40021004;',0x40021004,4,'read',0,0,0,'off-requested',0x40000),
            ('repeat-status',1,off+poll+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0,2,'powered-off',0),
            ('re-enable',1,off+poll+'*(volatile uint32_t*)0x40021004=0x40000;',0x40021004,4,'write',0x40000,None,1,'powered-off',0),
            ('config-off',1,off+poll+'result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,1,'powered-off',0),
            ('config-pending',1,off+'result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,0,'off-requested',0x40000),
            ('config-stuck',0,off+poll+'result[0]=*(volatile uint32_t*)0x400901f0;',0x400901f0,4,'read',0,None,1,'stuck-on',0x40000),
            ('irq-off',1,off+poll+'*(volatile uint32_t*)0x400900f8=0;',0x400900f8,4,'write',0,None,1,'powered-off',0),
            ('ring-off',1,off+poll+'*(volatile uint32_t*)0x400900ec=0x20010004;',0x400900ec,4,'write',0x20010004,None,1,'powered-off',0),
            ('status-off',1,off+poll+'result[0]=*(volatile uint32_t*)0x400900fc;',0x400900fc,4,'read',0,None,1,'powered-off',0),
            ('partial',1,'*(volatile uint16_t*)0x40021004=0;',0x40021004,2,'write',0,None,0,'on',0x40000)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-status-zero'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            requested=label!='partial'
            spec.update(name='gpu-off-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            spec['gpu_status']['reads']=0
            er=int(label=='request')
            spec['power'].update(phase=phase,request_word=0 if requested else 0x40000,status_word=status,
                                 status_reads=2+polls,enable_reads=er,enable_writes=1+int(requested),transitions=2+int(requested)+int(polls>0))
            spec['controls'].update(device_reads=2+polls+er,device_writes=1+int(requested))
            spec['gpu_off']=dict(profile=profile,epoch_retired=requested,requests=int(requested))
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpu_power_off:
        # Initial ring configuration is valid while on, unlike the always-blocked submit path.
        import copy
        for label,profile,transition,phase,status,polls,requested in [
            ('on',1,'','on',0x40000,0,False),
            ('pending',1,'*(volatile uint32_t*)0x40021004=0;','off-requested',0x40000,0,True),
            ('off',1,'*(volatile uint32_t*)0x40021004=0;(void)*(volatile uint32_t*)0x40021008;','powered-off',0,1,True),
            ('stuck',0,'*(volatile uint32_t*)0x40021004=0;(void)*(volatile uint32_t*)0x40021008;','stuck-on',0x40000,1,True)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='gpu-id-initial'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            spec.update(name='gpu-off-ring-init-'+label,code=prefix+transition+'*(volatile uint32_t*)0x400900ec=0x20010006;result[0]=17;',address=0x400900ec,width=4,operation='write',write_value=0x20010006)
            spec['gpu_ring']=dict(steps_completed=0 if requested else 1,request_word=0 if requested else 0x20010006,base_address=0 if requested else 0x20010000,byte_length=0)
            spec['power'].update(phase=phase,request_word=0 if requested else 0x40000,status_word=status,status_reads=2+polls,enable_reads=0,enable_writes=1+int(requested),transitions=2+int(requested)+int(polls>0))
            spec['controls'].update(device_reads=2+polls,device_writes=1+int(requested))
            spec['gpu_off']=dict(profile=profile,epoch_retired=requested,requests=int(requested))
            if not requested:spec['returned']=17
            selections.append(spec)
    if args.with_gpu_off_sequence:
        import copy
        fields=[(0x40020080,1023,None),(0x40020088,63,5)]
        fields += [(0x40020380,1<<b,1<<b) for b in [29,28,31,30]]
        fields += [(0x40020344,0x3e000000,6<<25),(0x40020344,0xf800,6<<11),
                   (0x4002034c,0x3e000000,5<<25),(0x4002034c,0xf800,5<<11),
                   (0x40020358,0x1f00,7<<8),(0x40020354,0x3e0000,10<<17),
                   (0x40020080,1023,None),(0x40020088,63,1)]
        fields += [(0x40020380,1<<b,0) for b in [29,28,31,30]]
        for label,n,enabled,state,badaddr,width,badval,badcode,returned in [
            ('complete',18,True,'off',0x40020380,4,0,'',17),
            ('wrong-first',0,True,'off',0x40020080,4,0x6d7d9,'*(volatile uint32_t*)0x40020080=0x6d7d9;',None),
            ('wrong-order',1,True,'off',0x40020380,4,0x20011000,'*(volatile uint32_t*)0x40020380=0x20011000;',None),
            ('wrong-ton',11,True,'off',0x40020354,4,0x260000,'*(volatile uint32_t*)0x40020354=0x260000;',None),
            ('restore-order',12,True,'off',0x40020380,4,0xd0011000,'*(volatile uint32_t*)0x40020380=0xd0011000;',None),
            ('partial',0,True,'off',0x40020080,2,0xd3d9,'*(volatile uint16_t*)0x40020080=0xd3d9;',None),
            ('repeat',18,True,'off',0x40020080,4,0x6d3d9,'*(volatile uint32_t*)0x40020080=0x6d3d9;',None),
            ('disabled',0,False,'off',0x40020080,4,0x6d3d9,'*(volatile uint32_t*)0x40020080=0x6d3d9;',None),
            ('pending',0,True,'pending',0x40020080,4,0x6d3d9,'*(volatile uint32_t*)0x40020080=0x6d3d9;',None),
            ('stuck-on',0,True,'stuck',0x40020080,4,0x6d3d9,'*(volatile uint32_t*)0x40020080=0x6d3d9;',None)]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')==('gpu-off-stuck-on' if state=='stuck' else 'gpu-off-off')))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            if state=='pending':
                spec['power'].update(phase='off-requested',status_word=0x40000,status_reads=2,transitions=3)
                spec['controls']['device_reads']-=1
            else:prefix+='(void)*(volatile uint32_t*)0x40021008;'
            original=spec['hal']['0x40020080']['value'];actions=[]
            for j,(a,mask,field) in enumerate(fields[:n]):
                r=spec['hal'][hex(a)]
                if j==0:
                    field=min((original&1023)+12,1023)
                    code='uint32_t offSaved=*(volatile uint32_t*)0x40020080;uint32_t offBoost=(offSaved&1023)>1011?1023:(offSaved&1023)+12;*(volatile uint32_t*)0x40020080=(offSaved&~1023u)|offBoost;'
                elif j==12:
                    field=original&1023;code='*(volatile uint32_t*)0x40020080=(*(volatile uint32_t*)0x40020080&~1023u)|(offSaved&1023);'
                else:code=f'*(volatile uint32_t*)0x{a:x}=(*(volatile uint32_t*)0x{a:x}&~0x{mask:x}u)|0x{field:x}u;'
                r['value']=(r['value']&~mask)|field;r['reads']+=1;r['writes']+=1;actions.append(code)
            spec.update(name='gpu-off-sequence-'+label,code=prefix+''.join(actions)+badcode,address=badaddr,width=width,operation='write',write_value=badval)
            if enabled:spec['gpu_off_sequence']=dict(steps_completed=n,complete=n==18,original_core_word=original if n else 0,boost_delta=min((original&1023)+12,1023)-(original&1023) if n else 0)
            if returned is not None:spec['code']+='result[0]=17;';spec['returned']=returned
            selections.append(spec)
    if args.with_prefetch_storage:
        address=0xe001e004
        for name,op,width,value,code,state,returned in [
            ('default','write',4,0x369,None,dict(initialized=True,value=0x369,reads=1,writes=1),0x369),
            ('zero','write',4,0,None,dict(initialized=True,value=0,reads=1,writes=1),0),
            ('all-fields','write',4,0,'result[0]=0;for(uint32_t v=0;v<1024;v++){*(volatile uint32_t*)0xe001e004=v;result[0]+=(*(volatile uint32_t*)0xe001e004!=v);}',dict(initialized=True,value=1023,reads=1024,writes=1024),0),
            ('initial-read','read',4,0,None,{},None),
            ('reserved','write',4,0x400,None,{},None),
            ('partial-write','write',2,0x369,None,{},None),
            ('partial-read','read',2,0,None,{},None),
            ('byte-after-write','read',1,0,'*(volatile uint32_t*)0xe001e004=0x369;result[0]=*(volatile uint8_t*)0xe001e004;',dict(initialized=True,value=0x369,writes=1),None),
            ('neighbor','write',4,0,None,{},None),
            ('repeat','write',4,0x3ff,'*(volatile uint32_t*)0xe001e004=0x369;*(volatile uint32_t*)0xe001e004=0;*(volatile uint32_t*)0xe001e004=0x3ff;result[0]=*(volatile uint32_t*)0xe001e004;',dict(initialized=True,value=1023,reads=1,writes=3),1023),
            ('disabled','write',4,0x369,None,None,None)]:
            spec=dict(name='prefetch-'+name,address=0xe001e000 if name=='neighbor' else address,
                      operation=op,width=width,write_value=value,controls={})
            if code is not None:spec['code']=code
            if state is not None:spec['prefetch']=dict(initialized=False,value=None,reads=0,writes=0,**{})|state
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpio_config:
        unlock='*(volatile uint32_t*)0x40010400=0x73;'
        lock='*(volatile uint32_t*)0x40010400=0;'
        write='*(volatile uint32_t*)0x40010000=0x20;'
        read='result[0]=*(volatile uint32_t*)0x40010000;'
        for label,code,addr,width,op,value,returned,keys,writes,reads,unlocked,values,enabled in [
            ('write-lock-read',unlock+write+lock+read,0x40010000,4,'read',0,0x20,2,1,1,False,{'0x40010000':0x20},True),
            ('unlocked-read',unlock+write+read,0x40010000,4,'read',0,0x20,1,1,1,True,{'0x40010000':0x20},True),
            ('locked-write',write,0x40010000,4,'write',0x20,None,0,0,0,False,{},True),
            ('wrong-key','*(volatile uint32_t*)0x40010400=1;',0x40010400,4,'write',1,None,0,0,0,False,{},True),
            ('key-read',unlock+'result[0]=*(volatile uint32_t*)0x40010400;',0x40010400,4,'read',0,None,1,0,0,True,{},True),
            ('reserved-bit',unlock+'*(volatile uint32_t*)0x40010000=0x80000000;',0x40010000,4,'write',0x80000000,None,1,0,0,True,{},True),
            ('partial-key','*(volatile uint16_t*)0x40010400=0x73;',0x40010400,2,'write',0x73,None,0,0,0,False,{},True),
            ('partial-pin',unlock+'*(volatile uint16_t*)0x40010000=0;',0x40010000,2,'write',0,None,1,0,0,True,{},True),
            ('last-pin',unlock+'*(volatile uint32_t*)0x4001037c=0x20;result[0]=*(volatile uint32_t*)0x4001037c;',0x4001037c,4,'read',0,0x20,1,1,1,True,{'0x4001037c':0x20},True),
            ('beyond-pin',unlock+'*(volatile uint32_t*)0x40010380=0;',0x40010380,4,'write',0,None,1,0,0,True,{},True),
            ('reserved-gap',unlock+'*(volatile uint32_t*)0x400103fc=0;',0x400103fc,4,'write',0,None,1,0,0,True,{},True),
            ('input-read',unlock+'result[0]=*(volatile uint32_t*)0x40010404;',0x40010404,4,'read',0,None,1,0,0,True,{},True),
            ('relocked-write',unlock+write+lock+'*(volatile uint32_t*)0x40010000=0;',0x40010000,4,'write',0,None,2,1,0,False,{'0x40010000':0x20},True),
            ('repeat-write',unlock+write+'*(volatile uint32_t*)0x40010000=0;'+read,0x40010000,4,'read',0,0,1,2,1,True,{'0x40010000':0},True),
            ('initial-read',read,0x40010000,4,'read',0,None,0,0,0,False,{},True),
            ('unwritten-pin',unlock+write+'result[0]=*(volatile uint32_t*)0x40010004;',0x40010004,4,'read',0,None,1,1,0,True,{'0x40010000':0x20},True),
            ('disabled',unlock,0x40010400,4,'write',0x73,None,0,0,0,False,{},False)]:
            spec=dict(name='gpio-'+label,controls={},address=addr,width=width,operation=op,write_value=value,code=code)
            if enabled:spec['gpio_config']=dict(unlocked=unlocked,key_writes=keys,config_writes=writes,config_reads=reads,values=values)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpio_interrupt_idle:
        for label,code,addr,width,op,value,returned,en,clr,er,ew,sr,cw,enabled in [
            ('initial-en','result[0]=*(volatile uint32_t*)0x40010530;',0x40010530,4,'read',0,0,{}, {},1,0,0,0,True),
            ('initial-status','result[0]=*(volatile uint32_t*)0x40010604;',0x40010604,4,'read',0,0,{}, {},0,0,1,0,True),
            ('enable-read','*(volatile uint32_t*)0x40010530=16;result[0]=*(volatile uint32_t*)0x40010530;',0x40010530,4,'read',0,16,{0:16},{},1,1,0,0,True),
            ('channel-isolation','*(volatile uint32_t*)0x40010530=16;result[0]=*(volatile uint32_t*)0x400105a0;',0x400105a0,4,'read',0,0,{0:16},{},1,1,0,0,True),
            ('last-enable','*(volatile uint32_t*)0x40010600=0x80000000;result[0]=*(volatile uint32_t*)0x40010600;',0x40010600,4,'read',0,0x80000000,{13:0x80000000},{},1,1,0,0,True),
            ('clear-idle','*(volatile uint32_t*)0x40010608=16;result[0]=*(volatile uint32_t*)0x40010604;',0x40010604,4,'read',0,0,{}, {13:16},0,0,1,1,True),
            ('repeat-clear','*(volatile uint32_t*)0x40010538=16;*(volatile uint32_t*)0x40010538=32;result[0]=*(volatile uint32_t*)0x40010534;',0x40010534,4,'read',0,0,{}, {0:48},0,0,1,2,True),
            ('status-write','*(volatile uint32_t*)0x40010534=1;',0x40010534,4,'write',1,None,{}, {},0,0,0,0,True),
            ('set-write','*(volatile uint32_t*)0x4001053c=1;',0x4001053c,4,'write',1,None,{}, {},0,0,0,0,True),
            ('clear-read','result[0]=*(volatile uint32_t*)0x40010538;',0x40010538,4,'read',0,None,{}, {},0,0,0,0,True),
            ('set-read','result[0]=*(volatile uint32_t*)0x4001053c;',0x4001053c,4,'read',0,None,{}, {},0,0,0,0,True),
            ('partial','result[0]=*(volatile uint16_t*)0x40010530;',0x40010530,2,'read',0,None,{}, {},0,0,0,0,True),
            ('before-range','result[0]=*(volatile uint32_t*)0x4001052c;',0x4001052c,4,'read',0,None,{}, {},0,0,0,0,True),
            ('after-range','result[0]=*(volatile uint32_t*)0x40010610;',0x40010610,4,'read',0,None,{}, {},0,0,0,0,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x40010530;',0x40010530,4,'read',0,None,{}, {},0,0,0,0,False)]:
            spec=dict(name='gpio-idle-'+label,controls={},gpio_config=dict(unlocked=False,key_writes=0,config_writes=0,config_reads=0,values={}),address=addr,width=width,operation=op,write_value=value,code=code)
            if enabled:spec['gpio_idle']=dict(enable_words=[en.get(j,0) for j in range(14)],clear_requests=[clr.get(j,0) for j in range(14)],enable_reads=er,enable_writes=ew,status_reads=sr,clear_writes=cw)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_gpio_output:
        for label,cfg,code,addr,width,op,value,returned,words,reads,direct,sets,clears,enabled in [
            ('set-clear-preserve',{7:0x103,8:0x103},'*(volatile uint32_t*)0x4001043c=0x180;*(volatile uint32_t*)0x40010458=0x80;result[0]=*(volatile uint32_t*)0x40010420;',0x40010420,4,'read',0,0x100,{0:0x100},1,0,1,1,True),
            ('clear-zero',{7:0x103},'*(volatile uint32_t*)0x40010458=0x80;result[0]=*(volatile uint32_t*)0x40010420;',0x40010420,4,'read',0,0,{},1,0,0,1,True),
            ('repeat-set',{7:0x103},'*(volatile uint32_t*)0x4001043c=0x80;*(volatile uint32_t*)0x4001043c=0x80;result[0]=*(volatile uint32_t*)0x40010420;',0x40010420,4,'read',0,0x80,{0:0x80},1,0,2,0,True),
            ('zero-alias',{},'*(volatile uint32_t*)0x4001043c=0;*(volatile uint32_t*)0x40010458=0;result[0]=*(volatile uint32_t*)0x40010420;',0x40010420,4,'read',0,0,{},1,0,1,1,True),
            ('direct-word',{j:0x103 for j in range(32)},'*(volatile uint32_t*)0x40010420=0xa5a5a5a5;result[0]=*(volatile uint32_t*)0x40010420;',0x40010420,4,'read',0,0xa5a5a5a5,{0:0xa5a5a5a5},1,1,0,0,True),
            ('direct-unknown',{7:0x103},'*(volatile uint32_t*)0x40010420=0;',0x40010420,4,'write',0,None,{},0,0,0,0,True),
            ('alias-read',{7:0x103},'*(volatile uint32_t*)0x4001043c=0x80;result[0]=*(volatile uint32_t*)0x4001043c;',0x4001043c,4,'read',0,None,{0:0x80},0,0,1,0,True),
            ('unconfigured',{},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('peripheral-mux',{7:0x101},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('mode-disabled',{7:3},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('open-drain',{7:0x203},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('tristate',{7:0x303},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('force-output',{7:0x08000103},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('force-input',{7:0x04000103},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,True),
            ('reserved-pin',{135:0x103},'*(volatile uint32_t*)0x4001044c=0x80;',0x4001044c,4,'write',0x80,None,{},0,0,0,0,True),
            ('mixed-mask',{7:0x103},'*(volatile uint32_t*)0x4001043c=0x180;',0x4001043c,4,'write',0x180,None,{},0,0,0,0,True),
            ('last-pin',{223:0x103},'*(volatile uint32_t*)0x40010454=0x80000000;result[0]=*(volatile uint32_t*)0x40010438;',0x40010438,4,'read',0,0x80000000,{6:0x80000000},1,0,1,0,True),
            ('partial',{7:0x103},'*(volatile uint16_t*)0x4001043c=0x80;',0x4001043c,2,'write',0x80,None,{},0,0,0,0,True),
            ('disabled',{7:0x103},'*(volatile uint32_t*)0x4001043c=0x80;',0x4001043c,4,'write',0x80,None,{},0,0,0,0,False),
            ('input-read',{7:0x103},'*(volatile uint32_t*)0x4001043c=0x80;result[0]=*(volatile uint32_t*)0x40010404;',0x40010404,4,'read',0,None,{0:0x80},0,0,1,0,True)]:
            prefix=''
            if cfg:
                prefix='*(volatile uint32_t*)0x40010400=0x73;'+''.join(f'*(volatile uint32_t*)0x{0x40010000+pin*4:x}=0x{word:x};' for pin,word in cfg.items())+'*(volatile uint32_t*)0x40010400=0;'
            spec=dict(name='gpio-output-'+label,controls={},gpio_config=dict(unlocked=False,key_writes=2 if cfg else 0,config_writes=len(cfg),config_reads=0,values={hex(0x40010000+pin*4):word for pin,word in cfg.items()}),address=addr,width=width,operation=op,write_value=value,code=prefix+code)
            if enabled:spec['gpio_output']=dict(words=[words.get(j,0) for j in range(7)],reads=reads,direct_writes=direct,set_writes=sets,clear_writes=clears)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_adc_info_zero:
        for label,code,addr,width,op,value,returned,reads,enabled in [
            ('five-words','result[0]=*(volatile uint32_t*)0x42003300 ^ *(volatile uint32_t*)0x42003304 ^ *(volatile uint32_t*)0x42003308 ^ *(volatile uint32_t*)0x42003328 ^ *(volatile uint32_t*)0x4200332c;',0x42003300,4,'read',0,0,[1]*5,True),
            ('repeat','result[0]=*(volatile uint32_t*)0x42003300 ^ *(volatile uint32_t*)0x42003300;',0x42003300,4,'read',0,0,[2,0,0,0,0],True),
            ('last-word','result[0]=*(volatile uint32_t*)0x4200332c;',0x4200332c,4,'read',0,0,[0,0,0,0,1],True),
            ('write','*(volatile uint32_t*)0x42003300=0;',0x42003300,4,'write',0,None,[0]*5,True),
            ('partial','result[0]=*(volatile uint16_t*)0x42003300;',0x42003300,2,'read',0,None,[0]*5,True),
            ('unprovided','result[0]=*(volatile uint32_t*)0x4200330c;',0x4200330c,4,'read',0,None,[0]*5,True),
            ('gap','result[0]=*(volatile uint32_t*)0x42003324;',0x42003324,4,'read',0,None,[0]*5,True),
            ('otp','result[0]=*(volatile uint32_t*)0x42006900;',0x42006900,4,'read',0,None,[0]*5,True),
            ('outside-domain','result[0]=*(volatile uint32_t*)0x40021900;',0x40021900,4,'read',0,None,[0]*5,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x42003300;',0x42003300,4,'read',0,None,[0]*5,False)]:
            spec=dict(name='adc-info-'+label,controls={},source='mram',metadata='zero',address=addr,width=width,operation=op,write_value=value,code=code)
            if enabled:spec['adc_info']=reads
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_adc_calibration_control:
        for label,code,addr,width,op,value,returned,state,reads,writes,enabled in [
            ('initial','result[0]=*(volatile uint32_t*)0x4002010c;',0x4002010c,4,'read',0,1,1,1,0,True),
            ('clear','*(volatile uint32_t*)0x4002010c &= ~1u;result[0]=*(volatile uint32_t*)0x4002010c;',0x4002010c,4,'read',0,0,0,2,1,True),
            ('enable','*(volatile uint32_t*)0x4002010c=0;*(volatile uint32_t*)0x4002010c=1;result[0]=*(volatile uint32_t*)0x4002010c;',0x4002010c,4,'read',0,1,1,1,2,True),
            ('repeat-clear','*(volatile uint32_t*)0x4002010c=0;*(volatile uint32_t*)0x4002010c=0;result[0]=*(volatile uint32_t*)0x4002010c;',0x4002010c,4,'read',0,0,0,1,2,True),
            ('status-zero','result[0]=*(volatile uint32_t*)0x4002010c & 2;',0x4002010c,4,'read',0,0,1,1,0,True),
            ('readonly-bit','*(volatile uint32_t*)0x4002010c=2;',0x4002010c,4,'write',2,None,1,0,0,True),
            ('readonly-plus-enable','*(volatile uint32_t*)0x4002010c=3;',0x4002010c,4,'write',3,None,1,0,0,True),
            ('reserved-bit','*(volatile uint32_t*)0x4002010c=0x80000001;',0x4002010c,4,'write',0x80000001,None,1,0,0,True),
            ('partial-read','result[0]=*(volatile uint16_t*)0x4002010c;',0x4002010c,2,'read',0,None,1,0,0,True),
            ('partial-write','*(volatile uint16_t*)0x4002010c=0;',0x4002010c,2,'write',0,None,1,0,0,True),
            ('neighbor','result[0]=*(volatile uint32_t*)0x40020110;',0x40020110,4,'read',0,None,1,0,0,True),
            ('disabled','result[0]=*(volatile uint32_t*)0x4002010c;',0x4002010c,4,'read',0,None,1,0,0,False)]:
            spec=dict(name='adc-cal-control-'+label,controls={},address=addr,width=width,operation=op,write_value=value,code=code)
            if enabled:spec['adc_cal_control']=dict(initial_word=1,value=state,reads=reads,writes=writes)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_adc_power_response:
        import copy
        enable='*(volatile uint32_t*)0x40021004=0x42000;'
        poll='(void)*(volatile uint32_t*)0x40021008;'
        for label,base,profile,code,addr,width,op,value,returned,phase,req,status,requests,cancels,trans,responses,bankwrites,er,sr,gpuoff,cal in [
            ('on-active','on',1,enable+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x42000,'on',0x2000,0x2000,1,0,2,1,1,0,1,False,'zero'),
            ('on-stuck','on',0,enable+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x40000,'stuck-off',0x2000,0,1,0,2,1,1,0,1,False,'zero'),
            ('request-read','on',1,enable+'result[0]=*(volatile uint32_t*)0x40021004;',0x40021004,4,'read',0,0x42000,'requested',0x2000,0,1,0,1,0,1,1,0,False,'zero'),
            ('off-active','off',1,'*(volatile uint32_t*)0x40021004=0x2000;result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x2000,'on',0x2000,0x2000,1,0,2,1,1,0,1,False,'zero'),
            ('calibration-enabled','on',1,enable,0x40021004,4,'write',0x42000,None,'off',0,0,0,0,0,0,0,0,0,False,'one'),
            ('pending-calibration-change','on',1,enable+'*(volatile uint32_t*)0x4002010c=1;result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,None,'requested',0x2000,0,1,0,1,0,1,0,0,False,'change'),
            ('both-domains','on',1,'*(volatile uint32_t*)0x40021004=0x2000;',0x40021004,4,'write',0x2000,None,'off',0,0,0,0,0,0,0,0,0,True,'zero'),
            ('other-bit','on',1,'*(volatile uint32_t*)0x40021004=0x42001;',0x40021004,4,'write',0x42001,None,'off',0,0,0,0,0,0,0,0,0,False,'zero'),
            ('noop','on',1,enable+enable+'result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x42000,'on',0x2000,0x2000,1,0,2,1,2,0,1,False,'zero'),
            ('cancel-pending','on',1,enable+'*(volatile uint32_t*)0x40021004=0x40000;result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x40000,'cancelled',0,0,1,1,2,0,2,0,1,False,'zero'),
            ('cancel-stuck','on',0,enable+poll+'*(volatile uint32_t*)0x40021004=0x40000;result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x40000,'cancelled',0,0,1,1,3,1,2,0,2,False,'zero'),
            ('adc-off-on','on',1,enable+poll+'*(volatile uint32_t*)0x40021004=0x40000;',0x40021004,4,'write',0x40000,None,'on',0x2000,0x2000,1,0,2,1,1,0,1,False,'zero'),
            ('gpu-off-preserve-adc','on',1,enable+poll+'*(volatile uint32_t*)0x40021004=0x2000;result[0]=*(volatile uint32_t*)0x40021008;',0x40021008,4,'read',0,0x2000,'on',0x2000,0x2000,1,0,2,1,2,0,2,True,'zero'),
            ('retired-gpu-reenable','off',1,'*(volatile uint32_t*)0x40021004=0x2000;'+poll+'*(volatile uint32_t*)0x40021004=0x42000;',0x40021004,4,'write',0x42000,None,'on',0x2000,0x2000,1,0,2,1,1,0,1,False,'zero'),
            ('partial','on',1,'*(volatile uint16_t*)0x40021004=0x2000;',0x40021004,2,'write',0x2000,None,'off',0,0,0,0,0,0,0,0,0,False,'zero'),
            ('status-write','on',1,'*(volatile uint32_t*)0x40021008=0x2000;',0x40021008,4,'write',0x2000,None,'off',0,0,0,0,0,0,0,0,0,False,'zero'),
            ('disabled','on',None,enable,0x40021004,4,'write',0x42000,None,'off',0,0,0,0,0,0,0,0,0,False,'zero')]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')==('gpu-response-active' if base=='on' else 'gpu-off-off')))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            if base=='on':
                spec['power']['enable_reads']-=1;spec['power']['status_reads']-=1;spec['controls']['device_reads']-=2
            else:prefix+=poll
            if cal!='one':prefix+='*(volatile uint32_t*)0x4002010c=0;'
            spec['adc_cal_control']=dict(initial_word=1,value=1 if cal in ('one','change') else 0,reads=0,writes=0 if cal=='one' else 2 if cal=='change' else 1)
            spec.update(name='adc-power-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            spec['power']['enable_reads']+=er;spec['power']['status_reads']+=sr
            spec['controls']['device_reads']+=er+sr;spec['controls']['device_writes']+=bankwrites
            if gpuoff:
                changed=label=='gpu-off-preserve-adc'
                spec['gpu_off']=dict(profile=1,epoch_retired=changed,requests=int(changed))
                if changed:spec['power'].update(phase='powered-off',request_word=0,status_word=0,enable_writes=2,transitions=4)
            if profile is not None:spec['adc_power']=dict(profile=profile,phase=phase,request_word=req,status_word=status,requests=requests,cancellations=cancels,transitions=trans,responses=responses)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_adc_trigger_config:
        import copy
        for label,code,addr,width,op,value,returned,stored,reads,writes,mode in [
            ('initial-read','result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,None,None,0,0,'on'),
            ('config','*(volatile uint32_t*)0x40038040=0x4001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x4001e,0x4001e,1,1,'on'),
            ('max','*(volatile uint32_t*)0x40038040=0x703ff;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x703ff,0x703ff,1,1,'on'),
            ('zero','*(volatile uint32_t*)0x40038040=0;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0,0,1,1,'on'),
            ('rewrite','*(volatile uint32_t*)0x40038040=0x4001e;*(volatile uint32_t*)0x40038040=1;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,1,1,1,2,'on'),
            ('enable','*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,None,0,0,'on'),
            ('reserved','*(volatile uint32_t*)0x40038040=0x400;',0x40038040,4,'write',0x400,None,None,0,0,'on'),
            ('reject-preserves-config','*(volatile uint32_t*)0x40038040=0x4001e;*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,0x4001e,0,1,'on'),
            ('partial-read','result[0]=*(volatile uint16_t*)0x40038040;',0x40038040,2,'read',0,None,None,0,0,'on'),
            ('partial-write','*(volatile uint16_t*)0x40038040=0x1e;',0x40038040,2,'write',0x1e,None,None,0,0,'on'),
            ('neighbor','*(volatile uint32_t*)0x40038044=0;',0x40038044,4,'write',0,None,None,0,0,'on'),
            ('requested','*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,None,0,0,'requested'),
            ('stuck','*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,None,0,0,'stuck-off'),
            ('stuck-read','result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,None,None,0,0,'stuck-off'),
            ('off','*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,None,0,0,'off'),
            ('disabled','*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,None,0,0,'disabled')]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='adc-power-off-active'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            if mode=='off':
                assert prefix.endswith('*(volatile uint32_t*)0x40021004=0x2000;')
                prefix=prefix[:-len('*(volatile uint32_t*)0x40021004=0x2000;')]
                spec['controls']['device_writes']-=1
                spec['adc_power'].update(phase='off',request_word=0,status_word=0,requests=0,transitions=0,responses=0)
            if mode in ('off','requested'):
                spec['power']['status_reads']-=1;spec['controls']['device_reads']-=1
                if mode=='requested':spec['adc_power'].update(phase='requested',status_word=0,transitions=1,responses=0)
            else:prefix+='(void)*(volatile uint32_t*)0x40021008;'
            if mode=='stuck-off':spec['adc_power'].update(profile=0,phase='stuck-off',status_word=0)
            spec.update(name='adc-trigger-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if returned is not None:spec['returned']=returned
            if mode!='disabled':spec['adc_trigger']=dict(configured=stored is not None,value=stored,reads=reads,writes=writes,power_blocks=int(mode in ('off','requested','stuck-off')))
            selections.append(spec)
    if args.with_adc_disabled_config:
        import copy
        cfg='*(volatile uint32_t*)0x40038000=0x2171014;'
        cv={'0x40038000':0x2171014}
        rows=[
            ('initial','result[0]=*(volatile uint32_t*)0x40038000;',0x40038000,4,'read',0,None,{},0,0,'on'),
            ('cfg',cfg+'result[0]=*(volatile uint32_t*)0x40038000;',0x40038000,4,'read',0,0x2171014,cv,1,1,'on'),
            ('cfg-rewrite',cfg+'*(volatile uint32_t*)0x40038000=0x2000000;result[0]=*(volatile uint32_t*)0x40038000;',0x40038000,4,'read',0,0x2000000,{'0x40038000':0x2000000},1,2,'on'),
            ('enable',cfg+'*(volatile uint32_t*)0x40038000=0x2171015;',0x40038000,4,'write',0x2171015,None,cv,0,1,'on'),
            ('reserved','*(volatile uint32_t*)0x40038000=0x2171034;',0x40038000,4,'write',0x2171034,None,{},0,0,'on'),
            ('clock','*(volatile uint32_t*)0x40038000=0x3171014;',0x40038000,4,'write',0x3171014,None,{},0,0,'on'),
            ('trigger','*(volatile uint32_t*)0x40038000=0x2151014;',0x40038000,4,'write',0x2151014,None,{},0,0,'on'),
            ('slot-before-cfg','*(volatile uint32_t*)0x4003800c=0x800001;',0x4003800c,4,'write',0x800001,None,{},0,0,'on'),
            ('unknown-slot',cfg+'result[0]=*(volatile uint32_t*)0x4003800c;',0x4003800c,4,'read',0,None,cv,0,1,'on'),
            ('slot-reserved',cfg+'*(volatile uint32_t*)0x4003800c=0x800005;',0x4003800c,4,'write',0x800005,None,cv,0,1,'on'),
            ('slot-short-tracking',cfg+'*(volatile uint32_t*)0x4003800c=0x7c0001;',0x4003800c,4,'write',0x7c0001,None,cv,0,1,'on'),
            ('slot-channel',cfg+'*(volatile uint32_t*)0x4003800c=0x800c01;',0x4003800c,4,'write',0x800c01,None,cv,0,1,'on'),
            ('slot-max',cfg+'*(volatile uint32_t*)0x40038028=0x7ff0b03;result[0]=*(volatile uint32_t*)0x40038028;',0x40038028,4,'read',0,0x7ff0b03,{**cv,'0x40038028':0x7ff0b03},1,2,'on'),
            ('partial',cfg+'*(volatile uint16_t*)0x40038000=0;',0x40038000,2,'write',0,None,cv,0,1,'on'),
            ('slot-partial',cfg+'result[0]=*(volatile uint16_t*)0x4003800c;',0x4003800c,2,'read',0,None,cv,0,1,'on'),
            ('status',cfg+'result[0]=*(volatile uint32_t*)0x40038004;',0x40038004,4,'read',0,None,cv,0,1,'on'),
            ('software-trigger',cfg+'*(volatile uint32_t*)0x40038008=0x37;',0x40038008,4,'write',0x37,None,cv,0,1,'on'),
            ('slot-outside',cfg+'*(volatile uint32_t*)0x4003802c=0;',0x4003802c,4,'write',0,None,cv,0,1,'on'),
            ('off',cfg,0x40038000,4,'write',0x2171014,None,{},0,0,'off'),
            ('requested',cfg,0x40038000,4,'write',0x2171014,None,{},0,0,'requested'),
            ('stuck',cfg,0x40038000,4,'write',0x2171014,None,{},0,0,'stuck-off'),
            ('disabled',cfg,0x40038000,4,'write',0x2171014,None,{},0,0,'disabled')]
        all_values={**cv,**{hex(0x4003800c+4*i):0x800001+(i<<8) for i in range(8)}}
        all_code=cfg+''.join('*(volatile uint32_t*)'+hex(a)+'='+hex(v)+';(void)*(volatile uint32_t*)'+hex(a)+';' for a,v in ((int(a,16),v) for a,v in list(all_values.items())[1:]))+'result[0]=*(volatile uint32_t*)0x40038028;'
        rows.append(('all-slots',all_code,0x40038028,4,'read',0,0x800701,all_values,9,9,'on'))
        for label,code,addr,width,op,value,returned,values,reads,writes,mode in rows:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='adc-power-off-active'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            if mode=='off':
                assert prefix.endswith('*(volatile uint32_t*)0x40021004=0x2000;')
                prefix=prefix[:-len('*(volatile uint32_t*)0x40021004=0x2000;')];spec['controls']['device_writes']-=1
                spec['adc_power'].update(phase='off',request_word=0,status_word=0,requests=0,transitions=0,responses=0)
            if mode in ('off','requested'):
                spec['power']['status_reads']-=1;spec['controls']['device_reads']-=1
                if mode=='requested':spec['adc_power'].update(phase='requested',status_word=0,transitions=1,responses=0)
            else:prefix+='(void)*(volatile uint32_t*)0x40021008;'
            if mode=='stuck-off':spec['adc_power'].update(profile=0,phase='stuck-off',status_word=0)
            spec.update(name='adc-config-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            if returned is not None:spec['returned']=returned
            if mode!='disabled':spec['adc_config']=dict(values=values,reads=reads,writes=writes,power_blocks=int(mode in ('off','requested','stuck-off')))
            selections.append(spec)
    if args.with_adc_enable_latch:
        import copy
        enable='*(volatile uint32_t*)0x40038000=0x2171015;'
        for label,code,addr,width,op,value,returned,enabled,reads,writes,requests,mode in [
            ('enable',enable+'result[0]=*(volatile uint32_t*)0x40038000;',0x40038000,4,'read',0,0x2171015,True,1,2,1,'normal'),
            ('repeat',enable+enable+'result[0]=*(volatile uint32_t*)0x40038000;',0x40038000,4,'read',0,0x2171015,True,1,3,1,'normal'),
            ('missing-timer',enable,0x40038000,4,'write',0x2171015,None,False,0,1,0,'no-timer'),
            ('missing-cfg',enable,0x40038000,4,'write',0x2171015,None,None,0,0,0,'no-cfg'),
            ('mixed-enable','*(volatile uint32_t*)0x40038000=0x217101d;',0x40038000,4,'write',0x217101d,None,False,0,1,0,'normal'),
            ('enable-only','*(volatile uint32_t*)0x40038000=1;',0x40038000,4,'write',1,None,False,0,1,0,'normal'),
            ('reserved','*(volatile uint32_t*)0x40038000=0x82171015;',0x40038000,4,'write',0x82171015,None,False,0,1,0,'normal'),
            ('disable',enable+'*(volatile uint32_t*)0x40038000=0x2171014;',0x40038000,4,'write',0x2171014,None,True,0,2,1,'normal'),
            ('clear-repeat',enable+'*(volatile uint32_t*)0x40038000=0x2171011;',0x40038000,4,'write',0x2171011,None,True,0,2,1,'normal'),
            ('slot-change',enable+'*(volatile uint32_t*)0x4003800c=0x800001;',0x4003800c,4,'write',0x800001,None,True,0,2,1,'normal'),
            ('timer-change',enable+'*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,True,0,2,1,'normal'),
            ('timer-start',enable+'*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,True,0,2,1,'normal'),
            ('status',enable+'result[0]=*(volatile uint32_t*)0x40038004;',0x40038004,4,'read',0,None,True,0,2,1,'normal'),
            ('software-trigger',enable+'*(volatile uint32_t*)0x40038008=0x37;',0x40038008,4,'write',0x37,None,True,0,2,1,'normal'),
            ('partial','*(volatile uint16_t*)0x40038000=0x1015;',0x40038000,2,'write',0x1015,None,False,0,1,0,'normal'),
            ('disabled',enable,0x40038000,4,'write',0x2171015,None,False,0,1,0,'feature-off')]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='adc-config-cfg'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            if mode=='no-cfg':
                assert prefix.endswith('*(volatile uint32_t*)0x40038000=0x2171014;')
                prefix=prefix[:-len('*(volatile uint32_t*)0x40038000=0x2171014;')]
            if mode!='no-timer':prefix+='*(volatile uint32_t*)0x40038040=0x4001e;'
            spec.update(name='adc-enable-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            spec['adc_config'].update(values={} if enabled is None else {'0x40038000':0x2171015 if enabled else 0x2171014},reads=reads,writes=writes)
            spec['adc_trigger']=dict(configured=mode!='no-timer',value=None if mode=='no-timer' else 0x4001e,reads=0,writes=int(mode!='no-timer'),power_blocks=0)
            if mode!='feature-off':spec['adc_enable']=dict(enable_requests=requests,cfg_bit_set=enabled)
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.with_adc_first_trigger:
        import copy
        for label,code,addr,width,op,value,returned,phase,starts,events,tw,tr,hz,mode in [
            ('armed','*(volatile uint32_t*)0x40038040=0x8004001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x8004001e,'armed',1,0,2,1,16,'normal'),
            ('repeat','*(volatile uint32_t*)0x40038040=0x8004001e;*(volatile uint32_t*)0x40038040=0x8004001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x8004001e,'armed',1,0,3,1,16,'normal'),
            ('event','*(volatile uint32_t*)0x40038040=0x8004001e;for(;;) {}',0x40038040,4,'write',0x8004001e,None,'trigger-consumption-required',1,1,2,0,24000000,'event'),
            ('not-enabled','*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,'idle',0,0,1,0,16,'no-enable'),
            ('wrong-routing','*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,'idle',0,0,1,0,16,'external'),
            ('zero-count','*(volatile uint32_t*)0x40038040=0x80040000;',0x40038040,4,'write',0x80040000,None,'idle',0,0,1,0,16,'zero-count'),
            ('unsupported-divider','*(volatile uint32_t*)0x40038040=0x8003001e;',0x40038040,4,'write',0x8003001e,None,'idle',0,0,1,0,16,'divider'),
            ('fractional-clock','*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,'idle',0,0,1,0,17,'normal'),
            ('changed-start','*(volatile uint32_t*)0x40038040=0x8004001f;',0x40038040,4,'write',0x8004001f,None,'idle',0,0,1,0,16,'normal'),
            ('active-change','*(volatile uint32_t*)0x40038040=0x8004001e;*(volatile uint32_t*)0x40038040=0x8004001f;',0x40038040,4,'write',0x8004001f,None,'armed',1,0,2,0,16,'normal'),
            ('active-disable','*(volatile uint32_t*)0x40038040=0x8004001e;*(volatile uint32_t*)0x40038040=0x4001e;',0x40038040,4,'write',0x4001e,None,'armed',1,0,2,0,16,'normal'),
            ('partial','*(volatile uint16_t*)0x40038042=0x8004;',0x40038042,2,'write',0x8004,None,'idle',0,0,1,0,16,'normal'),
            ('divider1','*(volatile uint32_t*)0x40038040=0x8000001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x8000001e,'armed',1,0,2,1,1,'clock0'),
            ('divider2','*(volatile uint32_t*)0x40038040=0x8001001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x8001001e,'armed',1,0,2,1,2,'clock1'),
            ('divider4','*(volatile uint32_t*)0x40038040=0x8002001e;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x8002001e,'armed',1,0,2,1,4,'clock2'),
            ('max-count','*(volatile uint32_t*)0x40038040=0x800403ff;result[0]=*(volatile uint32_t*)0x40038040;',0x40038040,4,'read',0,0x800403ff,'armed',1,0,2,1,16,'countmax'),
            ('no-event-default','*(volatile uint32_t*)0x40038040=0x8004001e;',0x40038040,4,'write',0x8004001e,None,'idle',0,0,1,0,16,'feature-off')]:
            spec=copy.deepcopy(next(x for x in selections if x.get('name')=='adc-enable-enable'))
            prefix=spec['code'].split('result[0]=',1)[0];spec.pop('returned',None)
            timerword=0x4001e
            if mode=='no-enable':
                assert prefix.endswith('*(volatile uint32_t*)0x40038000=0x2171015;');prefix=prefix[:-len('*(volatile uint32_t*)0x40038000=0x2171015;')]
                spec['adc_enable'].update(enable_requests=0,cfg_bit_set=False);spec['adc_config'].update(values={'0x40038000':0x2171014},writes=1)
            if mode=='external':
                prefix=prefix.replace('0x2171014','0x2071014').replace('0x2171015','0x2071015');spec['adc_config']['values']={'0x40038000':0x2071015}
            if mode in ('zero-count','divider'):
                timerword=0x40000 if mode=='zero-count' else 0x3001e;prefix=prefix.replace('0x4001e;',hex(timerword)+';')
            if mode in ('clock0','clock1','clock2','countmax'):
                timerword={'clock0':0x1e,'clock1':0x1001e,'clock2':0x2001e,'countmax':0x403ff}[mode];prefix=prefix.replace('0x4001e;',hex(timerword)+';')
            spec.update(name='adc-first-'+label,code=prefix+code,address=addr,width=width,operation=op,write_value=value)
            spec['adc_config']['reads']=0
            spec['adc_trigger'].update(value=timerword|0x80000000 if starts else timerword,writes=tw,reads=tr)
            if mode!='feature-off':spec['adc_timer']=dict(source_hz=hz,phase=phase,word=(timerword|0x80000000) if starts else None,divider=(1<<((timerword>>16)&7)) if starts else 0,tick_limit=(timerword&0x3ff) if starts else 0,start_requests=starts,trigger_events=events)
            if mode=='event':spec['conversion_stop']=True
            if returned is not None:spec['returned']=returned
            selections.append(spec)
    if args.case:
        unknown = set(args.case)-{s.get('name', f"{s['operation']}-{s['width']}-{s['address']:x}") for s in selections}
        if unknown:
            raise ValueError('Unknown cases: '+repr(sorted(unknown)))
        selections = [s for s in selections if s.get('name', f"{s['operation']}-{s['width']}-{s['address']:x}") in args.case]
    for spec in selections:
        address, width, operation = (spec[k] for k in ('address', 'width', 'operation'))
        name = spec.get('name', f'{operation}-{width}-{address:x}')
        directory = output/name
        directory.mkdir(mode=0o700)
        shutil.copy2(ROOT/'tools/renode-strict-mmio.cs', directory/'strict.cs')
        shutil.copy2(ROOT/'tests/fixtures/renode-main-minimal.repl', directory/'board.repl')
        fixture_selected = 'mode' in spec or 'latch' in spec or 'controls' in spec or 'source' in spec or 'metadata' in spec or 'silicon' in spec or 'memory' in spec or 'hal' in spec or 'mram' in spec
        if fixture_selected:
            board = (directory/'board.repl').read_text().replace(
                'guard: Miscellaneous.BlackwallStrictMMIO @ sysbus 0x40000000',
                'guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40000000')
            board = board.replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    powerMode: "'+spec.get('mode', 'none')+'"\n'
                '    resetLatch: '+str(spec.get('latch', -1)))
            (directory/'board.repl').write_text(board)
        if 'controls' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    startupControls: true')
            board = board.replace('ppb_guard: Miscellaneous.BlackwallStrictMMIO',
                                  'ppb_guard: Miscellaneous.BlackwallG2StartupFixture')
            board = board.replace('    baseAddress: 0xe0010000',
                '    baseAddress: 0xe0010000\n    startupControls: true')
            (directory/'board.repl').write_text(board)
        if 'source' in spec or 'metadata' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    shadowInfo1: "'+spec.get('source','none')+'"\n'
                '    info1Metadata: "'+spec.get('metadata','none')+'"')
            (directory/'board.repl').write_text(board)
        if 'silicon' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    chipRevision: '+str(spec.get('revision',-1))+'\n'
                '    spotStorage: '+('true' if spec.get('spot') else 'false'))
            (directory/'board.repl').write_text(board)
        if 'memory' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    memoryStartup: true')
            (directory/'board.repl').write_text(board)
        if 'hal' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    halStorage: true')
            (directory/'board.repl').write_text(board)
        if 'mram' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    mramControlStorage: true')
            (directory/'board.repl').write_text(board)
        if 'buck' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    buckOverrideStorage: true')
            (directory/'board.repl').write_text(board)
        if 'start' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    buckStartStorage: true')
            (directory/'board.repl').write_text(board)
        if 'coreldo' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    coreLdoReduction: true')
            (directory/'board.repl').write_text(board)
        if 'memldo' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    memLdoSetup: true')
            (directory/'board.repl').write_text(board)
        if 'status' in spec:
            board = (directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    buckStatusFixture: '+str(spec['status']['code']))
            (directory/'board.repl').write_text(board)
        if 'response' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    buckResponse: '+str(spec['response']['profile'])
                +'\n    vddfTempcoStorage: '+str(spec.get('tempco') is not None).lower())
            (directory/'board.repl').write_text(board)
        if 'adc_timer' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcInternalTrigger: adc_trigger')
            board+='\nadc_trigger: Miscellaneous.BlackwallAdcInternalTrigger\n    sourceHz: '+str(spec['adc_timer']['source_hz'])+'\n'
            (directory/'board.repl').write_text(board)
        if 'adc_enable' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcEnableLatch: true')
            (directory/'board.repl').write_text(board)
        if 'adc_config' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcDisabledConfigStorage: true')
            (directory/'board.repl').write_text(board)
        if 'adc_trigger' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcTriggerConfigStorage: true')
            (directory/'board.repl').write_text(board)
        if 'adc_power' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcPowerResponse: '+str(spec['adc_power']['profile']))
            (directory/'board.repl').write_text(board)
        if 'adc_cal_control' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcCalibrationControl: true')
            (directory/'board.repl').write_text(board)
        if 'adc_info' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    adcInfoZeroFixture: true')
            (directory/'board.repl').write_text(board)
        if 'gpio_output' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpioOutputLatch: true')
            (directory/'board.repl').write_text(board)
        if 'gpio_idle' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpioInterruptIdle: true')
            (directory/'board.repl').write_text(board)
        if 'gpio_config' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpioConfigStorage: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_off_sequence' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuOffSequenceStorage: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_off' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuPowerOffResponse: '+str(spec['gpu_off']['profile']))
            (directory/'board.repl').write_text(board)
        if 'gpu_status' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuInitialStatusHypothesis: '+str(spec['gpu_status']['profile']))
            (directory/'board.repl').write_text(board)
        if 'gpu_config' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuConfigLowResponse: true\n    gpuConfigHighHypothesis: '+str(spec['gpu_config']['high_hypothesis']))
            (directory/'board.repl').write_text(board)
        if 'gpu_raster' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuRasterInitStorage: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_reset' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuInitialResets: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_identity' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuIdentityResponse: '+str(spec['gpu_identity']['profile']))
            (directory/'board.repl').write_text(board)
        if 'gpu_ring' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuRingConfiguration: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_id' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuIdInitialization: true')
            (directory/'board.repl').write_text(board)
        if 'gpu_irq_clear' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000', '    baseAddress: 0x40000000\n    gpuInterruptClear: true')
            (directory/'board.repl').write_text(board)
        if 'power' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    gpuPowerResponse: '+str(spec['power']['profile']))
            (directory/'board.repl').write_text(board)
        if 'preparation' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    gpuPowerPreparation: true')
            (directory/'board.repl').write_text(board)
        if spec.get('hfrc'):
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    hfrcForceControl: true')
            (directory/'board.repl').write_text(board)
        if 'gfx' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    gfxPowerStorage: true')
            (directory/'board.repl').write_text(board)
        if 'clock' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0x40000000',
                '    baseAddress: 0x40000000\n    mcuClockResponse: '+str(spec['clock']['profile']))
            (directory/'board.repl').write_text(board)
        if 'prefetch' in spec:
            board=(directory/'board.repl').read_text().replace('    baseAddress: 0xe0010000',
                '    baseAddress: 0xe0010000\n    prefetchStorage: true')
            (directory/'board.repl').write_text(board)
        write_value = spec.get('write_value', 0x5a)
        access = f'*device = {write_value}; result[0] = *device;' if operation == 'write' else 'result[0] = *device;'
        if 'readback_address' in spec:
            access=f"*device = {write_value}; result[0] = *(volatile uint32_t *)0x{spec['readback_address']:x};"
        if 'pre_write' in spec:
            access=f"*device = {spec['pre_write']}; "+access
        if 'code' in spec: access=spec['code']
        (directory/'fixture.c').write_text('''#include <stdint.h>
void reset(void) {
 volatile uint32_t *sentinel = (volatile uint32_t *)0x20000000;
 volatile uint32_t *result = (volatile uint32_t *)0x20000004;
 volatile uint%d_t *device = (volatile uint%d_t *)0x%x;
 *sentinel = 0x11112222;
 %s
 *sentinel = 0x33334444;
 for (;;) {}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[] = {0x2007fb00,(uintptr_t)reset};
''' % (width*8, width*8, address, access))
        (directory/'fixture.ld').write_text('''ENTRY(reset)
SECTIONS {
 . = 0x438000;
 .vectors : { KEEP(*(.vectors)) }
 .text : { *(.text*) *(.rodata*) }
 /DISCARD/ : { *(.ARM.exidx*) *(.comment*) }
}
''')
        execute(['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55',
                 '-mthumb', '-O1', '-ffreestanding', '-fno-builtin', '-nostdlib',
                 '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld', '-Wl,-T,'+str(directory/'fixture.ld'),
                 str(directory/'fixture.c'), '-o', str(directory/'fixture.elf')], directory, 'compiler')
        guard = 'ppb_guard' if address >= 0xe0000000 else 'guard'
        (directory/'result.py').write_text('''import json
from System import Console
m = monitor.Machine
g = m['sysbus.%s']
fixture = None
if hasattr(g, 'PowerReads'):
    fixture = dict(power_reads=int(g.PowerReads),latch_reads=int(g.LatchReads),
        latch_writes=int(g.LatchWrites),latch_value=int(g.LatchValue),verified=bool(g.HardwareVerified))
prefetch = dict(initialized=bool(g.PrefetchInitialized),value=int(g.PrefetchValue) if g.PrefetchInitialized else None,reads=int(g.PrefetchReads),writes=int(g.PrefetchWrites)) if hasattr(g,'PrefetchStorage') and g.PrefetchStorage else None
status = dict(code=int(g.BuckStatusFixture),reads=int(g.BuckStatusReads)) if hasattr(g,'BuckStatusFixture') and g.BuckStatusFixture != -1 else None
response = dict(profile=int(g.BuckResponse),phase=str(g.BuckResponsePhase),reads=int(g.BuckResponseReads),transitions=int(g.BuckResponseTransitions)) if hasattr(g,'BuckResponse') and g.BuckResponse != -1 else None
adc_timer = dict(source_hz=int(g.AdcInternalTrigger.SourceHz),phase=str(g.AdcInternalTrigger.Phase),word=int(g.AdcInternalTrigger.Word) if g.AdcInternalTrigger.StartRequests else None,divider=int(g.AdcInternalTrigger.Divider),tick_limit=int(g.AdcInternalTrigger.TickLimit),start_requests=int(g.AdcInternalTrigger.StartRequests),trigger_events=int(g.AdcInternalTrigger.TriggerEvents)) if hasattr(g,'AdcInternalTrigger') and g.AdcInternalTrigger is not None else None
adc_enable = dict(enable_requests=int(g.AdcDisabledConfig.EnableRequests),cfg_bit_set=bool(g.AdcDisabledConfig.Enabled) if g.AdcDisabledConfig.Values.ContainsKey(0x40038000) else None) if hasattr(g,'AdcDisabledConfig') and g.AdcDisabledConfig is not None and g.AdcDisabledConfig.EnableLatch else None
adc_config = dict(values={hex(int(a)):int(g.AdcDisabledConfig.Values[a]) for a in g.AdcDisabledConfig.Values.Keys},reads=int(g.AdcDisabledConfig.Reads),writes=int(g.AdcDisabledConfig.Writes),power_blocks=int(g.AdcDisabledConfig.PowerBlocks)) if hasattr(g,'AdcDisabledConfig') and g.AdcDisabledConfig is not None else None
adc_trigger = dict(configured=bool(g.AdcTriggerConfigured),value=int(g.AdcTriggerConfig.Value) if g.AdcTriggerConfigured else None,reads=int(g.AdcTriggerConfig.Reads),writes=int(g.AdcTriggerConfig.Writes),power_blocks=int(g.AdcTriggerPowerBlocks)) if hasattr(g,'AdcTriggerConfig') and g.AdcTriggerConfig is not None else None
adc_power = dict(profile=int(g.AdcPower.Profile),phase=str(g.AdcPower.Phase),request_word=int(g.AdcPower.RequestWord),status_word=int(g.AdcPower.StatusWord),requests=int(g.AdcPower.Requests),cancellations=int(g.AdcPower.Cancellations),transitions=int(g.AdcPower.Transitions),responses=int(g.AdcPower.Responses)) if hasattr(g,'AdcPower') and g.AdcPower is not None else None
adc_cal_control = dict(initial_word=int(g.AdcCalibrationControl.InitialValue),value=int(g.AdcCalibrationControl.Value),reads=int(g.AdcCalibrationControl.Reads),writes=int(g.AdcCalibrationControl.Writes)) if hasattr(g,'AdcCalibrationControl') and g.AdcCalibrationControl is not None else None
adc_info = [int(g.AdcInfo.Reads[i]) for i in range(5)] if hasattr(g,'AdcInfo') and g.AdcInfo is not None else None
gpio_output = dict(words=[int(g.GpioOutput.Words[i]) for i in range(7)],reads=int(g.GpioOutput.Reads),direct_writes=int(g.GpioOutput.DirectWrites),set_writes=int(g.GpioOutput.SetWrites),clear_writes=int(g.GpioOutput.ClearWrites)) if hasattr(g,'GpioOutput') and g.GpioOutput is not None else None
gpio_idle = dict(enable_words=[int(g.GpioInterrupts.EnableWords[i]) for i in range(14)],clear_requests=[int(g.GpioInterrupts.ClearRequests[i]) for i in range(14)],enable_reads=int(g.GpioInterrupts.EnableReads),enable_writes=int(g.GpioInterrupts.EnableWrites),status_reads=int(g.GpioInterrupts.StatusReads),clear_writes=int(g.GpioInterrupts.ClearWrites)) if hasattr(g,'GpioInterrupts') and g.GpioInterrupts is not None else None
gpio_config = dict(unlocked=bool(g.GpioConfig.Unlocked),key_writes=int(g.GpioConfig.KeyWrites),config_writes=int(g.GpioConfig.ConfigWrites),config_reads=int(g.GpioConfig.ConfigReads),values={hex(int(a)):int(g.GpioConfig.Values[a]) for a in g.GpioConfig.Values.Keys}) if hasattr(g,'GpioConfig') and g.GpioConfig is not None else None
gpu_off_sequence = dict(steps_completed=int(g.GpuOffSequence.StepsCompleted),complete=bool(g.GpuOffSequence.Complete),original_core_word=int(g.GpuOffSequence.OriginalCoreWord),boost_delta=int(g.GpuOffSequence.BoostDelta)) if hasattr(g,'GpuOffSequence') and g.GpuOffSequence is not None else None
gpu_off = dict(profile=int(g.GpuPower.OffProfile),epoch_retired=bool(g.GpuPower.EpochRetired),requests=int(g.GpuPower.OffRequests)) if hasattr(g,'GpuPower') and g.GpuPower is not None and int(g.GpuPower.OffProfile)!=-1 else None
gpu_status = dict(profile=int(g.GpuInitialStatusHypothesis),reads=int(g.GpuInitialStatusReads)) if hasattr(g,'GpuInitialStatusHypothesis') and g.GpuInitialStatusHypothesis!=-1 else None
gpu_config = dict(low_reads=int(g.GpuConfigLowReads),high_reads=int(g.GpuConfigHighReads),high_hypothesis=int(g.GpuConfigHighHypothesis)) if hasattr(g,'GpuConfigLowResponse') and g.GpuConfigLowResponse else None
gpu_raster = bool(g.GpuRasterInitStored) if hasattr(g,'GpuRasterInitStorage') and g.GpuRasterInitStorage else None
gpu_reset = dict(steps_completed=int(g.GpuReset.StepsCompleted),command_processor_resets=int(g.GpuReset.CommandProcessorResets),gpu_resets=int(g.GpuReset.GpuResets),ring_requires_revalidation=bool(g.GpuReset.RingRequiresRevalidation)) if hasattr(g,'GpuReset') and g.GpuReset is not None else None
gpu_identity = dict(profile=int(g.GpuIdentityProfile),reads=int(g.GpuIdentityReads)) if hasattr(g,'GpuIdentityProfile') and g.GpuIdentityProfile!=-1 else None
gpu_ring = dict(steps_completed=int(g.GpuRing.StepsCompleted),request_word=int(g.GpuRing.RequestWord),base_address=int(g.GpuRing.BaseAddress),byte_length=int(g.GpuRing.ByteLength)) if hasattr(g,'GpuRing') and g.GpuRing is not None else None
gpu_id = bool(g.GpuIdInitialized) if hasattr(g,'GpuIdInitialization') and g.GpuIdInitialization else None
gpu_irq_clear = int(g.GpuInterruptClears) if hasattr(g,'GpuInterruptClear') and g.GpuInterruptClear else None
power = dict(profile=int(g.GpuPower.Profile),phase=str(g.GpuPower.Phase),request_word=int(g.GpuPower.RequestWord),status_word=int(g.GpuPower.StatusWord),enable_reads=int(g.GpuPower.EnableReads),status_reads=int(g.GpuPower.StatusReads),enable_writes=int(g.GpuPower.EnableWrites),transitions=int(g.GpuPower.Transitions)) if hasattr(g,'GpuPower') and g.GpuPower is not None else None
preparation = dict(steps_completed=int(g.GpuPreparation.StepsCompleted),complete=bool(g.GpuPreparation.Complete),original_core_word=int(g.GpuPreparation.OriginalCoreWord),boost_delta=int(g.GpuPreparation.BoostDelta)) if hasattr(g,'GpuPreparation') and g.GpuPreparation is not None else None
gfx = dict(selection=int(g.GfxPower.Selection),request=int(g.GfxPower.Request),selection_reads=int(g.GfxPower.SelectionReads),request_reads=int(g.GfxPower.RequestReads),selection_writes=int(g.GfxPower.SelectionWrites),request_writes=int(g.GfxPower.RequestWrites)) if hasattr(g,'GfxPower') and g.GfxPower is not None else None
clock = dict(profile=int(g.McuClock.Profile),phase=str(g.McuClock.Phase),mode_word=int(g.McuClock.ModeWord),force_writes=int(g.McuClock.ForceWrites),clock_reads=int(g.McuClock.ClockReads),mode_reads=int(g.McuClock.ModeReads),mode_writes=int(g.McuClock.ModeWrites),transitions=int(g.McuClock.Transitions),misc_word=int(g.McuClock.MiscWord),enabled=bool(g.McuClock.Enabled),ready=bool(g.McuClock.Ready)) if hasattr(g,'McuClock') and g.McuClock is not None else None
tempco = dict(applied=bool(g.VddfTempco.Applied),original_word=int(g.VddfTempco.OriginalWord),reduced_trim=int(g.VddfTempco.ReducedTrim)) if hasattr(g,'VddfTempco') and g.VddfTempco is not None else None
memldo = dict(steps_completed=int(g.MemLdo.StepsCompleted)) if hasattr(g,'MemLdo') and g.MemLdo is not None else None
coreldo = None
if hasattr(g,'CoreLdo') and g.CoreLdo is not None:
    coreldo=dict(applied=bool(g.CoreLdo.Applied),cache_witness=bool(g.CoreLdo.CacheWitness),
        original_word=int(g.CoreLdo.OriginalWord),expected_word=(int(g.CoreLdo.OriginalWord)&~0x3ff)|int(g.CoreLdo.ReducedTrim))
start = None
if hasattr(g,'BuckStart') and g.BuckStart is not None:
    start=dict(steps_completed=int(g.BuckStart.StepsCompleted),enable_requested=bool(g.BuckStart.EnableRequested),registers={
        hex(int(a)):dict(value=int(g.BuckStart.Registers[a].Value),reads=int(g.BuckStart.Registers[a].Reads),writes=int(g.BuckStart.Registers[a].Writes))
        for a in g.BuckStart.Registers.Keys})
buck = None
if hasattr(g,'BuckOverrideStorage') and g.BuckOverrideStorage:
    buck=dict(steps_completed=int(g.BuckOverrideStep),complete=bool(g.BuckOverrideComplete))
mram = None
if hasattr(g,'MramControlStorage') and g.MramControlStorage:
    mram=dict(value=int(g.MramValue),reads=int(g.MramReads),writes=int(g.MramWrites))
hal = None
if hasattr(g,'HalStorage') and g.HalStorage is not None:
    hal=dict(catalog_sha256=str(g.HalStorage.TrimCatalogSha256),valid_calibration=False,registers={
        hex(int(address)):dict(value=int(g.HalStorage.Registers[address].Value),
            reads=int(g.HalStorage.Registers[address].Reads),writes=int(g.HalStorage.Registers[address].Writes))
        for address in g.HalStorage.Registers.Keys})
memory = None
if hasattr(g,'MemoryStartup') and g.MemoryStartup is not None:
    memory=dict(rom_disables=int(g.MemoryStartup.RomDisables),registers={
        hex(int(address)):dict(value=int(g.MemoryStartup.Registers[address].Value),
            reads=int(g.MemoryStartup.Registers[address].Reads),writes=int(g.MemoryStartup.Registers[address].Writes))
        for address in g.MemoryStartup.Registers.Keys})
silicon = None
if hasattr(g,'ChipRevision') and (g.ChipRevision != -1 or g.SpotStorage):
    silicon = dict(revision=int(g.ChipRevision),revision_reads=int(g.ChipRevisionReads),
        acrg_value=int(g.AcrgValue),acrg_reads=int(g.AcrgReads),acrg_writes=int(g.AcrgWrites),
        vrctrl_value=int(g.VrctrlValue),vrctrl_reads=int(g.VrctrlReads),vrctrl_writes=int(g.VrctrlWrites),
        analog_power=str(g.AnalogPower),hardware_verified=bool(g.HardwareVerified))
information = None
if hasattr(g,'ShadowInfo1') and (g.ShadowInfo1 != 'none' or g.Info1Metadata != 'none'):
    information = dict(source=str(g.ShadowInfo1), metadata=str(g.Info1Metadata),
        shadow_reads=int(g.ShadowReads),tracker_reads=int(g.TrackerReads),
        revision_reads=int(g.TrimRevisionReads),ft1_reads=int(g.Ft1Reads),valid_calibration=bool(g.ValidCalibration))
controls = None
if hasattr(g,'StartupControls') and g.StartupControls:
    controls = dict(device_reads=int(g.DevicePowerReads),device_writes=int(g.DevicePowerWrites),
        debug_reads=int(g.DebugReads),debug_writes=int(g.DebugWrites),core_reads=int(g.CorePowerReads),
        core_writes=int(g.CorePowerWrites),wic_reads=int(g.WicReads),wic_writes=int(g.WicWrites),wic_value=int(g.WicValue))
Console.WriteLine('BLACKWALL_GUARD '+json.dumps(dict(address=int(g.LastAddress),width=int(g.LastWidth),
    operation=str(g.LastOperation),value=int(g.LastValue),accesses=int(g.AccessCount),
    sentinel=int(m.SystemBus.ReadDoubleWord(0x20000000)),returned=int(m.SystemBus.ReadDoubleWord(0x20000004)),
    fixture=fixture,controls=controls,information=information,silicon=silicon,memory=memory,hal=hal,mram=mram,buck=buck,start=start,coreldo=coreldo,memldo=memldo,status=status,prefetch=prefetch,response=response,tempco=tempco,clock=clock,gfx=gfx,preparation=preparation,power=power,gpu_irq_clear=gpu_irq_clear,gpu_id=gpu_id,gpu_ring=gpu_ring,gpu_identity=gpu_identity,gpu_reset=gpu_reset,gpu_raster=gpu_raster,gpu_config=gpu_config,gpu_status=gpu_status,gpu_off=gpu_off,gpu_off_sequence=gpu_off_sequence,gpio_config=gpio_config,gpio_idle=gpio_idle,gpio_output=gpio_output,adc_info=adc_info,adc_cal_control=adc_cal_control,adc_power=adc_power,adc_trigger=adc_trigger,adc_config=adc_config,adc_enable=adc_enable,adc_timer=adc_timer)))
''' % guard)
        (directory/'probe.resc').write_text('''include @/work/strict.cs
mach create "blackwall-guard-verification"
machine LoadPlatformDescription @/work/board.repl
sysbus LoadELF @/work/fixture.elf
cpu VectorTableOffset 0x438000
start
python "import time; time.sleep(0.2)"
pause
include @/work/result.py
quit
''')
        if 'adc_timer' in spec:
            script=(directory/'probe.resc').read_text()
            marker='\npause\ninclude @/work/result.py'
            if script.count(marker)!=1:raise ValueError('ADC pre-pause insertion ambiguous')
            diagnostic='\npython "from System import Console; Console.WriteLine(\'BLACKWALL_PREPAUSE \'+str(bool(monitor.Machine.IsPaused)))"'
            (directory/'probe.resc').write_text(script.replace(marker,diagnostic+marker))
        log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                       '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                       '--mount', f'type=bind,source={directory},target=/work,readonly', image_id,
                       '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], directory, 'renode')
        lines = [line.partition('BLACKWALL_GUARD ')[2] for line in log.splitlines()
                 if line.startswith('BLACKWALL_GUARD ')]
        if len(lines) != 1:
            raise ValueError('Missing guard result: '+name)
        observed = json.loads(lines[0])
        expected_fixture = None
        if fixture_selected:
            expected_fixture = dict(power_reads=spec.get('power_reads', 0),latch_reads=spec.get('latch_reads', 0),
                latch_writes=spec.get('latch_writes', 0),latch_value=spec.get('final_latch', spec.get('latch', -1)),verified=False)
        expected_controls = None
        if 'controls' in spec:
            expected_controls = dict.fromkeys(('device_reads','device_writes','debug_reads','debug_writes',
                'core_reads','core_writes','wic_reads','wic_writes','wic_value'),0)
            expected_controls.update(spec['controls'])
        if spec.get('conversion_stop'):
            expected = dict(address=0,width=0,operation='none',value=0,accesses=0,sentinel=0x11112222,returned=0,fixture=expected_fixture,controls=expected_controls)
        elif 'returned' in spec:
            expected = dict(address=0, width=0, operation='none', value=0, accesses=0,
                            sentinel=0x33334444,returned=spec['returned'],fixture=expected_fixture,controls=expected_controls)
        else:
            expected = dict(address=address, width=width, operation=operation,
                            value=write_value if operation == 'write' else 0, accesses=1, sentinel=0x11112222,
                            returned=0,fixture=expected_fixture,controls=expected_controls)
        expected['information'] = None
        if 'source' in spec or 'metadata' in spec:
            info = dict(source=spec.get('source','none'),metadata=spec.get('metadata','none'),
                shadow_reads=0,tracker_reads=0,revision_reads=0,ft1_reads=0,valid_calibration=False)
            if spec.get('info_reads'):
                key = {0x400201bc:'shadow_reads',0x42003240:'tracker_reads',
                       0x42003310:'revision_reads',0x42003314:'ft1_reads'}[address]
                info[key] = spec['info_reads']
            expected['information'] = info
        expected['silicon'] = None
        if 'silicon' in spec:
            silicon = dict(revision=spec.get('revision',-1),revision_reads=0,
                acrg_value=0x78,acrg_reads=0,acrg_writes=0,vrctrl_value=0,vrctrl_reads=0,vrctrl_writes=0,
                analog_power='not-modeled',hardware_verified=False)
            silicon.update(spec['silicon'])
            expected['silicon'] = silicon
        expected['memory'] = None
        if 'memory' in spec:
            registers={hex(address):dict(value=value,reads=0,writes=0) for address,value in
                [(0x40021014,0x3f),(0x40021018,0xcf),(0x4002101c,2),(0x40021024,7),
                 (0x40021028,7),(0x4002102c,0x7e38),(0x40021040,0x1b0c)]}
            for address,changes in spec['memory'].items(): registers[address].update(changes)
            expected['memory'] = dict(rom_disables=spec.get('rom_disables',0),registers=registers)
        expected['hal'] = None
        if 'hal' in spec:
            registers={hex(a):dict(value=v,reads=0,writes=0) for a,v in hal_initial.items()}
            for address,changes in spec['hal'].items():registers[address].update(changes)
            expected['hal']=dict(catalog_sha256=CATALOG_SHA256,valid_calibration=False,registers=registers)
        expected['mram'] = None
        if 'mram' in spec:
            expected['mram'] = dict(value=2,reads=0,writes=0)
            expected['mram'].update(spec['mram'])
        expected['buck'] = dict(steps_completed=spec['buck'],complete=spec['buck']==10) if 'buck' in spec else None
        expected['start'] = None
        if 'start' in spec:
            registers={hex(a):dict(value=0,reads=0,writes=0) for a in (0x40020378,0x4002033c,0x40021100)}
            for address,changes in spec.get('start_registers',{}).items():registers[address].update(changes)
            expected['start']=dict(steps_completed=spec['start'],enable_requested=spec['start']==3,registers=registers)
        expected['prefetch'] = spec.get('prefetch')
        expected['status'] = spec.get('status')
        expected['response'] = spec.get('response')
        expected['tempco'] = spec.get('tempco')
        expected['clock'] = spec.get('clock')
        expected['gfx'] = spec.get('gfx')
        expected['preparation'] = spec.get('preparation')
        expected['power'] = spec.get('power')
        expected['gpu_irq_clear'] = spec.get('gpu_irq_clear')
        expected['gpu_id'] = spec.get('gpu_id')
        expected['gpu_ring'] = spec.get('gpu_ring')
        expected['gpu_identity'] = spec.get('gpu_identity')
        expected['gpu_reset'] = spec.get('gpu_reset')
        expected['gpu_raster'] = spec.get('gpu_raster')
        expected['gpu_config'] = spec.get('gpu_config')
        expected['gpu_status'] = spec.get('gpu_status')
        expected['gpu_off'] = spec.get('gpu_off')
        expected['gpu_off_sequence'] = spec.get('gpu_off_sequence')
        expected['gpio_config'] = spec.get('gpio_config')
        expected['gpio_idle'] = spec.get('gpio_idle')
        expected['gpio_output'] = spec.get('gpio_output')
        expected['adc_info'] = spec.get('adc_info')
        expected['adc_cal_control'] = spec.get('adc_cal_control')
        expected['adc_power'] = spec.get('adc_power')
        expected['adc_trigger'] = spec.get('adc_trigger')
        expected['adc_config'] = spec.get('adc_config')
        expected['adc_enable'] = spec.get('adc_enable')
        expected['adc_timer'] = spec.get('adc_timer')
        expected['memldo'] = spec.get('memldo')
        expected['coreldo'] = None
        if 'coreldo' in spec:
            expected['coreldo']=dict(original_word=hal_initial[0x40020080],expected_word=expected_word)
            expected['coreldo'].update(spec['coreldo'])
        pre_pause=None
        pause_verified=True
        if 'adc_timer' in spec:
            states=[line.partition('BLACKWALL_PREPAUSE ')[2].strip() for line in log.splitlines() if line.startswith('BLACKWALL_PREPAUSE ')]
            if len(states)!=1 or states[0] not in ('True','False'):raise ValueError('Missing pre-pause state: '+name)
            pre_pause=states[0]=='True'
            if spec.get('conversion_stop'):pause_verified=pre_pause
            elif 'returned' in spec:pause_verified=not pre_pause
        cases[name] = {'observed': observed, 'paused_before_monitor_pause':pre_pause, 'passed': observed == expected and pause_verified}
        print(name, 'passed' if cases[name]['passed'] else 'FAILED', flush=True)
    report = {'scope': 'guard integration only; no Apollo510 behavior validation',
              'image_id': image_id, 'cases': cases, 'passed': all(c['passed'] for c in cases.values()),
              'hardware_validated': False}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': report['passed'], 'cases': len(cases)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
